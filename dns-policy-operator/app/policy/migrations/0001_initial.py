# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import migrations, models


def create_reviewer_group(apps, schema_editor):
    reviewer_group, created = Group.objects.get_or_create(name="Reviewers")

    record_request_content_type, created = ContentType.objects.get_or_create(
        app_label="policy", model="recordrequest"
    )

    # Ref: https://docs.djangoproject.com/en/stable/topics/auth/default/#programmatically-creating-permissions
    permissions = ["view_recordrequest", "change_recordrequest", "delete_recordrequest"]
    for permission_name in permissions:
        permission, created = Permission.objects.get_or_create(
            name=f"Can {permission_name.replace("_", " ")}",
            codename=permission_name,
            content_type=record_request_content_type,
        )
        reviewer_group.permissions.add(permission)

    reviewer_group.save()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RecordRequest",
            fields=[
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("domain", models.CharField(max_length=255)),
                ("host_label", models.CharField(max_length=255)),
                ("ttl", models.IntegerField(null=True)),
                ("record_type", models.CharField(max_length=10)),
                ("record_data", models.CharField(max_length=255)),
                ("requirer_id", models.CharField(max_length=255)),
                ("status", models.CharField(max_length=50)),
                ("status_reason", models.CharField(max_length=255, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "last_modified_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "reviewer",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.RunPython(
            code=create_reviewer_group,
        ),
        migrations.AlterField(
            model_name="recordrequest",
            name="requirer_id",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.RenameField(
            model_name="recordrequest",
            old_name="reviewer",
            new_name="reviewer",
        ),
        migrations.AddField(
            model_name="recordrequest",
            name="active",
            field=models.BooleanField(default=False),
        ),
    ]
