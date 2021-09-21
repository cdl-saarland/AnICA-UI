from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
import django

from django.utils.safestring import mark_safe
from django.utils.html import escape

from django.db.models import F

from django.core.cache import cache as CACHE

from collections import defaultdict
import json
import math
from pathlib import Path

from devidisc.abstractblock import AbstractBlock
from devidisc.abstractioncontext import AbstractionContext
from devidisc.configurable import config_diff
# Create your views here.

from .models import Campaign, Discovery

import django_tables2 as tables

from markdown import markdown

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import io, base64


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


def encode_plot(fig):
    flike = io.BytesIO()
    fig.savefig(flike)
    b64 = base64.b64encode(flike.getvalue()).decode()
    return b64

def make_discoveries_per_batch_plot(batches):
    ordered = batches.order_by('pk')

    objs = ordered.all()

    batch_idx = list(range(0, len(objs)))
    counts = [x.discovery_set.count() for x in objs]

    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(batch_idx, counts, '--bo')

    ax.set_title('Discoveries per Batch')
    ax.set_ylabel("# Discoveries")
    ax.set_xlabel("Batch Index")
    ax.grid(linestyle="--", linewidth=0.5, color='.25', zorder=-10)

    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    return encode_plot(fig)

def make_interestingness_histogramm_plot(measurements):
    interestingnesses = [ m.interestingness for m in measurements ]

    finite_entries = [i for i in interestingnesses if math.isfinite(i)]
    if len(finite_entries) == 0:
        return None
    max_finite = max(finite_entries)
    inf_val = abs(max_finite) * 1.5

    entries = [i if math.isfinite(i) else inf_val for i in interestingnesses]

    fig, ax = plt.subplots(figsize=(10,4))
    ax.hist(entries)

    ax.set_title('Interestingness of Samples')
    ax.set_ylabel("# Occurrences")
    ax.set_xlabel("Interestingness")
    ax.grid(linestyle="--", linewidth=0.5, color='.25', zorder=-10)

    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    return encode_plot(fig)


def load_abstract_block(json_dict, actx):
    if actx is None:
        config_dict = json_dict['config']
        config_dict['predmanager'] = None # we don't need that one here
        actx = AbstractionContext(config=config_dict)

    # result_ref = json_dict['result_ref']

    ab_dict = actx.json_ref_manager.resolve_json_references(json_dict['ab'])

    ab = AbstractBlock.from_json_dict(actx, ab_dict)
    return ab#, result_ref


def prettify_absinsn(absinsn, hl_feature=None, skip_top=False):
    if absinsn.is_top():
        res = "TOP"
        if hl_feature is not None:
            res = '<div class="highlightedcomponent">' + res + '</div>'
    else:
        list_entries = []
        for k, v in absinsn.features.items():
            if skip_top and v.is_top():
                continue
            entry = f"{k}: {v}"
            if hl_feature is not None and hl_feature[0] == k:
                entry = '<div class="highlightedcomponent">' + entry + "</div>"
            entry = "<li>" + entry + "</li>"
            list_entries.append(entry)
        res = "\n".join(list_entries)
        res = '<ul class="absfeaturelist">' + res + "</ul>"
    return res


