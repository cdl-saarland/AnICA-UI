from anica.abstractblock import AbstractBlock
from anica.abstractioncontext import AbstractionContext


def load_abstract_block(json_dict, actx):
    if actx is None:
        config_dict = json_dict['config']
        config_dict['predmanager'] = None # we don't need that one here
        actx = AbstractionContext(config=config_dict)

    # result_ref = json_dict['result_ref']

    ab_dict = actx.json_ref_manager.resolve_json_references(json_dict['ab'])

    ab = AbstractBlock.from_json_dict(actx, ab_dict)
    return ab#, result_ref



