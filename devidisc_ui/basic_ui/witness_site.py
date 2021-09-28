
from copy import deepcopy
import json
import textwrap

from devidisc.abstractioncontext import AbstractionContext
from devidisc.witness import WitnessTrace

from .custom_pretty_printing import prettify_absblock

def gen_witness_site(witness_path):
    tr = load_witness(witness_path)
    g =  make_witness_graph(tr)
    return g.generate()

def load_witness(trfile, actx=None):
    with open(trfile) as f:
        json_dict = json.load(f)

    if actx is None:
        config_dict = json_dict['config']
        config_dict['predmanager'] = None # we don't need that one here
        actx = AbstractionContext(config=config_dict)

    tr_dict = actx.json_ref_manager.resolve_json_references(json_dict['trace'])

    tr = WitnessTrace.from_json_dict(actx, tr_dict)
    return tr

def make_witness_graph(witness):
    actx = witness.start.actx

    g = HTMLGraph("DeviDisc Visualization", actx=actx)

    abb = deepcopy(witness.start)

    parent = g.add_block(text=prettify_absblock(abb), kind="start")
    g.new_row()

    for witness in witness.trace:
        meas_id = witness.measurements

        if witness.terminate:
            new_node = g.add_block(text="Terminated: " + witness.comment, kind="end")
            g.add_edge(parent, new_node)
            continue

        if witness.taken:
            abb.apply_expansion(witness.expansion)

            new_node = g.add_block(text=prettify_absblock(abb, witness.expansion), kind="interesting")
            g.add_edge(parent, new_node)

            parent = new_node
            g.new_row()
        else:
            tmp_abb = deepcopy(abb)
            tmp_abb.apply_expansion(witness.expansion)

            new_node = g.add_block(text=prettify_absblock(tmp_abb, witness.expansion), kind="notinteresting")
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

