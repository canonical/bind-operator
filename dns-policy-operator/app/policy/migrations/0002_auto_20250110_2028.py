from django.db import migrations
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


def create_approver_group(apps, schema_editor):
    approver_group, created = Group.objects.get_or_create(name='Approvers')

    record_request_content_type, created = ContentType.objects.get_or_create(
        app_label='policy',
        model='recordrequest'
    )

    # Ref: https://docs.djangoproject.com/en/stable/topics/auth/default/#programmatically-creating-permissions
    permissions = ['view_recordrequest', 'change_recordrequest', 'delete_recordrequest']
    for permission_name in permissions:
        permission, created = Permission.objects.get_or_create(
            name=f"Can {permission_name.replace("_", " ")}",
            codename=permission_name,
            content_type=record_request_content_type,
        )
        approver_group.permissions.add(permission)

    approver_group.save()


class Migration(migrations.Migration):
    dependencies = [
        ('policy', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(create_approver_group),
    ]
