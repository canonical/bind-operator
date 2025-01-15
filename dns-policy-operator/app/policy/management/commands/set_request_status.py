from django.core.management.base import BaseCommand
from policy.models import RecordRequest

class Command(BaseCommand):
    help = 'Set the status of a request'

    def add_arguments(self, parser):
        parser.add_argument('request_id', type=str, help='ID of the request')
        parser.add_argument('status', type=str, help='New status of the request')
        parser.add_argument('--reason', type=str, help='Reason for the status change', default=None)

    def handle(self, *args, **options):
        request_id = options['request_id']
        status = options['status']
        reason = options['reason']

        try:
            request = RecordRequest.objects.get(pk=request_id)
        except RecordRequest.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Request with ID {request_id} does not exist'))
            return

        request.status = status
        if reason:
            request.status_reason = reason
        request.save()

        self.stdout.write(self.style.SUCCESS(f'Status of request {request_id} set to {status}'))
