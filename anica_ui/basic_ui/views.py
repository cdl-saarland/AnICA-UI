import django
from django.core.cache import cache as CACHE
from django.db.models import F, Q, Sum, Avg, Count, Value
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.utils.safestring import mark_safe

from pathlib import Path
import os
import urllib

import django_tables2 as tables
from markdown import markdown

from anica.abstractioncontext import AbstractionContext
from anica.bbset_coverage import make_heatmap
from iwho.configurable import config_diff, pretty_print

from .models import Campaign, Discovery, InsnScheme, Generalization, BasicBlockSet, BasicBlockSetMetrics, BasicBlockEntry
from .custom_pretty_printing import prettify_absblock, prettify_seconds, prettify_config_diff, prettify_abstraction_config, listify
from .witness_site import gen_witness_site, gen_measurement_site, get_witnessing_series_id
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

def url_with_querystring(path, **kwargs):
    return path + '?' + urllib.parse.urlencode(kwargs)

def tool_str_for(campaign_id):
    campaign_obj = get_object_or_404(Campaign, pk=campaign_id)
    tool_list = campaign_obj.tools.all()
    tool_str = " vs. ".join(map(str, tool_list))
    return tool_str

campaign_table_attrs = {"class": "campaigntable"}

def start_view(request):
    context = {
        "title": "Start",
        'topbarpathlist': [],
    }
    context.update(get_docs('start'))
    return render(request, "basic_ui/start.html",  context)

