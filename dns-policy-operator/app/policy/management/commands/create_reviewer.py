# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Create reviewer command."""

import getpass

from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Create reviewer command."""

    help = 'Create a new reviewer'

    def add_arguments(self, parser):
        """Define CLI arguments."""
        parser.add_argument('username', type=str, help='Username of the user')
        parser.add_argument('email', type=str, help='Email of the user')

    def handle(self, *args, **options):
        """Handle CLI invocation."""
        username = options['username']
        email = options['email']

        # Took example on Django here
        # ref: https://github.com/django/django/blob/main/django/contrib/auth/management/commands/createsuperuser.py#L172
        password = getpass.getpass()
        password2 = getpass.getpass("Password (again): ")
        if password != password2:
            self.stderr.write("Error: Your passwords didn't match.")
            # Don't validate passwords that don't match.
            return
        if password.strip() == "":
            self.stderr.write("Error: Blank passwords aren't allowed.")
            # Don't validate blank passwords.
            return
        try:
            validate_password(password2)
        except exceptions.ValidationError as err:
            self.stderr.write("\n".join(err.messages))
            response = input(
                "Bypass password validation and create user anyway? [y/N]: "
            )
            if response.lower() != "y":
                return

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
                reviewer_group = Group.objects.get(name='Reviewers')
                user.groups.add(reviewer_group)
                self.stdout.write(self.style.SUCCESS(f'User {username} created successfully and added to Reviewers group'))
            except Group.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'User {username} created successfully, but Reviewers group does not exist'))
