# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Create approver command."""

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Create approver command."""

    help = 'Create a new approver'

    def add_arguments(self, parser):
        """Define CLI arguments."""
        parser.add_argument('username', type=str, help='Username of the user')
        parser.add_argument('password', type=str, help='Password of the user')
        parser.add_argument('email', type=str, help='Email of the user')

    def handle(self, *args, **options):
        """Handle CLI invocation."""
        username = options['username']
        password = options['password']
        email = options['email']

        try:
            user = User.objects.get(username=username)
            self.stdout.write(self.style.WARNING(f'User {username} already exists'))
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_staff=True,
            )
            self.stdout.write(self.style.SUCCESS(f'User {username} created successfully'))
            try:
                approver_group = Group.objects.get(name='Approvers')
                user.groups.add(approver_group)
                self.stdout.write(self.style.SUCCESS(f'User {username} created successfully and added to Approvers group'))
            except Group.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'User {username} created successfully, but Approvers group does not exist'))
