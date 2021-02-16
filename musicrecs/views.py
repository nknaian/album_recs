import random
import secrets
from typing import List, Tuple

from flask import render_template, redirect, url_for, flash
from flask.globals import request

import musicrecs.random_words.random_words as random_words

from musicrecs import app
from musicrecs import db
from musicrecs import spotify_iface
from musicrecs.sql_models import Submission, Round
from musicrecs.forms import NewRoundForm, TrackrecForm, AlbumrecForm, PlaylistForm
from musicrecs.enums import RoundStatus, MusicType, SnoozinRecType
from musicrecs.exceptions import UserError, InternalError
from musicrecs.spotify import spotify_user
from musicrecs import external_auth
from musicrecs.spotify.item.spotify_music import SpotifyMusic


'''ROUTES'''


@app.route('/', methods=('GET', 'POST'))
@app.route('/index', methods=('GET', 'POST'))
def index():
    new_round_form = NewRoundForm()

    try:
        if new_round_form.validate_on_submit():
            # Get the new_round_form fields
            description = new_round_form.description.data
            music_type = new_round_form.music_type.data
            snoozin_rec_type = new_round_form.snoozin_rec_type.data

            # Add the round to the database
            new_round = Round(
                description=description,
                music_type=music_type,
                snoozin_rec_type=snoozin_rec_type,
                long_id=secrets.token_urlsafe(16)
            )
            db.session.add(new_round)
            db.session.commit()

            # Go to the page for the new round
            return redirect(url_for('round', long_id=new_round.long_id))

        elif new_round_form.errors:
            raise InternalError(new_round_form.errors)

    except UserError as e:
        flash(e, "warning")
    except InternalError as e:
        flash(e, "danger")

    return render_template('index.html', new_round_form=new_round_form)


@app.route('/round/<string:long_id>', methods=["GET", "POST"])
def round(long_id):
    # Get the round from the long id
    round = Round.query.filter_by(long_id=long_id).first()

    # Prepare the forms
    if round.music_type == MusicType.album:
        rec_form = AlbumrecForm()
        playlist_form = None
    elif round.music_type == MusicType.track:
        rec_form = TrackrecForm()
        playlist_form = PlaylistForm()
        playlist_form.playlist_name.data = round.description  # prefill
    else:
        raise Exception(f"Unknown music type {round.music_type}")

    if round.status == RoundStatus.submit:
        return render_template('round/submit_phase.html',
                               rec_form=rec_form,
                               round=round)
    elif round.status == RoundStatus.listen or round.status == RoundStatus.revealed:
        # Get the playlist
        if round.playlist_link:
            playlist = spotify_iface.get_playlist_from_link(round.playlist_link)
        else:
            playlist = None

        return render_template('round/listen_phase.html',
                               round=round,
                               music_submissions=_get_shuffled_music_submissions(round),
                               playlist_form=playlist_form,
                               playlist=playlist,
                               revealed=RoundStatus.revealed)


@app.route('/round/<string:long_id>/advance', methods=['POST'])
def round_advance(long_id):
    # Get the round from the long id
    round = Round.query.filter_by(long_id=long_id).first()

    # Perform actions that are round phase transition specific
    if 'advance_to_listen' in request.form:
        try:
            # Add snoozin's rec:
            new_submission = Submission(
                spotify_link=_get_snoozin_rec(round).link,
                user_name="snoozin",
                round_id=round.id,
            )
            db.session.add(new_submission)

            # Advance to 'listen' phase
            round.status = RoundStatus.listen

            db.session.commit()
        except UserError as e:
            flash(e, "warning")
        except InternalError as e:
            flash(e, "danger")
    elif 'advance_to_revealed' in request.form:
        round.status = RoundStatus.revealed
        db.session.commit()

    # Go back to the round page
    return redirect(url_for('round', long_id=long_id))


@app.route('/round/<string:long_id>/submit_rec', methods=['POST'])
def round_submit_rec(long_id):
    # Get the round from the long id
    round = Round.query.filter_by(long_id=long_id).first()

    # Get the correct recommendation form
    if round.music_type == MusicType.album:
        rec_form = AlbumrecForm()
    elif round.music_type == MusicType.track:
        rec_form = TrackrecForm()
    else:
        raise InternalError(f"Unknown music type {round.music_type.name}")

    try:
        # Process the music recommendation
        if rec_form.validate_on_submit():
            # Get the rec_form fields
            user_name = rec_form.name.data
            spotify_link = rec_form.spotify_link.data

            # Verify form info
            if spotify_iface.spotify_link_invalid(round.music_type, spotify_link):
                raise UserError(f"Invalid spotify {round.music_type.name} link")
            elif _user_name_taken(round, user_name):
                raise UserError(f"The name \"{user_name}\" is taken already for this round!")
            elif user_name == "snoozin":
                raise UserError("This town's only big enough for one snoozin...")

            # Add the submission to the database
            new_submission = Submission(
                spotify_link=spotify_link,
                user_name=user_name,
                round_id=round.id,
            )
            db.session.add(new_submission)
            db.session.commit()

            # Alert the user that the form was successfully submitted
            flash("Successfully submitted your recommendation: "
                  f"{spotify_iface.get_music_from_link(round.music_type, spotify_link)}",
                  "success")

            # Reload the round page
            return redirect(url_for('round', long_id=long_id))

        elif rec_form.errors:
            raise InternalError(rec_form.errors)

    except UserError as e:
        flash(e, "warning")
    except InternalError as e:
        flash(e, "danger")

    # Retain form entries when there was a mistake in the submission
    return render_template('round/submit_phase.html',
                           rec_form=rec_form,
                           round=round)


