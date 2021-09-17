from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
import django

from django.utils.safestring import mark_safe
from django.utils.html import escape

from django.db.models import F

import json

from devidisc.abstractblock import AbstractBlock
from devidisc.abstractioncontext import AbstractionContext
# Create your views here.

from .models import Campaign, Discovery

import django_tables2 as tables

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import io, base64

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
            res += "Feasible Schemes: {} <button onclick=\"(function(){{let el = document.getElementById('{content_id}'); if (el.style.visibility === 'visible') {{el.style.visibility = 'collapse'; }} else {{el.style.visibility = 'visible';}} }})()\">show</button>\n".format(len(feasible_schemes), content_id=content_id)
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
    init_interesting_sample_ratio = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Initial Interesting Sample Ratio")
    time_spent = tables.Column(attrs={"td": campaign_table_attrs, "th": campaign_table_attrs},
            verbose_name="Run-Time")

    class Meta:
        row_attrs = campaign_table_attrs


def all_campaigns(request):
    campaigns = Campaign.objects.all()

    data = []
    for campaign in campaigns:
        batches = campaign.discoverybatch_set.all()
        num_discoveries = sum([b.discovery_set.count() for b in batches])
        tool_list = campaign.tools.all()
        init_interesting_sample_ratio = None
        if len(batches) > 0:
            init_batch = batches[0]
            if init_batch.num_sampled > 0:
                init_interesting_sample_ratio = init_batch.num_interesting / init_batch.num_sampled

        data.append({
            'campaign_id': campaign.id,
            'tools': ", ".join(map(str, tool_list)),
            'date': campaign.date,
            'host_pc': campaign.host_pc,
            'num_batches': len(batches),
            'num_discoveries': num_discoveries,
            'init_interesting_sample_ratio': init_interesting_sample_ratio,
            'time_spent': prettify_seconds(campaign.total_seconds),
            })

    table = CampaignTable(data)

    tables.RequestConfig(request).configure(table)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
        ]

    return render(request, "basic_ui/data_table.html", {
        "title": "All Campaigns",
        "table": table,
        'topbarpathlist': topbarpathlist,
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

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:campaign', kwargs={'campaign_id': campaign_id})),
        ]

    discoveries_per_batch_plot = make_discoveries_per_batch_plot(batches)

    context = {
            'campaign': campaign_obj,
            'tool_list': tool_list,
            'termination_condition': termination_condition,
            'abstraction_config': cfg_str,
            'num_discovery_batches': len(batches),
            'num_discoveries': num_discoveries,
            'time_spent': time_spent,
            'discoveries_per_batch_plot': discoveries_per_batch_plot,
            'topbarpathlist': topbarpathlist,
        }

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
    coverage = tables.Column(
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

    def render_num_insns(self, value, record):
        return len(record.absblock['ab']['abs_insns'])

    def order_num_insns(self, queryset, is_descending):
        queryset = queryset.annotate(
            num_insns=len(F('absblock')['ab']['abs_insns'])
        ).order_by(("-" if is_descending else "") + "num_insns")
        return (queryset, True)

def all_discoveries(request, campaign_id):
    table = DiscoveryTable(Discovery.objects.filter(batch__campaign_id=campaign_id))

    tables.RequestConfig(request).configure(table)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:campaign', kwargs={'campaign_id': campaign_id})),
            ('all discoveries', django.urls.reverse('basic_ui:all_discoveries', kwargs={'campaign_id': campaign_id})),
        ]

    return render(request, "basic_ui/data_table.html", {
        "title": "Discoveries",
        "table": table,
        'topbarpathlist': topbarpathlist,
    })


def discovery(request, campaign_id, discovery_id):
    discovery_obj = get_object_or_404(Discovery, batch__campaign_id=campaign_id, identifier=discovery_id)

    absblock = load_abstract_block(discovery_obj.absblock, None)

    absblock_html = prettify_absblock(absblock, add_schemes=True)

    topbarpathlist = [
            ('all campaigns', django.urls.reverse('basic_ui:all_campaigns')),
            (f'campaign {campaign_id}', django.urls.reverse('basic_ui:campaign', kwargs={'campaign_id': campaign_id})),
            ('all discoveries', django.urls.reverse('basic_ui:all_discoveries', kwargs={'campaign_id': campaign_id})),
            (f'discovery {discovery_id}', django.urls.reverse('basic_ui:discovery', kwargs={'campaign_id': campaign_id, 'discovery_id': discovery_id}))
        ]

    context = {
            'absblock': absblock_html,
            'topbarpathlist': topbarpathlist,
        }
    return render(request, 'basic_ui/discovery_overview.html', context)