class CampaignTable(tables.Table):
    campaign_id = tables.Column(
            linkify=(lambda value: django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': value})),
            attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="ID")
    tag = tables.Column(
            linkify=(lambda value: url_with_querystring(django.urls.reverse('basic_ui:all_campaigns'), tag=value)),
            attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Tag")
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
        attrs = campaign_table_attrs
        row_attrs = campaign_table_attrs


def all_campaigns_view(request):
    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
        ]

    tag_filter = request.GET.get('tag', None)
    if tag_filter is None:
        campaigns = Campaign.objects.all()
    else:
        campaigns = Campaign.objects.filter(tag=tag_filter)
        topbarpathlist.append((f"with tag '{tag_filter}'", url_with_querystring(django.urls.reverse('basic_ui:all_campaigns'), tag=tag_filter)))

    if len(campaigns) == 0:
        context = {
                "title": "All Campaigns",
                'topbarpathlist': topbarpathlist,
            }
        context.update(get_docs('all_campaigns'))
        return render(request, "basic_ui/all_campaigns_empty.html", context)

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
        num_discoveries = Discovery.objects.filter(batch__campaign=campaign).filter(subsumed_by=None).count()
        tool_list = campaign.tools.all()
        init_interesting_sample_ratio = None
        if num_batches > 0:
            init_batch = campaign.discoverybatch_set.order_by('pk').first()
            if init_batch.num_sampled > 0:
                init_interesting_sample_ratio = init_batch.num_interesting / init_batch.num_sampled

        config_delta_html = prettify_config_diff(delta)

        data.append({
            'campaign_id': campaign.id,
            'tag': campaign.tag,
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

    return render(request, "basic_ui/all_campaigns.html",  context)



def single_campaign_view(request, campaign_id):
    campaign_obj = get_object_or_404(Campaign, pk=campaign_id)

    # get the batch-independent information
    tool_list = campaign_obj.tools.all()
    termination_condition = list(campaign_obj.termination_condition.items())
    cfg_str = prettify_abstraction_config(campaign_obj.config_dict)

    all_batches = campaign_obj.discoverybatch_set.all().order_by('batch_index')
    total_batches = all_batches.count()

    # Check whether we should make this view comparable with a different one
    # (i.e. make sure that all plot axes are the same and we use a common
    # prefix if not explicitly specified otherwise.)
    cmp_campaign_id_str = request.GET.get('compare_with', None)

    cmp_campaign_objs = []
    all_cmp_batches = []

    if cmp_campaign_id_str is not None:
        cmp_campaign_ids = cmp_campaign_id_str.split(',')
        for cmp_campaign_id in cmp_campaign_ids:
            try:
                cmp_campaign_id = int(cmp_campaign_id)
                curr_cmp_campaign_obj = Campaign.objects.get(pk=cmp_campaign_id)
                cmp_campaign_objs.append(curr_cmp_campaign_obj)
            except (ValueError, Campaign.DoesNotExist):
                raise Http404(f"Campaign {cmp_campaign_id} could not be found for comparison.")
            all_cmp_batches.append(curr_cmp_campaign_obj.discoverybatch_set.all().order_by('batch_index'))

    batch_pos_pre = total_batches

    # get the number of batches that we should use for this display
    batch_pos_str = request.GET.get('batch_pos', None)

    if batch_pos_str is None:
        batch_pos_explicitly_set = False
        batch_pos_str = batch_pos_pre
    else:
        batch_pos_explicitly_set = True

    if batch_pos_str == 'min':
        batch_pos = min(batch_pos_pre, *map(lambda x: x.count(), all_cmp_batches))
    else:
        try:
            batch_pos = int(batch_pos_str)
        except ValueError:
            batch_pos = batch_pos_pre

    # make sure that the position is in bounds
    if batch_pos <= 0:
        batch_pos = 1
    if batch_pos > total_batches:
        batch_pos = total_batches

    # restrict to the first batch_pos batches
    batches = all_batches[:batch_pos]

    cmp_batches = []
    cmp_discoveries = []
    for cmp_batch, cmp_campaign_obj in zip(all_cmp_batches, cmp_campaign_objs):
        if batch_pos_explicitly_set:
            cmp_batches.append(cmp_batch[:batch_pos])
            cmp_discoveries.append(Discovery.objects.filter(batch__campaign=cmp_campaign_obj, batch__batch_index__range=(0, batch_pos-1)))
        else:
            cmp_batches.append(cmp_batch)
            cmp_discoveries.append(Discovery.objects.filter(batch__campaign=cmp_campaign_obj))

    num_batches = batch_pos

    relevant_discoveries = Discovery.objects.filter(batch__campaign=campaign_obj, batch__batch_index__range=(0, batch_pos-1))
    num_discoveries = relevant_discoveries.count()

    relevant_discoveries = relevant_discoveries.filter(subsumed_by=None)

    num_discoveries_not_subsumed = relevant_discoveries.count()

    total_seconds = batches.aggregate(Sum('batch_time'))['batch_time__sum']
    time_spent = prettify_seconds(total_seconds)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id} ({tool_str_for(campaign_id)})', django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': campaign_id})),
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
            ('discoveries made', num_discoveries_not_subsumed),
            ('discoveries made (before filtering subsumed ones)', num_discoveries),
            ('discoveries per batch', discoveries_per_batch),
            ('average generality', avg_generality),
            ('average witness length', avg_witness_length),
            ('average number of instructions', avg_num_insns),
            ('time spent', time_spent),
        ]

    plots = [
            make_discoveries_per_batch_plot(batches, cmp_batches),
            make_generality_histogramm_plot(relevant_discoveries, cmp_discoveries),
        ]

    context = {
            'campaign': campaign_obj,
            'tool_list': tool_list,
            'termination_condition': termination_condition,
            'abstraction_config': cfg_str,

            'is_comparing': len(cmp_campaign_objs) > 0,
            'cmp_campaign_ids': ", ".join(map(lambda x: str(x.pk), cmp_campaign_objs)),

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
    show_subsumed = request.GET.get('show_subsumed', '0')
    show_subsumed = (show_subsumed != '0')

    objs = Discovery.objects.filter(batch__campaign_id=campaign_id)
    if not show_subsumed:
        objs = objs.filter(subsumed_by=None)

    table = DiscoveryTable(objs)

    tables.RequestConfig(request).configure(table)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id} ({tool_str_for(campaign_id)})', django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': campaign_id})),
            ('all discoveries', django.urls.reverse('basic_ui:all_discoveries', kwargs={'campaign_id': campaign_id})),
        ]

    context = {
            "title": "All Discoveries",
            "table": table,
            'topbarpathlist': topbarpathlist,
        }
    context.update(get_docs('all_discoveries'))

    return render(request, "basic_ui/data_table.html", context)

