from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
import django

from django.db.models import F

import json

from devidisc.abstractblock import AbstractBlock
from devidisc.abstractioncontext import AbstractionContext
# Create your views here.

from .models import Campaign, Discovery

import django_tables2 as tables

def load_abstract_block(json_dict, actx):
    if actx is None:
        config_dict = json_dict['config']
        config_dict['predmanager'] = None # we don't need that one here
        actx = AbstractionContext(config=config_dict)

    # result_ref = json_dict['result_ref']

    ab_dict = actx.json_ref_manager.resolve_json_references(json_dict['ab'])

    ab = AbstractBlock.from_json_dict(actx, ab_dict)
    return ab#, result_ref

def prettify_seconds(secs):
    remaining_time = secs
    time_entries = []
    for kind, factor in (('seconds', 60), ('minutes', 60), ('hours', 24), ('days', None)):
        if factor is None:
            curr_val = remaining_time
            remaining_time = 0
        else:
            curr_val = remaining_time % factor
            remaining_time = remaining_time // factor
        time_entries.append((kind, curr_val))
        if remaining_time <= 0:
            break
    if len(time_entries) > 2:
        time_entries = time_entries[-2:]
    time_entries.reverse()
    return ", ".join((f"{val} {kind}" for kind, val in time_entries))

campaign_table_attrs = {"class": "campaigntable"}

class CampaignTable(tables.Table):
    campaign_id = tables.Column(
            linkify=(lambda value: django.urls.reverse('basic_ui:campaign', kwargs={'campaign_id': value})),
            attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Campaign ID")
    date = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Start Date")
    host_pc = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Host PC")
    tools = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Tools under Investigation")
    num_batches = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="# Batches")
    num_discoveries = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="# Discoveries")
    time_spent = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Run-Time")

    class Meta:
        row_attrs = campaign_table_attrs

def index(request):
    campaigns = Campaign.objects.all()

    data = []
    for campaign in campaigns:
        batches = campaign.discoverybatch_set.all()
        num_discoveries = sum([b.discovery_set.count() for b in batches])
        tool_list = campaign.tools.all()
        data.append({
            'campaign_id': campaign.id,
            'tools': ", ".join(map(str, tool_list)),
            'date': campaign.date,
            'host_pc': campaign.host_pc,
            'num_batches': len(batches),
            'num_discoveries': num_discoveries,
            'time_spent': prettify_seconds(campaign.total_seconds),
            })

    table = CampaignTable(data)

    tables.RequestConfig(request).configure(table)

    return render(request, "basic_ui/data_table.html", {
        "title": "All Campaigns",
        "table": table
    })



def format_abstraction_config(abstraction_config):
    res = "<div class='absconfig'>\n"

    res += "<ul class='absconfig_ul'>\n"

    for k, v in abstraction_config.items():
        if k in ('measurement_db', 'predmanager'):
            continue
        res += "  <li class='absconfig_li'>"
        res += f"{k}:\n"
        res += "    <ul class='absconfig_ul_inner'>\n"
        for ki, vi in v.items():
            if ki.endswith(".doc"):
                continue
            doc = v.get(f'{ki}.doc', None)
            res += "      <li class='absconfig_li_inner'>"
            if ki == 'features':
                entry_str = f"{ki}:\n"
                entry_str += "<ul class='absconfig_ul_inner'>\n"
                for vs in vi:
                    entry_str += "<li class='absconfig_li_inner'>"
                    entry_str += f"{vs[0]}: {json.dumps(vs[1])}"
                    entry_str += "</li>\n"
                entry_str += "</ul>\n"
            else:
                entry_str = f"{ki}: {json.dumps(vi)}"

            if doc is not None:
                entry_str = "<div class='tooltip'>" + entry_str + "<span class='tooltiptext'>" + doc + "</span></div>"

            res += entry_str
            res += "</li>\n"
        res += "    </ul>\n"
        res += "  </li>\n"

    res += "</ul>\n"

    res += "</div>\n"
    return res


def campaign(request, campaign_id):
    campaign_obj = get_object_or_404(Campaign, pk=campaign_id)

    tool_list = campaign_obj.tools.all()

    termination_condition = list(campaign_obj.termination_condition.items())

    total_seconds = campaign_obj.total_seconds

    time_spent = prettify_seconds(total_seconds)

    batches = campaign_obj.discoverybatch_set.all()
    num_discoveries = sum([b.discovery_set.count() for b in batches])

    cfg_str = format_abstraction_config(campaign_obj.config_dict)

    context = {
            'campaign': campaign_obj,
            'tool_list': tool_list,
            'termination_condition': termination_condition,
            'abstraction_config': cfg_str,
            'num_discovery_batches': len(batches),
            'num_discoveries': num_discoveries,
            'time_spent': time_spent,
        }

    return render(request, 'basic_ui/campaign_overview.html', context)

discovery_table_attrs = {"class": "discoverytable"}

class DiscoveryTable(tables.Table):
    identifier = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Discovery ID")
    absblock = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Abstract Block")
    num_insns = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="# Instructions", empty_values=())
    coverage = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Sample Coverage")
    interestingness = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Mean Interestingness")
    witness_len = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Witness Length")

    def render_absblock(self, value):
        # TODO storing the AbstractionContext here is somewhat ugly, but it is
        # a lot faster than recreating it every time.
        actx = getattr(self, '_actx', None)
        res = load_abstract_block(value, actx)
        if actx is None:
            self._actx = res.actx
        return str(res)

    def render_num_insns(self, value, record):
        return len(record.absblock['ab']['abs_insns'])

    def order_num_insns(self, queryset, is_descending):
        queryset = queryset.annotate(
            num_insns=len(F('absblock')['ab']['abs_insns'])
        ).order_by(("-" if is_descending else "") + "num_insns")
        return (queryset, True)

def discoveries(request, campaign_id):
    table = DiscoveryTable(Discovery.objects.filter(batch__campaign_id=campaign_id))

    tables.RequestConfig(request).configure(table)

    return render(request, "basic_ui/data_table.html", {
        "title": "Discoveries",
        "table": table
    })

