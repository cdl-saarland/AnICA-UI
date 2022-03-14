import django

from copy import deepcopy
import json
import textwrap

from anica.abstractioncontext import AbstractionContext
from anica.witness import WitnessTrace
from iwho.configurable import load_json_config

from .custom_pretty_printing import prettify_absblock

def gen_witness_site(campaign_id, witness_path):
    tr = load_witness(witness_path)
    g =  make_witness_graph(campaign_id, tr)
    return g.generate()


def get_witnessing_series_id(campaign_id, witness_path):
    """ Get the measurement series id that corresponds to the terminating
    abstract block.
    """
    res_id = -1

    tr = load_witness(witness_path)
    for witness, ab in tr.iter(taken_only=True):
        if witness.measurements is not None:
            res_id = witness.measurements

    return res_id


def load_witness(trfile, actx=None):
    json_dict = load_json_config(trfile)

    if actx is None:
        config_dict = json_dict['config']
        config_dict['predmanager'] = None # we don't need that one here
        actx = AbstractionContext(config=config_dict)

    tr_dict = actx.json_ref_manager.resolve_json_references(json_dict['trace'])

    tr = WitnessTrace.from_json_dict(actx, tr_dict)
    return tr

def make_witness_graph(campaign_id, witness):
    actx = witness.start.actx

    g = HTMLGraph("AnICA Visualization", actx=actx)

    abb = deepcopy(witness.start)

    empty_link = django.urls.reverse('basic_ui:measurements_empty')

    parent = g.add_block(text=prettify_absblock(abb), kind="start", link=empty_link)
    g.new_row()

    prev_taken_link = empty_link

    for witness in witness.trace:
        meas_id = witness.measurements

        if meas_id is None:
            link = prev_taken_link
        else:
            link = django.urls.reverse('basic_ui:measurements', kwargs={'campaign_id': campaign_id, 'meas_id': meas_id})

        if witness.terminate:
            new_node = g.add_block(text="Terminated: " + witness.comment, kind="end", link=link)
            g.add_edge(parent, new_node)
            continue

        if witness.taken:
            abb.apply_expansion(witness.expansion)

            new_node = g.add_block(text=prettify_absblock(abb, witness.expansion), kind="interesting", link=link)
            g.add_edge(parent, new_node)

            parent = new_node
            g.new_row()

            prev_taken_link = link
        else:
            tmp_abb = deepcopy(abb)
            tmp_abb.apply_expansion(witness.expansion)

            new_node = g.add_block(text=prettify_absblock(tmp_abb, witness.expansion), kind="notinteresting", link=link)
            g.add_edge(parent, new_node)
    g.new_row()

    return g


class HTMLGraph:
    class Block:
        def __init__(self, ident, text, link, kind):
            self.ident = ident
            self.text = text
            self.link = link
            self.kind = kind

    def __init__(self, title, actx):
        self.title = title

        self.actx = actx

        self.rows = []
        self.current_row = []

        self.next_ident = 0

        self.ident2block = dict()

        self.edges = []

        self.measurement_sites = []

    def new_row(self):
        self.rows.append(self.current_row)
        self.current_row = []

    def add_block(self, text, kind, link=None):
        ident = "block_{}".format(self.next_ident)
        self.next_ident += 1

        block = HTMLGraph.Block(ident, text, link, kind)

        self.current_row.append(block)

        self.ident2block[ident] = block
        return ident

    def add_edge(self, src_ident, dst_ident):
        self.edges.append((src_ident, dst_ident))

    def generate(self):
        # compute the grid components
        grid_content = ""
        for row in self.rows:
            grid_content += textwrap.indent('<div class="gridsubcontainer">\n', 16*' ')
            for block in reversed(row):
                link = 'null' if block.link is None else f"\'{block.link}\'"
                onclick = f'onclick="click_handler(this, {link})"'
                grid_content += textwrap.indent(f'<div id="{block.ident}" class="griditem block_{block.kind}" {onclick}>\n', 18*' ')
                grid_content += f'<div class="abstractbb">{block.text}</div>\n'
                grid_content += textwrap.indent('</div>\n', 18*' ')
            grid_content += textwrap.indent('</div>\n', 16*' ')

        # arrows go to the script part
        connectors = []
        for src, dst in self.edges:
            connectors.append(f'drawConnector("{src}", "{dst}");')
        connector_str = "\n".join(connectors)
        connector_str = textwrap.indent(connector_str, 4*' ')

        return {
            "grid_content": grid_content,
            "connector_js": connector_str,
        }