def discovery_json_view(request, campaign_id, discovery_id):
    discovery_obj = get_object_or_404(Discovery, batch__campaign_id=campaign_id, identifier=discovery_id)
    json_content = pretty_print(discovery_obj.absblock)
    return HttpResponse(json_content, content_type="text/plain")

def single_discovery_view(request, campaign_id, discovery_id):
    discovery_obj = get_object_or_404(Discovery, batch__campaign_id=campaign_id, identifier=discovery_id)

    absblock = load_abstract_block(discovery_obj.absblock, None)

    absblock_html = prettify_absblock(absblock, add_schemes=True)

    min_absblock_html = prettify_absblock(absblock.minimize(), add_schemes=True)

    mean_interestingness = discovery_obj.interestingness
    witness_length = discovery_obj.witness_len
    generality = discovery_obj.generality
    subsumed_by = discovery_obj.subsumed_by

    remark_text = discovery_obj.remarks
    if remark_text is None:
        remark_text = "No remarks."

    stats = [
            ('geomean interestingness', mean_interestingness),
            ('generality', generality),
            ('witness length', witness_length),
        ]

    if subsumed_by is not None:
        stats.append(('subsumed by', subsumed_by))

    plots = [
            make_interestingness_histogramm_plot(list(discovery_obj.measurement_set.all())),
        ]


    example_series_id = -1
    path = discovery_obj.batch.campaign.witness_path + f'/{discovery_id}.json'
    if os.path.isfile(path):
        example_series_id = get_witnessing_series_id(path)

    input_id = discovery_obj.identifier.rsplit('_', 1)[0]
    related_generalizations = Discovery.objects.filter(batch__campaign_id=campaign_id, identifier__startswith=input_id).exclude(identifier=discovery_obj.identifier)
    table = DiscoveryTable(related_generalizations)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id} ({tool_str_for(campaign_id)})', django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': campaign_id})),
            ('all discoveries', django.urls.reverse('basic_ui:all_discoveries', kwargs={'campaign_id': campaign_id})),
            (f'discovery {discovery_id}', django.urls.reverse('basic_ui:single_discovery', kwargs={'campaign_id': campaign_id, 'discovery_id': discovery_id}))
        ]

    context = {
            'campaign_id': campaign_id,
            'discovery_id': discovery_id,
            'absblock': absblock_html,
            'min_absblock': min_absblock_html,
            'topbarpathlist': topbarpathlist,
            'example_series_id': example_series_id,
            'table': table,

            'stats': stats,
            'plots': plots,
            'remark_text': remark_text,
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
    show_subsumed = request.GET.get('show_subsumed', '0')
    show_subsumed = (show_subsumed != '0')

    if show_subsumed:
        insnscheme_objs = InsnScheme.objects.filter(discovery__batch__campaign_id=campaign_id).distinct().order_by('text')
    else:
        insnscheme_objs = InsnScheme.objects.filter(discovery__batch__campaign_id=campaign_id, discovery__subsumed_by=None).distinct().order_by('text')

    extra_cols = []

    insnscheme_objs = insnscheme_objs.annotate(total_discovery_count=Count('discovery'))

    extra_cols.append( ('total_discovery_count', tables.Column(accessor='total_discovery_count',
        attrs={"td": insnscheme_table_attrs, "th": insnscheme_table_attrs},
        verbose_name='Total Occurrences')) )

    possible_num_insns = list(map(lambda x: x['num_insns'], Discovery.objects.filter(batch__campaign_id=campaign_id).values('num_insns').distinct().order_by('num_insns')))
    for num_insns in possible_num_insns:
        field_name = f"discovery_count_{num_insns}"
        if show_subsumed:
            kwargs = {field_name: Count('discovery', filter=Q(discovery__num_insns=num_insns))}
        else:
            kwargs = {field_name: Count('discovery', filter=Q(discovery__num_insns=num_insns, discovery__subsumed_by=None))}
        insnscheme_objs = insnscheme_objs.annotate(**kwargs)
        extra_cols.append( (field_name, tables.Column(accessor=field_name,
        attrs={"td": insnscheme_table_attrs, "th": insnscheme_table_attrs},
        verbose_name=f'L{num_insns}')) )

    insnscheme_objs = insnscheme_objs.annotate(campaign_id=Value(campaign_id))

    table = InsnSchemeTable(insnscheme_objs, extra_columns=extra_cols)

    tables.RequestConfig(request, paginate=False).configure(table)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id} ({tool_str_for(campaign_id)})', django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': campaign_id})),
            ('all InsnSchemes', django.urls.reverse('basic_ui:all_insnschemes', kwargs={'campaign_id': campaign_id})),
        ]

    context = {
            "title": "All InsnSchemes",
            "table": table,
            'topbarpathlist': topbarpathlist,
        }
    context.update(get_docs('all_insnschemes'))

    return render(request, "basic_ui/data_table.html", context)


