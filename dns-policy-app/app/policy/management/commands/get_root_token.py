# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from django.core.management.base import BaseCommand
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
import json


class Command(BaseCommand):
    help = 'Obtain a JWT token for the root user'

    def handle(self, *args, **options):
        internal_user = User.objects.get(username='root')
        refresh_token = RefreshToken.for_user(internal_user)
        access_token = refresh_token.access_token
        token_data = {
            'access': str(access_token),
            'refresh': str(refresh_token),
        }
        self.stdout.write(json.dumps(token_data, indent=4))
