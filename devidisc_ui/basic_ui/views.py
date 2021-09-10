from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
import django

# Create your views here.

from .models import Campaign, Discovery

import django_tables2 as tables

class CampaignTable(tables.Table):
    campaign_id = tables.Column(linkify=(lambda value: django.urls.reverse('basic_ui:campaign', kwargs={'campaign_id': value})))
    date = tables.Column()
    host_pc = tables.Column()
    num_batches = tables.Column()
    num_discoveries = tables.Column()
    seconds_spent = tables.Column()

def index(request):
    campaigns = Campaign.objects.all()

    data = []
    for campaign in campaigns:
        batches = campaign.discoverybatch_set.all()
        num_discoveries = sum([b.discovery_set.count() for b in batches])
        data.append({
            'campaign_id': campaign.id,
            'date': campaign.date,
            'host_pc': campaign.host_pc,
            'num_batches': len(batches),
            'num_discoveries': num_discoveries,
            'seconds_spent': campaign.total_seconds,
            })

    table = CampaignTable(data)

    return render(request, "basic_ui/data_table.html", {
        "title": "All Campaigns",
        "table": table
    })


def campaign(request, campaign_id):
    campaign_obj = get_object_or_404(Campaign, pk=campaign_id)

    tool_list = campaign_obj.tools.all()

    termination_condition = list(campaign_obj.termination_condition.items())

    total_seconds = campaign_obj.total_seconds

    remaining_time = total_seconds
    time_entries = []
    for kind, factor in (('seconds', 60), ('minutes', 60), ('hours', 24), ('days', None)):
        if factor is  None:
            curr_val = remaining_time
            remaining_time = 0
        else:
            curr_val = remaining_time % factor
            remaining_time = remaining_time // 60
        time_entries.append((kind, curr_val))
        if remaining_time <= 0:
            break

    if len(time_entries) > 2:
        time_entries = time_entries[-2:]
    time_entries.reverse()

    time_spent = ", ".join((f"{val} {kind}" for kind, val in time_entries))

    context = {
            'campaign': campaign_obj,
            'tool_list': tool_list,
            'termination_condition': termination_condition,
            'time_spent': time_spent,
        }

    return render(request, 'basic_ui/campaign_overview.html', context)


class DiscoveryTable(tables.Table):
    gen_id = tables.Column()
    absblock = tables.Column()
    num_insns = tables.Column()
    coverage = tables.Column()
    mean_interestingness = tables.Column()
    witness_len = tables.Column()

def discoveries(request, campaign_id):
    table = DiscoveryTable(Discovery.objects.filter(batch__campaign_id=campaign_id))

    return render(request, "basic_ui/data_table.html", {
        "title": "Discoveries",
        "table": table
    })