def single_insnscheme_view(request, campaign_id, ischeme_id):
    show_subsumed = request.GET.get('show_subsumed', '0')
    show_subsumed = (show_subsumed != '0')

    ischeme_obj = get_object_or_404(InsnScheme, pk=ischeme_id)

    if show_subsumed:
        discoveries = ischeme_obj.discovery_set.filter(batch__campaign_id=campaign_id)
    else:
        discoveries = ischeme_obj.discovery_set.filter(batch__campaign_id=campaign_id, subsumed_by=None)

    table = DiscoveryTable(discoveries)

    tables.RequestConfig(request).configure(table)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id} ({tool_str_for(campaign_id)})', django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': campaign_id})),
            ('all InsnSchemes', django.urls.reverse('basic_ui:all_insnschemes', kwargs={'campaign_id': campaign_id})),
            (f'InsnScheme \'{ischeme_obj.text}\'', django.urls.reverse('basic_ui:single_insnscheme', kwargs={'campaign_id': campaign_id, 'ischeme_id': ischeme_id})),
        ]

    context = {
            "title": "Single InsnScheme",
            "table": table,
            'topbarpathlist': topbarpathlist,
        }
    context.update(get_docs('single_insnscheme'))

    return render(request, "basic_ui/data_table.html", context)

gen_table_attrs = {"class": "discoverytable"}

class GeneralizationTable(tables.Table):
    generalization_id = tables.Column(
            linkify=(lambda value: django.urls.reverse('basic_ui:single_generalization', kwargs={'generalization_id': value})),
            attrs={"td": gen_table_attrs, "th": gen_table_attrs},
            verbose_name="ID")
    identifier = tables.Column(
            attrs={"td": gen_table_attrs, "th": gen_table_attrs},
            verbose_name="Name")
    tools = tables.Column(attrs={"td": gen_table_attrs, "th": gen_table_attrs},
            verbose_name="Tools under Investigation")
    absblock = tables.Column(
            attrs={"td": gen_table_attrs, "th": gen_table_attrs},
            verbose_name="Abstract Block")
    num_insns = tables.Column(
            attrs={"td": gen_table_attrs, "th": gen_table_attrs},
            verbose_name="# Instructions", empty_values=())
    # interestingness = tables.Column(
    #         attrs={"td": gen_table_attrs, "th": gen_table_attrs},
    #         verbose_name="Mean Interestingness")
    generality = tables.Column(
            attrs={"td": gen_table_attrs, "th": gen_table_attrs},
            verbose_name="Generality")
    witness_len = tables.Column(
            attrs={"td": gen_table_attrs, "th": gen_table_attrs},
            verbose_name="Witness Length")

    def render_absblock(self, value):
        # We cannot use the hack of storing the actx here, since
        # generalizations may have entirely different configs!
        res = load_abstract_block(value, None)
        return prettify_absblock(res, skip_top=True)

    def render_interestingness(self, value):
        return "{:.2f}".format(value)

    class Meta:
        attrs = gen_table_attrs
        row_attrs = gen_table_attrs


