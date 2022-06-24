from django.core.management.base import BaseCommand, CommandError
from basic_ui.models import compute_bbset_coverage


class Command(BaseCommand):
    help = 'Imports a campaign from each specified campaign directory'

    def add_arguments(self, parser):
        parser.add_argument('--campaigns', nargs='*', default=[], type=int)
        parser.add_argument('--bbsets', nargs='*', default=[], type=int)

    def handle(self, *args, **options):
        campaign_ids = options['campaigns']
        bbset_ids = options['bbsets']
        compute_bbset_coverage(campaign_ids, bbset_ids)
        self.stdout.write(self.style.SUCCESS('Done.'))

