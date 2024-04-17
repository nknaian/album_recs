from flask.helpers import url_for

from musicrecs.database.helpers import add_user_to_db
from musicrecs.database.models import User

from tests.test_user import UserTestCase


class UserLoginTestCase(UserTestCase):
    """Test flows involving POSTS to the user.login route

    The 'user.sp_auth_complete' route is also exercised through
    these tests.
    """

    def test_register_authed_user(self):
        """Test the scenario that a user who is already authenticated with musicrecs through their
        spotify account logs in for the first time (registration)
        """
        # Mock that a spotify user is already authenticated
        self.auth_dummy_user()

        # Visit main page. Verify that the text 'Log in' is on the page
        response = self.client.get(url_for('main.index'))
        self.assert_200(response)
        self.assertIn(bytes('Log in', 'utf-8'), response.data)

        # Make post to login from the main page
        response = self.client.post(
            url_for('user.login'),
            data=dict(login_with_spotify="Log in"),
            follow_redirects=False,
            headers={
                "Referer": url_for('main.index')  # set 'request.referrer' ('Referer' is not a typo lol)
            }
        )
        print("NAKDBG url_for = ", url_for('main.index'))
        # Verify that post was successful and redirected back to the main page
        self.assertEqual(response.location, url_for('main.index'))

        # Verify that the user was added to the database
        users = User.query.all()
        self.assertEqual(len(users), 1)

        user = users[0]
        self.assertEqual(user.id, 1)
        self.assertEqual(user.spotify_user_id, self.DUMMY_USER_SP_ID)

        # Verify that the round page now contains the submitter's name instead of 'Log in'
        response = self.client.get(url_for('main.index'))
        self.assert_200(response)
        self.assertNotIn(bytes('Log in', 'utf-8'), response.data)
        self.assertIn(bytes(self.DUMMY_USER_DISPLAY_NAME, 'utf-8'), response.data)

    def test_register_unauthed_user(self):
        # Visit main page. Verify that the text 'Log in' is on the page
        response = self.client.get(url_for('main.index'))
        self.assert_200(response)
        self.assertIn(bytes('Log in', 'utf-8'), response.data)

        # Make post to login from the main page
        response = self.client.post(
            url_for('user.login'),
            data=dict(login_with_spotify="Log in"),
            follow_redirects=True,
            headers={
                "Referer": url_for('main.index')  # set 'request.referrer' ('Referer' is not a typo lol)
            }
        )

        # Verify that the user was added to the database
        users = User.query.all()
        self.assertEqual(len(users), 1)

        user = users[0]
        self.assertEqual(user.id, 1)
        self.assertEqual(user.spotify_user_id, self.DUMMY_USER_SP_ID)

        # Verify that post was successful and redirected back to the main page
        # NOTE: I have a hacky solution of puttting in a string of text I know
        # will be on the main page. I can't figure out how to check the url
        # of the response so this is the best I could come up with.
        self.assert200(response)
        self.assertIn(bytes("Musicrecs is a platform", 'utf-8'), response.data)

        # Verify that the round page now contains the submitter's name instead of 'Log in'
        self.assertNotIn(bytes('Log in', 'utf-8'), response.data)
        self.assertIn(bytes(self.DUMMY_USER_DISPLAY_NAME, 'utf-8'), response.data)

    def test_login_user(self):
        # Add a fake user to the database
        add_user_to_db(self.DUMMY_USER_SP_ID, self.DUMMY_USER_DISPLAY_NAME)

        # Visit main page. Verify that the text 'Log in' is on the page
        response = self.client.get(url_for('main.index'))
        self.assert_200(response)
        self.assertIn(bytes('Log in', 'utf-8'), response.data)

        # Make post to login from the main page
        response = self.client.post(
            url_for('user.login'),
            data=dict(login_with_spotify="Log in"),
            follow_redirects=True,
            headers={
                "Referer": url_for('main.index')  # set 'request.referrer' ('Referer' is not a typo lol)
            }
        )

        # Verify that post was successful and redirected back to the main page
        # NOTE: I have a hacky solution of puttting in a string of text I know
        # will be on the main page. I can't figure out how to check the url
        # of the response so this is the best I could come up with.
        self.assert200(response)
        self.assertIn(bytes("Musicrecs is a platform", 'utf-8'), response.data)

        # Verify that the round page now contains the submitter's name instead of 'Log in'
        self.assertNotIn(bytes('Log in', 'utf-8'), response.data)
        self.assertIn(bytes(self.DUMMY_USER_DISPLAY_NAME, 'utf-8'), response.data)