def all_generalizations_view(request):
    topbarpathlist = [
            ('individual generalizations', django.urls.reverse('basic_ui:all_generalizations')),
        ]

    generalizations = Generalization.objects.all()

    if len(generalizations) == 0:
        context = {
                "title": "Individual Generalizations",
                'topbarpathlist': topbarpathlist,
            }
        context.update(get_docs('all_generalizations'))
        return render(request, "basic_ui/all_generalizations_empty.html", context)

    assert len(generalizations) > 0

    data = []
    for generalization in generalizations:
        tool_list = generalization.tools.all()

        data.append({
            'generalization_id': generalization.id,
            'tools': ", ".join(map(str, tool_list)),
            'absblock': generalization.absblock,
            # 'interestingness': generalization.interestingness,
            'generality': generalization.generality,
            'witness_len': generalization.witness_len,
            'num_insns': generalization.num_insns,
            'identifier': generalization.identifier,
        })

    table = GeneralizationTable(data)

    tables.RequestConfig(request).configure(table)

    context = {
        "title": "All Generalizations",
        "table": table,
        'topbarpathlist': topbarpathlist,
    }

    context.update(get_docs('all_generalizations'))

    return render(request, "basic_ui/all_generalizations.html",  context)

def generalization_json_view(request, generalization_id):
    gen_obj = get_object_or_404(Generalization, id=generalization_id)
    json_content = pretty_print(gen_obj.absblock)
    return HttpResponse(json_content, content_type="text/plain")

def single_generalization_view(request, generalization_id):
    gen_obj = get_object_or_404(Generalization, id=generalization_id)

    absblock = load_abstract_block(gen_obj.absblock, None)

    absblock_html = prettify_absblock(absblock, add_schemes=True)

    cfg_str = prettify_abstraction_config(absblock.actx.get_config())

    min_absblock_html = prettify_absblock(absblock.minimize(), add_schemes=True)

    # mean_interestingness = gen_obj.interestingness
    witness_length = gen_obj.witness_len
    generality = gen_obj.generality

    remark_text = gen_obj.remarks
    if remark_text is None:
        remark_text = "No remarks."

    stats = [
            # ('geomean interestingness', mean_interestingness),
            ('generality', generality),
            ('witness length', witness_length),
        ]

    plots = [
        ]

    example_series_id = -1
    path = gen_obj.witness_file
    if os.path.isfile(path):
        example_series_id = get_witnessing_series_id(path)

    gen_key = generalization_id
    if gen_obj.identifier is not None:
        gen_key = "'{}'".format(gen_obj.identifier)

    topbarpathlist = [
            ('individual generalizations', django.urls.reverse('basic_ui:all_generalizations')),
            (f'generalization {gen_key}', django.urls.reverse('basic_ui:single_generalization', kwargs={'generalization_id': generalization_id}))
        ]

    context = {
            'generalization_id': generalization_id,
            'absblock': absblock_html,
            'min_absblock': min_absblock_html,
            'topbarpathlist': topbarpathlist,
            'example_series_id': example_series_id,
            'abstraction_config': cfg_str,

            'stats': stats,
            'plots': plots,
            'remark_text': remark_text,
        }
    context.update(get_docs('single_generalization'))

    return render(request, 'basic_ui/single_generalization_view.html', context)

def gen_measurements_view(request, generalization_id, meas_id):
    gen_obj = get_object_or_404(Generalization, pk=generalization_id)

    config = gen_obj.absblock.get('config', {})
    config['predmanager'] = None
    actx = AbstractionContext(config)

    context = gen_measurement_site(actx, meas_id)

    if context is None:
        raise Http404(f"Measurements could not be found.")

    return render(request, 'basic_ui/measurements.html', context)

