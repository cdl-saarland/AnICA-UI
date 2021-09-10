from django.core.management.base import BaseCommand, CommandError
from basic_ui.models import import_campaign


class Command(BaseCommand):
    help = 'Imports a campaign from each specified campaign directory'

    def add_arguments(self, parser):
        parser.add_argument('campaign_dirs', nargs='+', type=str)

    def handle(self, *args, **options):
        for campaign_dir in options['campaign_dirs']:
            import_campaign(campaign_dir)
            self.stdout.write(self.style.SUCCESS('Successfully imported campaign "{}"'.format(campaign_dir)))
