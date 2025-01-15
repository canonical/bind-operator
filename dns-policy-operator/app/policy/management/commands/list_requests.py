from django.core.management.base import BaseCommand
from policy.models import RecordRequest

class Command(BaseCommand):
    help = 'List all requests with a certain status'

    def add_arguments(self, parser):
        parser.add_argument('status', type=str, help='Status of the requests to list')

    def handle(self, *args, **options):
        status = options['status']

        requests = RecordRequest.objects.filter(status=status)

        if requests.exists():
            for request in requests:
                self.stdout.write(self.style.SUCCESS(f'{request.pk}, {request}'))
        else:
            self.stdout.write(self.style.WARNING(f'No requests found with status "{status}"'))