@app.route('/round/<string:long_id>/create_playlist', methods=['GET', 'POST'])
@external_auth.recover_after_auth()
def round_create_playlist(long_id, recovered_form_data=None):
    # Get the round from the long id
    round = Round.query.filter_by(long_id=long_id).first()

    # Make sure this is a 'track' round...or else making a playlist doesn't make
    # any sense
    assert round.music_type == MusicType.track

    # Get the form data
    if recovered_form_data:
        playlist_form = PlaylistForm(recovered_form_data)
    else:
        playlist_form = PlaylistForm()

    # Make the playlist!
    if playlist_form.validate():
        playlist_name = playlist_form.playlist_name.data

        # Get a list of the tracks in the round (in the 'shuffled' order)
        tracks = [track for _, track in _get_shuffled_music_submissions(round)]

        # Make the playlist
        new_playlist = spotify_user.create_playlist(playlist_name, tracks)

        # Add the playlist to the database
        round.playlist_link = new_playlist.link
        db.session.commit()

        flash(f"Created a playlist for the round: {new_playlist.name}", "success")

    return redirect(url_for('round', long_id=long_id))


'''PRIVATE FUNCTIONS'''


def _user_name_taken(round: Round, user_name: str) -> bool:
    for submission in round.submissions:
        if submission.user_name == user_name:
            return True
    return False


# TODO: maybe we need to put in a max number of search attempts for buggy situations...
def _get_snoozin_rec(round: Round):
    snoozin_rec = None
    if round.snoozin_rec_type == SnoozinRecType.random:
        rw_gen = random_words.RandomWords()
        num_words = random.randint(1, 2)

        search_term = ""
        while snoozin_rec is None:
            search_term = " ".join(
                rw_gen.get_random_words(num_words)
            )
            snoozin_rec = spotify_iface.search_for_music(round.music_type, search_term)

        # Set the round's search term
        round.snoozin_rec_search_term = search_term
        db.session.commit()

    elif round.snoozin_rec_type == SnoozinRecType.similar:
        snoozin_rec = spotify_iface.recommend_music(round.music_type, _get_music_list(round))
    else:
        raise InternalError("Unknown Snoozin rec type")

    return snoozin_rec


def _get_music_list(round: Round) -> List[SpotifyMusic]:
    """Get a list of the music in the round in the order it was submitted"""
    return [
        spotify_iface.get_music_from_link(
            round.music_type, submission.spotify_link
        ) for submission in round.submissions
    ]


def _get_shuffled_music_submissions(round: Round) -> List[Tuple[str, SpotifyMusic]]:
    """Get a shuffled list of tuples of the username paired with
    the music they submitted for the round
    """
    # Make a list large enough to hold the submissions
    shuffled_music_submissions = [None] * len(round.submissions)

    # Shuffle the submissions if they haven't been already
    _shuffle_music_submissions(round)

    # Add a tuple of user_name and music at the 'shuffled position' of the new list
    for submission in round.submissions:
        shuffled_music_submissions[submission.shuffled_pos] = (
            submission.user_name,
            spotify_iface.get_music_from_link(round.music_type, submission.spotify_link)
        )

    # Make sure that every spot in the list was filled
    assert all(shuffled_music_submissions)

    return shuffled_music_submissions


def _shuffle_music_submissions(round: Round, reshuffle=False):
    """Shuffle the submissions in the round by storing a random
    'shuffled_pos' in each db entry.

    By default, this will have no effect if the submissions have
    already been shuffled, but that behavior can be overridden by
    passing `reshuffle=True`.
    """
    # Bail if we've already shuffled it `reshuffle` was not specified
    if (round.submissions[0].shuffled_pos is not None) and (not reshuffle):
        return

    # Create a random order on integers from 0 to the number of submissions
    # Ex for 6 submissions: `[4, 3, 5, 0, 1, 2]` (first submitted should be
    # shuffled to the fourth spot, second submitted should be shuffled to
    # the third spot etc.)
    rand_order = list(range(len(round.submissions)))
    random.shuffle(rand_order)

    # Assign each submission a 'shuffled position' using the `rand_order`
    for submission, rand_num in zip(
        round.submissions,
        rand_order
    ):
        submission.shuffled_pos = rand_num

    # commit the shuffled possitions to the database
    db.session.commit()