def prettify_absblock(absblock, hl_expansion=None, skip_top=False, add_schemes=False):
    res = ""
    res += "<b>Abstract Instructions:</b>\n"
    res += "<table class=\"absinsn\">\n"
    for idx, ai in enumerate(absblock.abs_insns):
        res += "<tr class=\"absinsn\">"
        res += f"<th class=\"absinsn\">{idx}</th>\n"
        hl_feature = None
        if hl_expansion is not None and hl_expansion[0] == 0 and hl_expansion[1] == idx:
            hl_feature = hl_expansion[2]

        insn_str = prettify_absinsn(ai, hl_feature, skip_top=skip_top)
        res += f"<td class=\"absinsn\">{insn_str}</td>"

        feasible_schemes = absblock.actx.insn_feature_manager.compute_feasible_schemes(ai.features)
        if not add_schemes:
            num_schemes = len(feasible_schemes)
            res += f"<td class=\"absinsn\">({num_schemes})</td>"

        res += "\n</tr>\n"

        if add_schemes:
            content_id = "expl_schemes_{}".format(idx) # TODO add a unique identifier before the idx
            res += "<tr class=\"absinsn\"><td class=\"absinsn\"></td><td class=\"absinsn\">"
            res += "<div class=\"absinsn indent_content\">"
            res += "Respresented Schemes: {} <button onclick=\"(function(){{let el = document.getElementById('{content_id}'); if (el.style.visibility === 'visible') {{el.style.visibility = 'collapse'; }} else {{el.style.visibility = 'visible';}} }})()\">show</button>\n".format(len(feasible_schemes), content_id=content_id)
            res += "</div>"
            res += "</td></tr>\n"

            res += "<tr class=\"absinsn explicit_schemes\" id=\"{}\"><td class=\"absinsn\"></td><td class=\"absinsn\">".format(content_id)
            res += "<div class=\"explicit_schemes code indent_content\">"

            strs = list(map(str, feasible_schemes))
            strs.sort()
            for s in strs:
                res += escape(s)
                res += '\n'
            res += "</div>"
            res += "</td></tr>\n"

    res += "</table>\n"

    # abstract aliasing

    highlight_key = None
    if hl_expansion is not None and hl_expansion[0] == 1:
        highlight_key = absblock.actx.json_ref_manager.resolve_json_references(hl_expansion[1])[0]

    entries = []
    abs_alias_dict = absblock.abs_aliasing._aliasing_dict
    for ((iidx1, oidx1), (iidx2,oidx2)), absval in abs_alias_dict.items():
        highlighted = highlight_key == ((iidx1, oidx1), (iidx2,oidx2))
        if absval.is_top():
            if highlighted:
                valtxt = "TOP"
            else:
                continue
        elif absval.is_bottom():
            valtxt = "BOTTOM"
        elif absval.val is False:
            valtxt = "must not alias"
        elif absval.val is True:
            valtxt = "must alias"
        else:
            assert False

        div = "", ""
        if highlighted:
            div = '<div class="highlightedcomponent">', "</div>"
        entries.append((f"<tr><td>{div[0]}{iidx1}:{oidx1} - {iidx2}:{oidx2}{div[1]}</td> <td>{div[0]} {valtxt} {div[1]} </td></tr>\n", f"{iidx1}:{oidx1} - {iidx2}:{oidx2}"))

    if len(entries) > 0:
        res += "<b>Abstract Aliasing:</b>"
        entries.sort(key=lambda x: x[1])
        res += "\n<table>"
        res += "\n" + "\n".join(map(lambda x: x[0], entries))
        res += "</table>"
    elif not skip_top:
        res += "<b>Abstract Aliasing:</b> TOP"

    return '<div class="absblock">\n' + res + '\n</div>'


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

def prettify_config_diff(config_diff):
    css_class = "config-diff"
    lines = []
    compacted = defaultdict(list)
    for ks, v in config_diff:
        if any(map(lambda x: x.endswith("_path"), ks)):
            continue
        compacted[ks].append(v)

    for ks, vs in compacted.items():
        lines.append("<span class='line'>" + ".".join(ks) + "</span>: <span class='line'>" + ",".join(map(escape, vs)) + "</span>")

    if len(lines) == 0:
        return None

    res = f"<div class=\"{css_class}\">\n" + "<br>\n".join(lines) + "</div>\n"

    return mark_safe(res)

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
        batches = campaign.discoverybatch_set.all()
        num_discoveries = sum([b.discovery_set.count() for b in batches])
        tool_list = campaign.tools.all()
        init_interesting_sample_ratio = None
        if len(batches) > 0:
            init_batch = batches[0]
            if init_batch.num_sampled > 0:
                init_interesting_sample_ratio = init_batch.num_interesting / init_batch.num_sampled

        config_delta_html = prettify_config_diff(delta)

        data.append({
            'campaign_id': campaign.id,
            'tools': ", ".join(map(str, tool_list)),
            'config_delta': config_delta_html,
            'date': campaign.date,
            'host_pc': campaign.host_pc,
            'num_batches': len(batches),
            'num_discoveries': num_discoveries,
            'init_interesting_sample_ratio': init_interesting_sample_ratio,
            'time_spent': prettify_seconds(campaign.total_seconds),
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

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:campaign', kwargs={'campaign_id': campaign_id})),
        ]

    discoveries_per_batch_plot = make_discoveries_per_batch_plot(batches)

    num_batches = len(batches)

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
        return mark_safe(prettify_absblock(res, skip_top=True)) # TODO we might want to use django methods to create this html in the first place


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