def gen_witness_view(request, generalization_id):
    gen_obj = get_object_or_404(Generalization, pk=generalization_id)

    # We don't add the witness data into the django database but rather just
    # refer to the original location. This is probably a bad design, but
    # simplifies things in the project import. It probably also causes security
    # risks.
    path = gen_obj.witness_file

    if not os.path.isfile(path):
        raise Http404(f"Witness trace could not be found.")


    def mk_meas_link(meas_id):
        return django.urls.reverse('basic_ui:gen_measurements', kwargs={'generalization_id': generalization_id, 'meas_id': meas_id})

    witness_site = gen_witness_site(path, mk_meas_link)

    gen_key = generalization_id
    if gen_obj.identifier is not None:
        gen_key = "'{}'".format(gen_obj.identifier)

    topbarpathlist = [
            ('individual generalizations', django.urls.reverse('basic_ui:all_generalizations')),
            (f'generalization {gen_key}', django.urls.reverse('basic_ui:single_generalization', kwargs={'generalization_id': generalization_id})),
            (f'witness', django.urls.reverse('basic_ui:gen_witness', kwargs={'generalization_id': generalization_id})),
        ]

    context = {
            'topbarpathlist': topbarpathlist,
        }
    context.update(witness_site)
    context.update(get_docs('witness'))

    return render(request, 'basic_ui/witness.html', context)

def gen_measurements_overview_view(request, generalization_id, meas_id):
    gen_obj = get_object_or_404(Generalization, pk=generalization_id)

    config = gen_obj.absblock.get('config', {})
    config['predmanager'] = None
    actx = AbstractionContext(config)

    context = gen_measurement_site(actx, meas_id, 3)

    if context is None:
        raise Http404(f"Measurements could not be found.")

    return render(request, 'basic_ui/measurements.html', context)


def witness_view(request, campaign_id, discovery_id):
    discovery_obj = get_object_or_404(Discovery, batch__campaign_id=campaign_id, identifier=discovery_id)

    # We don't add the witness data into the django database but rather just
    # refer to the original location. This is probably a bad design, but
    # simplifies things in the project import. It probably also causes security
    # risks.
    path = discovery_obj.batch.campaign.witness_path + f'/{discovery_id}.json'

    if not os.path.isfile(path):
        raise Http404(f"Witness trace could not be found.")

    def mk_meas_link(meas_id):
        return django.urls.reverse('basic_ui:measurements', kwargs={'campaign_id': campaign_id, 'meas_id': meas_id})

    witness_site = gen_witness_site(path, mk_meas_link)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id} ({tool_str_for(campaign_id)})', django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': campaign_id})),
            ('all discoveries', django.urls.reverse('basic_ui:all_discoveries', kwargs={'campaign_id': campaign_id})),
            (f'discovery {discovery_id}', django.urls.reverse('basic_ui:single_discovery', kwargs={'campaign_id': campaign_id, 'discovery_id': discovery_id})),
            (f'witness', django.urls.reverse('basic_ui:witness', kwargs={'campaign_id': campaign_id, 'discovery_id': discovery_id})),
        ]

    context = {
            'topbarpathlist': topbarpathlist,
        }
    context.update(witness_site)
    context.update(get_docs('witness'))

    return render(request, 'basic_ui/witness.html', context)


def measurements_empty_view(request):
    return render(request, 'basic_ui/measurements_empty.html')


def measurements_view(request, campaign_id, meas_id):
    campaign_obj = get_object_or_404(Campaign, pk=campaign_id)


    config = campaign_obj.config_dict
    config['predmanager'] = None
    actx = AbstractionContext(config)

    context = gen_measurement_site(actx, meas_id)

    if context is None:
        raise Http404(f"Measurements could not be found.")

    return render(request, 'basic_ui/measurements.html', context)


def measurements_overview_view(request, campaign_id, meas_id):
    campaign_obj = get_object_or_404(Campaign, pk=campaign_id)


    config = campaign_obj.config_dict
    config['predmanager'] = None
    actx = AbstractionContext(config)

    context = gen_measurement_site(actx, meas_id, 3)

    if context is None:
        raise Http404(f"Measurements could not be found.")

    return render(request, 'basic_ui/measurements.html', context)


