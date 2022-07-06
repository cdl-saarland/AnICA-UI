from django.core.management.base import BaseCommand, CommandError
from basic_ui.models import import_basic_block_set


class Command(BaseCommand):
    help = 'Imports a basic block set from the specified csv file (columns: bb and one for every considered tool)'

    def add_arguments(self, parser):
        parser.add_argument('--isa', type=str, default="x86", help="instruction set architecture to assume when disassembling hex basic blocks (default: x86)")
        parser.add_argument('identifier', type=str, help="a unique identifier to refer to the basic block set in the UI")
        parser.add_argument('csv_file', type=str)

    def handle(self, *args, **options):
        isa = options['isa']
        identifier = options['identifier']
        csv_file = options['csv_file']
        bbset_id = import_basic_block_set(isa, identifier, csv_file)
        self.stdout.write(self.style.SUCCESS('Successfully imported basic block set "{}" with id {}'.format(csv_file, bbset_id)))

