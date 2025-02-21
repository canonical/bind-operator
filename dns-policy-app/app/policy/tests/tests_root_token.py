# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test root token creation command."""

import json
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken


class TestRootToken(TestCase):
    """Test root token."""

    def setUp(self):
        """Set up."""
        self.internal_user = User.objects.get(username='root')

    def test_command_output(self):
        """Test command output."""
        out = StringIO()
        call_command('get_root_token', stdout=out)
        output = out.getvalue()
        token_data = json.loads(output)
        self.assertIn('access', token_data)
        self.assertIn('refresh', token_data)

    def test_token_is_valid(self):
        """Test token validity."""
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