_measurement_frame = """
    <div class="measurement">
      <h3> Measurement #{meas_id} </h3>
      <table class="meastable">
        <tr> <th> assembly </th>
          <td>
            <div class="asmblock">{{asmblock}}</div>
          </td>
        </tr>
        <tr> <th> hex </th>
          <td>
            <div class="hexblock">{hexblock}</div>
          </td>
        </tr>
        {predictor_runs}
      </table>
    </div>
"""

_predictor_run_frame = """
        <tr>
          <th> {predictor} </th>
          <td> {result} </td>
        </tr>
"""

def gen_measurement_site(actx, series_id, choose_only=None):
    """ Collect the data to show a measurement series (used as an input to
    render with the measurements.html template).

    If choose_only is not None, choose (up to) num_examples measurements from
    the given series in a way that attempts to capture diverse interestingness
    values and display them like a normal measurement site. Otherwise: show
    all.
    """

    with actx.measurement_db as mdb:
        measdict = mdb.get_series(series_id)

    if measdict is None:
        return None

    # series_id = measdict.get("series_id", "N")
    series_date = measdict["series_date"]
    source_computer = measdict["source_computer"]

    measurement_texts = []

    num_interesting = 0
    num_measurements = len(measdict["measurements"])

    for m in measdict["measurements"]:
        meas_id = m.get("measurement_id", "N")
        hexblock = m["input"]

        predictor_run_texts = []
        for r in m["predictor_runs"]:
            predictor_text = ", ".join(r["predictor"]) + ", " + r["uarch"]
            results = []
            if r["result"] is not None:
                results.append(r["result"])
            if r["remark"] is not None:
                remark = r["remark"]
                try:
                    json_dict = json.loads(remark)
                    if "error" in json_dict:
                        results.append("\n<div class='code'>" + json_dict["error"] + "</div>")
                except:
                    results.append(remark)
            result_text = ", ".join(map(str, results))
            predictor_run_texts.append(_predictor_run_frame.format(predictor=predictor_text, result=result_text))

        # compute interestingness to sort by it
        eval_res = {x: {"TP": r.get("result", None)} for x, r in enumerate(m["predictor_runs"])}
        interestingness = actx.interestingness_metric.compute_interestingness(eval_res)
        if actx.interestingness_metric.is_interesting(eval_res):
            num_interesting += 1

        full_predictor_run_text = "\n".join(predictor_run_texts)

        full_predictor_run_text = _predictor_run_frame.format(predictor="interestingness", result=f"{interestingness:.3f}") + full_predictor_run_text

        meas_text = _measurement_frame.format(meas_id=meas_id, hexblock=hexblock , predictor_runs=full_predictor_run_text)
        measurement_texts.append((interestingness, meas_text, hexblock))

    measurement_texts.sort(key=lambda x: x[0], reverse=True)

    if choose_only is not None:
        if 1 < choose_only < len(measurement_texts):
            # take `choose_only` measurements separated by a maximal equal distance `step` from the list
            step = int((len(measurement_texts) - 1) / (choose_only - 1))
            measurement_texts = list(measurement_texts[::step])

    measurement_texts_with_asm = []
    # We postpone creating the ASM representation after filtering because it is
    # too costly to do unnecessarily.
    for (interestingness, meas_text, hexblock) in measurement_texts:
        asmblock = '\n'.join(actx.iwho_ctx.coder.hex2asm(hexblock))
        measurement_texts_with_asm.append(meas_text.format(asmblock=asmblock))

    full_meas_text = "\n".join(measurement_texts_with_asm)

    interesting_percentage = (num_interesting / num_measurements) * 100

    comment_str = f"{num_interesting} out of {num_measurements} measurements ({interesting_percentage:.1f}%) are interesting."

    return dict(
            series_id=series_id,
            series_date=series_date,
            comment=comment_str,
            source_computer=source_computer,
            measurement_text=full_meas_text)



