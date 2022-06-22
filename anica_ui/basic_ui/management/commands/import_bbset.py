from django.core.management.base import BaseCommand, CommandError
from basic_ui.models import import_basic_block_set


class Command(BaseCommand):
    help = 'Imports a basic block set from the specified csv file (columns: bb and one for every considered tool)'

    def add_arguments(self, parser):
        parser.add_argument('identifier', type=str)
        parser.add_argument('csv_file', type=str)

    def handle(self, *args, **options):
        identifier = options['identifier']
        csv_file = options['csv_file']
        import_basic_block_set(identifier, csv_file)
        self.stdout.write(self.style.SUCCESS('Successfully imported basic block set "{}"'.format(csv_file)))