class AllBBSetTable(tables.Table):
    bbset_id = tables.Column(
            linkify=(lambda value: django.urls.reverse('basic_ui:single_bbset', kwargs={'bbset_id': value})),
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="BBSet ID")
    identifier = tables.Column(
            linkify=(lambda record: django.urls.reverse('basic_ui:single_bbset', kwargs={'bbset_id': record['bbset_id']})),
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Basic Block Set")
    tools = tables.Column(attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Measured Tools", orderable=False)
    num_bbs = tables.Column(attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="# BBs")

    class Meta:
        attrs = discovery_table_attrs
        row_attrs = discovery_table_attrs


def all_bbsets_view(request):

    bbsets = BasicBlockSet.objects.all()

    data = []
    for bbset in bbsets:
        tool_str = listify(bbset.has_data_for.all())
        data.append({
            'bbset_id': bbset.id,
            'identifier': bbset.identifier,
            'tools': tool_str,
            'num_bbs': bbset.basicblockentry_set.count(),
        })

    table = AllBBSetTable(data)
    tables.RequestConfig(request).configure(table)

    topbarpathlist = [
            ('basic block sets', django.urls.reverse('basic_ui:all_bbsets')),
        ]

    context = {
            "title": "All Basic Block Sets",
            'topbarpathlist': topbarpathlist,
            'table': table,
        }

    context.update(get_docs('all_bbsets'))

    return render(request, 'basic_ui/data_table.html', context)


class SingleBBSetTable(tables.Table):
    campaign_id = tables.Column(
            linkify=(lambda value: django.urls.reverse('basic_ui:single_campaign', kwargs={'campaign_id': value})),
            attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Campaign")
    tag = tables.Column(
            linkify=(lambda value, record: url_with_querystring(django.urls.reverse('basic_ui:single_bbset', kwargs={'bbset_id': record['bbset_id']}), tag=value)),
            attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Campaign Tag")
    tools = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Tools under Investigation")
    num_discoveries = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="# Discoveries")
    time_spent = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Run-Time")

    bbset_size = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs}, visible=False)
    bbset_id = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs}, visible=False)

    num_interesting = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="# BBs interesting")
    num_interesting_covered = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            visible=False)
    percent_interesting_covered = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="int. BBs covered")

    num_interesting_covered_top10 = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            visible=False)
    percent_interesting_covered_top10 = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="int. BBs covered by top 10")

    def render_time_spent(self, value):
        return prettify_seconds(value)

    def render_num_interesting(self, value, record):
        return "{} ({:.2f}%)".format(value, 100 * float(value) / float(record['bbset_size']))

    def render_percent_interesting_covered(self, value, record):
        return "{:.2f}% ({})".format(value, record['num_interesting_covered'])

    def render_percent_interesting_covered_top10(self, value, record):
        return "{:.2f}% ({})".format(value, record['num_interesting_covered_top10'])

    class Meta:
        attrs = campaign_table_attrs
        row_attrs = campaign_table_attrs

