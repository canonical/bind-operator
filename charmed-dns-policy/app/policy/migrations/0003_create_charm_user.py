# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from django.db import migrations
from django.contrib.auth.models import User
import secrets
import string


def create_internal_user(apps, schema_editor):
    username = 'root'
    email = 'root@dnspolicy.local'
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

    User.objects.create_user(
        username=username,
        email=email,
        password=password,
        is_active=True,
        is_staff=True,
        is_superuser=True,
    )


def delete_internal_user(apps, schema_editor):
    User.objects.filter(username='root').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('policy', '0002_alter_recordrequest_status'),
    ]

    operations = [
        migrations.RunPython(create_internal_user, delete_internal_user),
    ]
