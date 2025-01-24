# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Create record request command."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from policy.models import RecordRequest


class Command(BaseCommand):
    """Create Record Request command."""
    help = 'Create a new record request'

    def add_arguments(self, parser):
        """Define CLI arguments."""
        parser.add_argument('host_label', type=str, help='Host label')
        parser.add_argument('domain', type=str, help='Domain name')
        parser.add_argument('ttl', type=int, help='TTL')
        parser.add_argument('record_type', type=str, help='Record type')
        parser.add_argument('record_data', type=str, help='Record data')
        parser.add_argument('--requirer_id', type=str, help='Requirer ID', nargs='?', default=None)
        parser.add_argument('--status', type=str, help='Status', nargs='?', default="pending")
        parser.add_argument('--status_reason', type=str, help='Status reason', nargs='?', default=None)
        parser.add_argument('--reviewer', type=str, help='Reviewer username', nargs='?', default=None)

    def handle(self, *args, **options):
        """Handle CLI invocation."""
        domain = options['domain']
        host_label = options['host_label']
        ttl = options['ttl']
        record_type = options['record_type']
        record_data = options['record_data']
        requirer_id = options['requirer_id']
        status = options['status']
        status_reason = options['status_reason']
        reviewer_username = options['reviewer']

        if reviewer_username:
            try:
                reviewer = User.objects.get(username=reviewer_username)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Reviewer with username "{reviewer_username}" does not exist'))
                return
        else:
            reviewer = None

        record_request = RecordRequest(
            domain=domain,
            host_label=host_label,
            ttl=ttl,
            record_type=record_type,
            record_data=record_data,
            requirer_id=requirer_id,
            status=status,
            status_reason=status_reason,
            reviewer=reviewer
        )
        record_request.save()

        self.stdout.write(self.style.SUCCESS(f'Record request created successfully: {record_request}'))
