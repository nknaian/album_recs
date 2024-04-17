from flask.helpers import url_for

from musicrecs.enums import MusicType, SnoozinRecType
from musicrecs.database.models import Submission
from musicrecs.database.helpers import add_round_to_db, add_user_to_db

from tests.test_round import RoundTestCase


class RoundSubmitTestCase(RoundTestCase):
    """Test POST and GET to round.submit route

    For each permutation of music type and snoozin rec type,
    create a new round in the database and submit one spotify
    link using the round.submit_rec route. Then, make sure that
    the submission was correctly added.
    """

    """TESTS"""

    def test_submit_rec_track_random(self):
        round = add_round_to_db(
            description="Trackrecs random round",
            music_type=MusicType.track,
            snoozin_rec_type=SnoozinRecType.random,
        )

        self._test_submit_rec(
            round_long_id=round.long_id,
            rec_name="John Doe",
            rec_spotify_link="http://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6"
        )

    def test_submit_rec_track_similar(self):
        round = add_round_to_db(
            description="Trackrecs similar round",
            music_type=MusicType.track,
            snoozin_rec_type=SnoozinRecType.similar,
        )

        self._test_submit_rec(
            round_long_id=round.long_id,
            rec_name="Dory Johnson",
            rec_spotify_link="http://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6"
        )

    def test_submit_rec_album_random(self):
        round = add_round_to_db(
            description="Albumrecs random round",
            music_type=MusicType.album,
            snoozin_rec_type=SnoozinRecType.random,
        )

        self._test_submit_rec(
            round_long_id=round.long_id,
            rec_name="Nick Jones",
            rec_spotify_link="https://open.spotify.com/album/3a0UOgDWw2pTajw85QPMiz"
        )

    def test_submit_rec_album_similar(self):
        round = add_round_to_db(
            description="Albumrecs similar round",
            music_type=MusicType.album,
            snoozin_rec_type=SnoozinRecType.similar,
        )

        self._test_submit_rec(
            round_long_id=round.long_id,
            rec_name="Jonie Nixon",
            rec_spotify_link="https://open.spotify.com/album/3a0UOgDWw2pTajw85QPMiz"
        )

    def test_multiple_submit_rec_with_loggedin_user(self):
        """Test main usecases when submitting while logged in.

        1. Submit a song to the round while logged in
        2. Submit another song and make sure that your submission is changed
        """
        # Add a fake user to the database
        add_user_to_db(self.DUMMY_USER_SP_ID, self.DUMMY_USER_DISPLAY_NAME)

        # Mock authentication of the fake user
        self.auth_dummy_user()

        # Add a round to the database
        round = add_round_to_db(
            description="Trackrecs random round with logged in user",
            music_type=MusicType.track,
            snoozin_rec_type=SnoozinRecType.random,
        )

        # Make post with rec form data
        response = self.client.post(
            url_for('round.submit', long_id=round.long_id),
            data=dict(name="Dummy Alias", spotify_link="http://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6"),
            follow_redirects=False
        )

        # Verify that post was successfull, and redirected
        self.assertEqual(response.location, url_for('round.submit', long_id=round.long_id))

        # Verify that the submission was successfully added to the database
        submissions = Submission.query.all()
        self.assertEqual(len(submissions), 1)

        submission = submissions[0]
        self.assertEqual(submission.user_name, "Dummy Alias")
        self.assertEqual(submission.spotify_link, "http://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6")

        # Re-submit with different name and link
        response = self.client.post(
            url_for('round.submit', long_id=round.long_id),
            data=dict(name="Dummier Alias", spotify_link="https://open.spotify.com/track/2ctvdKmETyOzPb2GiJJT53"),
            follow_redirects=False
        )

        # Verify that post was successfull, and redirected
        self.assertEqual(response.location, url_for('round.submit', long_id=round.long_id))

        # Verify that the same submission now has the new values
        self.assertEqual(submission.user_name, "Dummier Alias")
        self.assertEqual(submission.spotify_link, "https://open.spotify.com/track/2ctvdKmETyOzPb2GiJJT53")

    """PRIVATE FUNCTIONS"""

    def _test_submit_rec(self, round_long_id, rec_name, rec_spotify_link):
        """Common code for test_submit_rec_<music_type>_<snoozin_rec_type> tests"""
        # Make post with the rec form data
        response = self.client.post(
            url_for('round.submit', long_id=round_long_id),
            data=dict(name=rec_name, spotify_link=rec_spotify_link),
            follow_redirects=False
        )

        # Verify that post was successfull, and redirected
        self.assertEqual(response.location, url_for('round.submit', long_id=round_long_id))

        # Verify that the submission was successfully added to the database
        submissions = Submission.query.all()
        self.assertEqual(len(submissions), 1)

        submission = submissions[0]
        self.assertEqual(submission.user_name, rec_name)
        self.assertEqual(submission.spotify_link, rec_spotify_link)

        # Verify that the round page now contains the submitter's name
        response = self.client.get(url_for('round.submit', long_id=round_long_id))
        self.assert_200(response)
        self.assertIn(bytes(rec_name, 'utf-8'), response.data)
