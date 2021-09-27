from collections import defaultdict
import json

from django.utils.html import escape
from django.utils.safestring import mark_safe

# TODO we might want to use django methods to create this html in the first place

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

def make_link(url, caption, is_relative=False):
    prefix = ""
    if not is_relative:
        prefix = "https://"
    link_frame = '<a href="{prefix}{url}" target="_blank" rel="noopener noreferrer">{caption}</a>'
    return link_frame.format(prefix=prefix, url=url, caption=caption)

def prettify_absblock(absblock, hl_expansion=None, skip_top=False, add_schemes=False):
    actx = absblock.actx

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

        feasible_schemes = actx.insn_feature_manager.compute_feasible_schemes(ai.features)
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

            # add clickable links to uops.info and felixcloutier.com where available
            strs = []
            for ischeme in feasible_schemes:
                features = actx.iwho_ctx.get_features(ischeme)
                ischeme_str = str(ischeme)
                ann_insn_str = escape(ischeme_str)

                num_indents = max(4, 52 - len(ischeme_str))
                annotations = []
                if features is not None and len(features) > 0:
                    general_features = features[0]
                    ref_url = general_features.get("ref_url", None)
                    if ref_url is not None:
                        annotations.append(make_link(url=ref_url, caption="ref"))
                    uops_info_url = general_features.get("uops_info_url", None)
                    if uops_info_url is not None:
                        annotations.append(make_link(url=uops_info_url, caption="uops.info"))
                if len(annotations) > 0:
                    ann = ",".join(annotations)
                    ann_insn_str += '<span class="code_comment">{}; [{}]</span>'.format("&nbsp;" * num_indents, ann)

                strs.append(ann_insn_str)

            strs.sort()
            res += "\n".join(strs)

            res += "</div>"
            res += "</td></tr>\n"

    res += "</table>\n"

    # abstract aliasing

    highlight_key = None
    if hl_expansion is not None and hl_expansion[0] == 1:
        highlight_key = actx.json_ref_manager.resolve_json_references(hl_expansion[1])[0]

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

    return mark_safe('<div class="absblock">\n' + res + '\n</div>')


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

def prettify_abstraction_config(abstraction_config):
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


