import django
from django.core.cache import cache as CACHE
from django.db.models import F
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.utils.safestring import mark_safe

from pathlib import Path

import django_tables2 as tables
from markdown import markdown

from devidisc.abstractblock import AbstractBlock
from devidisc.abstractioncontext import AbstractionContext
from devidisc.configurable import config_diff

from .models import Campaign, Discovery
from .custom_pretty_printing import prettify_absblock, prettify_seconds, prettify_config_diff, prettify_abstraction_config

from .plots import make_discoveries_per_batch_plot, make_interestingness_histogramm_plot

def get_docs(site_name):
    # cached = CACHE.get(site_name, None)
    # if cached is not None:
    #     return cached

    base = Path(django.apps.apps.get_app_config('basic_ui').path)
    doc_file = base / 'inline_docs' / (site_name + '.md' )
    assert doc_file.is_file()

    with open(doc_file, 'r') as f:
        lines = f.readlines()
    title_line = lines[0]
    assert title_line[0] == '#'
    title = title_line[1:]
    body = "".join(lines[1:])

    body_html = mark_safe(markdown(body))

    res = { 'helptitle': title, 'helpcontent': body_html }

    # CACHE.set(site_name, res)

    return res


def load_abstract_block(json_dict, actx):
    if actx is None:
        config_dict = json_dict['config']
        config_dict['predmanager'] = None # we don't need that one here
        actx = AbstractionContext(config=config_dict)

    # result_ref = json_dict['result_ref']

    ab_dict = actx.json_ref_manager.resolve_json_references(json_dict['ab'])

    ab = AbstractBlock.from_json_dict(actx, ab_dict)
    return ab#, result_ref


campaign_table_attrs = {"class": "campaigntable"}

class CampaignTable(tables.Table):
    campaign_id = tables.Column(
            linkify=(lambda value: django.urls.reverse('basic_ui:campaign', kwargs={'campaign_id': value})),
            attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Campaign ID")
    date = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Start Date")
    host_pc = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Host PC", visible=False)
    tools = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Tools under Investigation")
    config_delta = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Config Delta")
    num_batches = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="# Batches")
    num_discoveries = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="# Discoveries")
    init_interesting_sample_ratio = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="IISR")
    time_spent = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Run-Time")

    def render_time_spent(self, value):
        return prettify_seconds(value)

    class Meta:
        row_attrs = campaign_table_attrs


def all_campaigns(request):
    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
        ]

    campaigns = Campaign.objects.all()

    if len(campaigns) == 0:
        return render(request, "basic_ui/all_campaigns_empty.html", {
            "title": "All Campaigns",
            'topbarpathlist': topbarpathlist,
        })

    assert len(campaigns) > 0

    base_config = AbstractionContext.get_default_config()
    config_deltas = []
    for campaign in campaigns:
        config_deltas.append(config_diff(base_config, campaign.config_dict))

    common_diffs = []
    for diff in config_deltas[0]:
        if all(map(lambda x: diff in x, config_deltas)):
            common_diffs.append(diff)

    for d in common_diffs:
        for delta in config_deltas:
            delta.remove(d)

    data = []
    for campaign, delta in zip(campaigns, config_deltas):
        num_batches = campaign.discoverybatch_set.count()
        num_discoveries = Discovery.objects.filter(batch__campaign=campaign).count()
        tool_list = campaign.tools.all()
        init_interesting_sample_ratio = None
        if num_batches > 0:
            init_batch = campaign.discoverybatch_set.order_by('pk').first()
            if init_batch.num_sampled > 0:
                init_interesting_sample_ratio = init_batch.num_interesting / init_batch.num_sampled

        config_delta_html = prettify_config_diff(delta)

        data.append({
            'campaign_id': campaign.id,
            'tools': ", ".join(map(str, tool_list)),
            'config_delta': config_delta_html,
            'date': campaign.date,
            'host_pc': campaign.host_pc,
            'num_batches': num_batches,
            'num_discoveries': num_discoveries,
            'init_interesting_sample_ratio': init_interesting_sample_ratio,
            'time_spent': campaign.total_seconds,
            })

    table = CampaignTable(data)

    tables.RequestConfig(request).configure(table)


    context = {
        "title": "All Campaigns",
        "table": table,
        'topbarpathlist': topbarpathlist,
    }

    context.update(get_docs('all_campaigns'))

    return render(request, "basic_ui/data_table.html",  context)



