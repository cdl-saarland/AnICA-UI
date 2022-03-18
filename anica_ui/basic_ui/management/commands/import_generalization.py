from django.core.management.base import BaseCommand, CommandError
from basic_ui.models import import_generalization


class Command(BaseCommand):
    help = 'Imports a campaign from each specified campaign directory'

    def add_arguments(self, parser):
        parser.add_argument('generalization_dirs', nargs='+', type=str)

    def handle(self, *args, **options):
        for gen_dir in options['generalization_dirs']:
            import_generalization(gen_dir)
            self.stdout.write(self.style.SUCCESS('Successfully imported generalization "{}"'.format(gen_dir)))