def single_bbset_view(request, bbset_id):

    bbset_obj = get_object_or_404(BasicBlockSet, pk=bbset_id)

    topbarpathlist = [
            ('basic block sets', django.urls.reverse('basic_ui:all_bbsets')),
            (f'{bbset_obj.identifier}', django.urls.reverse('basic_ui:single_bbset', kwargs={'bbset_id': bbset_id})),
        ]

    tag_filter = request.GET.get('tag', None)
    if tag_filter is None:
        campaigns = Campaign.objects.all()
    else:
        campaigns = Campaign.objects.filter(tag=tag_filter)
        topbarpathlist.append((f"campaigns with tag '{tag_filter}'", url_with_querystring(django.urls.reverse('basic_ui:single_bbset', kwargs={'bbset_id': bbset_id}), tag=tag_filter)))

    data = []
    bbset_size = bbset_obj.basicblockentry_set.count()

    for cobj in campaigns:
        relevant_discoveries = Discovery.objects.filter(batch__campaign=cobj).filter(subsumed_by=None)
        num_discoveries = relevant_discoveries.count()

        try:
            metrics = BasicBlockSetMetrics.objects.get(bbset=bbset_obj, campaign=cobj)

            num_interesting = metrics.num_bbs_interesting
            num_interesting_covered = metrics.num_interesting_bbs_covered
            percent_interesting_covered = metrics.percent_interesting_bbs_covered
            num_interesting_covered_top10 = metrics.num_interesting_bbs_covered_top10
            percent_interesting_covered_top10 = metrics.percent_interesting_bbs_covered_top10

            data.append({
                    'campaign_id': cobj.id,
                    'tag': cobj.tag,
                    'tools': tool_str_for(cobj.id),
                    'num_discoveries': num_discoveries,
                    'time_spent': cobj.total_seconds,
                    'bbset_size': bbset_size,
                    'bbset_id': bbset_id,
                    'num_interesting': num_interesting,
                    'num_interesting_covered': num_interesting_covered,
                    'percent_interesting_covered': percent_interesting_covered,
                    'num_interesting_covered_top10': num_interesting_covered_top10,
                    'percent_interesting_covered_top10': percent_interesting_covered_top10,
                })
        except BasicBlockSetMetrics.DoesNotExist:
            pass

    table = SingleBBSetTable(data)
    tables.RequestConfig(request, paginate=False).configure(table)


    tool_keys = [ str(t) for t in bbset_obj.has_data_for.all()]

    plot_data = []
    for entry in bbset_obj.basicblockentry_set.all():
        d = {'bb': entry.hex_str, **entry.measurement_results}
        plot_data.append(d)

    threshold = 0.5

    heatmap = encode_plot(make_heatmap(tool_keys, plot_data, threshold))

    context = {
            "title": "Single Basic Block Set",
            'bbset_name': bbset_obj.identifier,
            'bbset_id': bbset_id,
            'topbarpathlist': topbarpathlist,
            'plot': heatmap,
            'table': table,
        }

    context.update(get_docs('single_bbset'))

    return render(request, 'basic_ui/single_bbset.html', context)



class EntireBBSetTable(tables.Table):
    hex_str = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Basic Block (HEX)")
    asm_str = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Basic Block (ASM)", orderable=False)
    measurement_results = tables.Column(
            attrs={"td": discovery_table_attrs, "th": discovery_table_attrs},
            verbose_name="Predictor Results", orderable=False)

    def render_measurement_results(self, value):
        lines = []
        for tool, res in value.items():
            lines.append("  {}: {:.2f}".format(tool, res))
        lines.sort()
        return listify(lines)

    def render_asm_str(self, value):
        return mark_safe("<pre class=\"asmblock\">" + escape(value) + "</pre>")

    def render_hex_str(self, value):
        return mark_safe("<pre class=\"hexblock\">" + escape(value) + "</pre>")

    class Meta:
        attrs = discovery_table_attrs
        row_attrs = discovery_table_attrs


def single_bbset_allbbs_view(request, bbset_id):
    bbset_obj = get_object_or_404(BasicBlockSet, pk=bbset_id)

    topbarpathlist = [
            ('basic block sets', django.urls.reverse('basic_ui:all_bbsets')),
            (f'{bbset_obj.identifier}', django.urls.reverse('basic_ui:single_bbset', kwargs={'bbset_id': bbset_id})),
            ('all basic blocks', django.urls.reverse('basic_ui:single_bbset_allbbs', kwargs={'bbset_id': bbset_id}) )
        ]

    table = EntireBBSetTable(bbset_obj.basicblockentry_set.all())
    tables.RequestConfig(request).configure(table)

    context = {
            "title": "All Basic Blocks",
            'topbarpathlist': topbarpathlist,
            'table': table
        }

    context.update(get_docs('entire_bbset'))
    return render(request, "basic_ui/data_table.html", context)

