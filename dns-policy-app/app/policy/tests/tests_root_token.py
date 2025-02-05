from django.test import TestCase
from django.core.management import call_command
from io import StringIO
import json
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from django.contrib.auth.models import User


class TestRootToken(TestCase):

    def setUp(self):
        self.internal_user = User.objects.get(username='root')

    def test_command_output(self):
        out = StringIO()
        call_command('get_root_token', stdout=out)
        output = out.getvalue()
        token_data = json.loads(output)
        self.assertIn('access', token_data)
        self.assertIn('refresh', token_data)

    def test_token_is_valid(self):
        out = StringIO()
        call_command('get_root_token', stdout=out)
        output = out.getvalue()
        token_data = json.loads(output)
        access_token = token_data['access']
        refresh_token = token_data['refresh']

        # Verify that the access token can be used to authenticate
        token = AccessToken(access_token)
        self.assertEqual(token.payload['user_id'], self.internal_user.id)

        # Verify that the refresh token can be used to refresh the access token
        new_refresh_token = RefreshToken(refresh_token)
        new_access_token = new_refresh_token.access_token
        self.assertIsNotNone(new_access_token)
