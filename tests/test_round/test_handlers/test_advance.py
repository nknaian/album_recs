from unittest.mock import Mock

from flask.helpers import url_for

from musicrecs import spotify_iface
from musicrecs.enums import MusicType, RoundStatus, SnoozinRecType
from musicrecs.spotify.item.spotify_music import SpotifyAlbum, SpotifyTrack
from musicrecs.database.models import Round, Submission
from musicrecs.database.helpers import add_round_to_db, add_submission_to_db

from tests.test_round import RoundTestCase


class RoundAdvanceTestCase(RoundTestCase):
    """Test POST to round.advance route

    For every important permutation of round status transition,
    music_type and snoozin_rec_type - make sure that the round status
    changes, and any intermediate actions are accomplished.
    """
    def test_track_random_advance_to_listen(self):
        # Add a round to the database
        round = add_round_to_db(
            description="Trackrecs random round",
            music_type=MusicType.track,
            snoozin_rec_type=SnoozinRecType.random,
            status=RoundStatus.submit
        )

        # Add a submission to the round
        add_submission_to_db(round.id, None, "John Doe", "http://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6")

        # Mock the search_for_music spotify interface
        def _mock_search_for_music(*args, **kwargs):
            track_mock = Mock(spec=SpotifyTrack)
            track_mock.link = "http://open.spotify.com/track/7GhIk7Il098yCjg4BQjzvb"

            return [track_mock]

        spotify_iface.search_for_music = Mock(side_effect=_mock_search_for_music)

        # Run the advance to listen test
        self._test_advance_to_listen(round, "http://open.spotify.com/track/7GhIk7Il098yCjg4BQjzvb")

    def test_track_similar_advance_to_listen(self):
        # Add a round to the database
        round = add_round_to_db(
            description="Trackrecs similar round",
            music_type=MusicType.track,
            snoozin_rec_type=SnoozinRecType.similar,
            status=RoundStatus.submit
        )

        # Add a submission to the round
        add_submission_to_db(round.id, None, "Dory Johnson", "http://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6")

        # Mock the recommend_music spotify interface
        def _mock_recommend_music(*args):
            track_mock = Mock(spec=SpotifyTrack)
            track_mock.link = "http://open.spotify.com/track/7GhIk7Il098yCjg4BQjzvb"

            return track_mock

        spotify_iface.recommend_music = Mock(side_effect=_mock_recommend_music)

        # Run the advance to listen test
        self._test_advance_to_listen(round, "http://open.spotify.com/track/7GhIk7Il098yCjg4BQjzvb")

    def test_album_random_advance_to_listen(self):
        # Add a round to the database
        round = add_round_to_db(
            description="Albumrecs random round",
            music_type=MusicType.album,
            snoozin_rec_type=SnoozinRecType.random,
            status=RoundStatus.submit
        )

        # Add a submission to the round
        add_submission_to_db(round.id, None, "Nick Jones", "https://open.spotify.com/album/3a0UOgDWw2pTajw85QPMiz")

        # Mock the search_for_music spotify interface
        def _mock_search_for_music(*args, **kwargs):
            album_mock = Mock(spec=SpotifyAlbum)
            album_mock.link = "https://open.spotify.com/album/5Z9iiGl2FcIfa3BMiv6OIw"

            return [album_mock]

        spotify_iface.search_for_music = Mock(side_effect=_mock_search_for_music)

        # Run the advance to listen test
        self._test_advance_to_listen(round, "https://open.spotify.com/album/5Z9iiGl2FcIfa3BMiv6OIw")

    def test_album_similar_advance_to_listen(self):
        # Add a round to the database
        round = add_round_to_db(
            description="Albumrecs similar round",
            music_type=MusicType.album,
            snoozin_rec_type=SnoozinRecType.similar,
            status=RoundStatus.submit
        )

        # Add a submission to the round
        add_submission_to_db(round.id, None, "Jonie Nixon", "https://open.spotify.com/album/3a0UOgDWw2pTajw85QPMiz")

        # Mock the recommend_music spotify interface
        def _mock_recommend_music(*args):
            album_mock = Mock(spec=SpotifyAlbum)
            album_mock.link = "https://open.spotify.com/album/5Z9iiGl2FcIfa3BMiv6OIw"

            return album_mock

        spotify_iface.recommend_music = Mock(side_effect=_mock_recommend_music)

        # Run the advance to listen test
        self._test_advance_to_listen(round, "https://open.spotify.com/album/5Z9iiGl2FcIfa3BMiv6OIw")

    def test_track_advance_to_revealed(self):
        # Add a round to the database
        round = add_round_to_db(
            description="Trackrecs random round",
            music_type=MusicType.track,
            snoozin_rec_type=SnoozinRecType.random,
            status=RoundStatus.listen
        )

        # Add a submission to the round
        add_submission_to_db(round.id, None, "John Doe", "http://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6")

        # Run the advance to revealed test
        self._test_advance_to_revealed(round)

    def test_album_advance_to_revealed(self):
        # Add a round to the database
        round = add_round_to_db(
            description="Albumrecs random round",
            music_type=MusicType.album,
            snoozin_rec_type=SnoozinRecType.random,
            status=RoundStatus.listen
        )

        # Add a submission to the round
        add_submission_to_db(round.id, None, "Nick Jones", "https://open.spotify.com/album/3a0UOgDWw2pTajw85QPMiz")

        # Run the advance to revealed test
        self._test_advance_to_revealed(round)

    def _test_advance_to_listen(self, round: Round, snoozin_spotify_link: str):
        # post 'round.advance'
        response = self.client.post(
            url_for('round.advance', long_id=round.long_id),
            data=dict(advance_to_listen="Advance to listen"),
            follow_redirects=False
        )

        # Verify that post was successfull, and redirected
        self.assertEqual(response.location, url_for('round.index', long_id=round.long_id))

        # Verify that GET the round.listen is successful
        response = self.client.get(url_for('round.listen', long_id=round.long_id))
        self.assert_200(response)

        # Verify that the database now contains snoozin's submission
        snoozin_submission = Submission.query.filter_by(user_name="snoozin").first()
        self.assertIsNotNone(snoozin_submission)
        self.assertEqual(snoozin_submission.spotify_link, snoozin_spotify_link)

    def _test_advance_to_revealed(self, round: Round):
        # post 'round.advance'
        response = self.client.post(
            url_for('round.advance', long_id=round.long_id),
            data=dict(advance_to_revealed="Advance to revealed"),
            follow_redirects=False
        )

        # Verify that post was successfull, and redirected
        self.assertEqual(response.location, url_for('round.index', long_id=round.long_id))

        # Verify that the GET to the round.revealed is successfull
        response = self.client.get(url_for('round.revealed', long_id=round.long_id))
        self.assert_200(response)
