# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Create reviewer command."""

import getpass
import os
import secrets
import select
import string
import sys

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
        parser.add_argument('--generate_password', action='store_true', help='Generate password')

    def handle(self, *args, **options):
        """Handle CLI invocation."""
        password = ""

        if options["generate_password"]:
            password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

        if password == "":
            # Check if there is any input available on sys.stdin
            rlist, _, _ = select.select([sys.stdin], [], [], 0)
            if rlist:
                # Read password from STDIN
                password = sys.stdin.readline().strip()

        if password == "":
            # Check if there is a password given in the environment
            password = os.getenv("POLICY_REVIEWER_PASSWORD", "")

        if password == "":
            # Fallback to prompting the user for a password
            # Took example on Django here
            # ref: https://github.com/django/django/blob/main/django/contrib/auth/management/commands/createsuperuser.py#L172
            password = getpass.getpass()
            password_repeat = getpass.getpass("Password (again): ")
            if password != password_repeat:
                self.stderr.write("Error: Your passwords didn't match.")
                # Don't validate passwords that don't match.
                return

        if password.strip() == "":
            self.stderr.write("Error: Blank passwords aren't allowed.")
            # Don't validate blank passwords.
            return
        try:
            validate_password(password)
        except exceptions.ValidationError as err:
            self.stderr.write("\n".join(err.messages))
            return

        user, created = User.objects.get_or_create(
            username=options['username'],
            defaults={
                'email': options['email'],
                'is_staff': True,
            }
        )
        if not created:
            self.stdout.write(self.style.WARNING(f'User {options['username']} already exists'))
            return

        user.set_password(password)
        user.save()

        reviewer_group, _ = Group.objects.get_or_create(name='Reviewers')
        user.groups.add(reviewer_group)
        self.stdout.write(self.style.SUCCESS(f'User {options['username']} created successfully'))
        if options["generate_password"]:
            self.stdout.write(self.style.SUCCESS(f'Generated password: {password}'))
