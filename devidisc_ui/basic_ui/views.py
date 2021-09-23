import django
from django.core.cache import cache as CACHE
from django.db.models import F, Q, Sum, Avg, Count, Value
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.utils.safestring import mark_safe

from pathlib import Path

import django_tables2 as tables
from markdown import markdown

from devidisc.abstractioncontext import AbstractionContext
from devidisc.configurable import config_diff

from .models import Campaign, Discovery, InsnScheme
from .custom_pretty_printing import prettify_absblock, prettify_seconds, prettify_config_diff, prettify_abstraction_config
from .helpers import load_abstract_block

from .plots import *

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


campaign_table_attrs = {"class": "campaigntable"}

class CampaignTable(tables.Table):
    campaign_id = tables.Column(
            linkify=(lambda value: django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': value})),
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


def all_campaigns_view(request):
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



def single_campaign_view(request, campaign_id):
    campaign_obj = get_object_or_404(Campaign, pk=campaign_id)

    # get the batch-independent information
    tool_list = campaign_obj.tools.all()
    termination_condition = list(campaign_obj.termination_condition.items())
    cfg_str = prettify_abstraction_config(campaign_obj.config_dict)

    all_batches = campaign_obj.discoverybatch_set.all().order_by('batch_index')
    total_batches = all_batches.count()

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

    num_batches = batch_pos

    relevant_discoveries = Discovery.objects.filter(batch__campaign=campaign_obj, batch__batch_index__range=(0, batch_pos-1))
    num_discoveries = relevant_discoveries.count()

    total_seconds = batches.aggregate(Sum('batch_time'))['batch_time__sum']
    time_spent = prettify_seconds(total_seconds)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': campaign_id})),
        ]

    if num_discoveries == 0:
        avg_witness_length = None
        avg_num_insns = None
        avg_generality = None
    else:
        witness_lengths = 0
        num_insns = 0
        agg = relevant_discoveries.aggregate(Avg('witness_len'), Avg('num_insns'), Avg('generality'))
        avg_witness_length = '{:.2f}'.format(agg['witness_len__avg'])
        avg_num_insns = '{:.2f}'.format(agg['num_insns__avg'])
        avg_generality = '{:.2f}'.format(agg['generality__avg'])

    discoveries_per_batch = None if num_batches == 0 else '{:.2f}'.format(num_discoveries / num_batches)

    stats = [
            ('batches run', num_batches),
            ('discoveries made', num_discoveries),
            ('discoveries per batch', discoveries_per_batch),
            ('average generality', avg_generality),
            ('average witness length', avg_witness_length),
            ('average number of instructions', avg_num_insns),
            ('time spent', time_spent),
        ]

    plots = [
            make_discoveries_per_batch_plot(batches),
            make_generality_histogramm_plot(relevant_discoveries),
        ]

    context = {
            'campaign': campaign_obj,
            'tool_list': tool_list,
            'termination_condition': termination_condition,
            'abstraction_config': cfg_str,

            'batch_pos': batch_pos,
            'total_batches': total_batches,

            'stats': stats,
            'plots': plots,
            'topbarpathlist': topbarpathlist,
        }

    context.update(get_docs('single_campaign'))

    return render(request, 'basic_ui/campaign_overview.html', context)

discovery_table_attrs = {"class": "discoverytable"}

class DiscoveryTable(tables.Table):
    identifier = tables.Column(
            linkify=(lambda value, record: django.urls.reverse('basic_ui:single_discovery', kwargs={'campaign_id': record.batch.campaign.id, 'discovery_id': value})),
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
    generality = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Generality")
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

    def render_interestingness(self, value):
        return "{:.2f}".format(value)


def all_discoveries_view(request, campaign_id):
    table = DiscoveryTable(Discovery.objects.filter(batch__campaign_id=campaign_id))

    tables.RequestConfig(request).configure(table)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': campaign_id})),
            ('all discoveries', django.urls.reverse('basic_ui:all_discoveries', kwargs={'campaign_id': campaign_id})),
        ]

    context = {
            "title": "Discoveries",
            "table": table,
            'topbarpathlist': topbarpathlist,
        }
    context.update(get_docs('all_discoveries'))

    return render(request, "basic_ui/data_table.html", context)


def single_discovery_view(request, campaign_id, discovery_id):
    discovery_obj = get_object_or_404(Discovery, batch__campaign_id=campaign_id, identifier=discovery_id)

    absblock = load_abstract_block(discovery_obj.absblock, None)

    absblock_html = prettify_absblock(absblock, add_schemes=True)

    mean_interestingness = discovery_obj.interestingness
    ab_coverage = discovery_obj.ab_coverage
    witness_length = discovery_obj.witness_len

    plot = make_interestingness_histogramm_plot(list(discovery_obj.measurement_set.all()))

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': campaign_id})),
            ('all discoveries', django.urls.reverse('basic_ui:all_discoveries', kwargs={'campaign_id': campaign_id})),
            (f'discovery {discovery_id}', django.urls.reverse('basic_ui:single_discovery', kwargs={'campaign_id': campaign_id, 'discovery_id': discovery_id}))
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


insnscheme_table_attrs = {"class": "insnschemetable"}

class InsnSchemeTable(tables.Table):
    text = tables.Column(
            linkify=(lambda value, record: django.urls.reverse('basic_ui:single_insnscheme', kwargs={'campaign_id': record.campaign_id, 'ischeme_id': record.id})),
            attrs={"td": insnscheme_table_attrs, "th": insnscheme_table_attrs},
            verbose_name="InsnScheme",
        )

    def render_text(self, value):
        shorten_length = 60
        if len(value) > shorten_length:
            return value[:shorten_length] + ' [...]'
        return value

    class Meta:
        row_attrs = insnscheme_table_attrs
        attrs = insnscheme_table_attrs


def all_insnschemes_view(request, campaign_id):
    insnscheme_objs = InsnScheme.objects.filter(discovery__batch__campaign_id=campaign_id).distinct().order_by('text')

    extra_cols = []

    insnscheme_objs = insnscheme_objs.annotate(total_discovery_count=Count('discovery'))

    extra_cols.append( ('total_discovery_count', tables.Column(accessor='total_discovery_count',
        attrs={"td": insnscheme_table_attrs, "th": insnscheme_table_attrs},
        verbose_name='Total Occurrences')) )

    possible_num_insns = list(map(lambda x: x['num_insns'], Discovery.objects.filter(batch__campaign_id=campaign_id).values('num_insns').distinct().order_by('num_insns')))
    for num_insns in possible_num_insns:
        field_name = f"discovery_count_{num_insns}"
        kwargs = {field_name: Count('discovery', filter=Q(discovery__num_insns=num_insns))}
        insnscheme_objs = insnscheme_objs.annotate(**kwargs)
        extra_cols.append( (field_name, tables.Column(accessor=field_name,
        attrs={"td": insnscheme_table_attrs, "th": insnscheme_table_attrs},
        verbose_name=f'L{num_insns}')) )

    insnscheme_objs = insnscheme_objs.annotate(campaign_id=Value(campaign_id))

    table = InsnSchemeTable(insnscheme_objs, extra_columns=extra_cols)

    tables.RequestConfig(request, paginate=False).configure(table)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': campaign_id})),
            ('all InsnSchemes', django.urls.reverse('basic_ui:all_insnschemes', kwargs={'campaign_id': campaign_id})),
        ]

    context = {
            "title": "InsnSchemes",
            "table": table,
            'topbarpathlist': topbarpathlist,
        }
    context.update(get_docs('all_insnschemes'))

    return render(request, "basic_ui/data_table.html", context)


def single_insnscheme_view(request, campaign_id, ischeme_id):
    ischeme_obj = get_object_or_404(InsnScheme, pk=ischeme_id)

    discoveries = ischeme_obj.discovery_set.filter(batch__campaign_id=campaign_id)

    table = DiscoveryTable(discoveries)

    tables.RequestConfig(request).configure(table)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': campaign_id})),
            ('all InsnSchemes', django.urls.reverse('basic_ui:all_insnschemes', kwargs={'campaign_id': campaign_id})),
            (f'InsnScheme \'{ischeme_obj.text}\'', django.urls.reverse('basic_ui:single_insnscheme', kwargs={'campaign_id': campaign_id, 'ischeme_id': ischeme_id})),
        ]

    context = {
            "title": "Discoveries connected to an InsnScheme ",
            "table": table,
            'topbarpathlist': topbarpathlist,
        }
    context.update(get_docs('single_insnscheme'))

    return render(request, "basic_ui/data_table.html", context)