def campaign(request, campaign_id):
    campaign_obj = get_object_or_404(Campaign, pk=campaign_id)

    # get the batch-independent information
    tool_list = campaign_obj.tools.all()
    termination_condition = list(campaign_obj.termination_condition.items())
    cfg_str = prettify_abstraction_config(campaign_obj.config_dict)

    all_batches = list(campaign_obj.discoverybatch_set.all().order_by('pk'))
    total_batches = len(all_batches)

    # get the number of batches that we should use for this display
    batch_pos_str = request.GET.get('batch_pos', total_batches)

    try:
        batch_pos = int(batch_pos_str)
    except ValueError:
        batch_pos = total_batches

    # make sure that the position is in bounds
    if batch_pos <= 0:
        batch_pos = 1
    if batch_pos > total_batches:
        batch_pos = total_batches

    # restrict to the first batch_pos batches
    batches = all_batches[:batch_pos]

    num_batches = len(batches)

    num_discoveries = sum([b.discovery_set.count() for b in batches])

    total_seconds = sum([b.batch_time for b in batches])
    time_spent = prettify_seconds(total_seconds)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:campaign', kwargs={'campaign_id': campaign_id})),
        ]

    # create plots
    discoveries_per_batch_plot = make_discoveries_per_batch_plot(batches)

    if num_discoveries == 0:
        avg_witness_length = None
        avg_num_insns = None
    else:
        witness_lengths = 0
        num_insns = 0
        for b in batches:
            for discovery in b.discovery_set.all():
                witness_lengths += discovery.witness_len
                num_insns += discovery.num_insns
        avg_witness_length = witness_lengths / num_discoveries
        avg_witness_length = '{:.2f}'.format(avg_witness_length)

        avg_num_insns = num_insns / num_discoveries
        avg_num_insns = '{:.2f}'.format(avg_num_insns)

    discoveries_per_batch = None if num_batches == 0 else '{:.2f}'.format(num_discoveries / num_batches)

    stats = [
            ('batches run', num_batches),
            ('discoveries made', num_discoveries),
            ('discoveries per batch', discoveries_per_batch),
            ('avg witness length', avg_witness_length),
            ('avg number of instructions', avg_num_insns),
            ('time spent', time_spent),
        ]

    context = {
            'campaign': campaign_obj,
            'tool_list': tool_list,
            'termination_condition': termination_condition,
            'abstraction_config': cfg_str,

            'batch_pos': batch_pos,
            'total_batches': total_batches,

            'stats': stats,
            'discoveries_per_batch_plot': discoveries_per_batch_plot,
            'topbarpathlist': topbarpathlist,
        }

    context.update(get_docs('single_campaign'))

    return render(request, 'basic_ui/campaign_overview.html', context)

discovery_table_attrs = {"class": "discoverytable"}

class DiscoveryTable(tables.Table):
    identifier = tables.Column(
            linkify=(lambda value, record: django.urls.reverse('basic_ui:discovery', kwargs={'campaign_id': record.batch.campaign.id, 'discovery_id': value})),
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Discovery ID",
            )
    absblock = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Abstract Block")
    num_insns = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="# Instructions", empty_values=())
    ab_coverage = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Sample Coverage")
    interestingness = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Mean Interestingness")
    witness_len = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Witness Length")

    class Meta:
        row_attrs = discovery_table_attrs
        attrs = discovery_table_attrs

    def render_absblock(self, value):
        # TODO storing the AbstractionContext here is somewhat ugly, but it is
        # a lot faster than recreating it every time.
        actx = getattr(self, '_actx', None)
        res = load_abstract_block(value, actx)
        if actx is None:
            self._actx = res.actx
        return prettify_absblock(res, skip_top=True)


def all_discoveries(request, campaign_id):
    table = DiscoveryTable(Discovery.objects.filter(batch__campaign_id=campaign_id))

    tables.RequestConfig(request).configure(table)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:campaign', kwargs={'campaign_id': campaign_id})),
            ('all discoveries', django.urls.reverse('basic_ui:all_discoveries', kwargs={'campaign_id': campaign_id})),
        ]

    context = {
            "title": "Discoveries",
            "table": table,
            'topbarpathlist': topbarpathlist,
        }
    context.update(get_docs('all_discoveries'))

    return render(request, "basic_ui/data_table.html", context)


def discovery(request, campaign_id, discovery_id):
    discovery_obj = get_object_or_404(Discovery, batch__campaign_id=campaign_id, identifier=discovery_id)

    absblock = load_abstract_block(discovery_obj.absblock, None)

    absblock_html = prettify_absblock(absblock, add_schemes=True)

    mean_interestingness = discovery_obj.interestingness
    ab_coverage = discovery_obj.ab_coverage
    witness_length = discovery_obj.witness_len

    plot = make_interestingness_histogramm_plot(list(discovery_obj.measurement_set.all()))

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:campaign', kwargs={'campaign_id': campaign_id})),
            ('all discoveries', django.urls.reverse('basic_ui:all_discoveries', kwargs={'campaign_id': campaign_id})),
            (f'discovery {discovery_id}', django.urls.reverse('basic_ui:discovery', kwargs={'campaign_id': campaign_id, 'discovery_id': discovery_id}))
        ]

    context = {
            'absblock': absblock_html,
            'topbarpathlist': topbarpathlist,
            'mean_interestingness': mean_interestingness,
            'ab_coverage': ab_coverage,
            'witness_length': witness_length,
            'interestingness_histogram': plot,
        }
    context.update(get_docs('single_discovery'))

    return render(request, 'basic_ui/discovery_overview.html', context)
