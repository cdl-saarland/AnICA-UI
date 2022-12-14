#!/usr/bin/env python3
""" This script adds a metrics.json file with additional discovery metrics to
campaign directories.
"""

import argparse
import json
import math
import os
from pathlib import Path
import random
from statistics import geometric_mean

from progress.bar import Bar as ProgressBar

from anica.abstractblock import AbstractBlock
from anica.abstractioncontext import AbstractionContext
from iwho.configurable import load_json_config, store_json_config

from anica.satsumption import check_subsumed_aa

from anica.utils import Timer

def load_absblock(abfile, actx=None):
    json_dict = load_json_config(abfile)

    if actx is None:
        config_dict = json_dict['config']
        config_dict['predmanager'] = None # we don't need that one here
        actx = AbstractionContext(config=config_dict)

    result_ref = json_dict['result_ref']

    ab_dict = actx.json_ref_manager.resolve_json_references(json_dict['ab'])

    ab = AbstractBlock.from_json_dict(actx, ab_dict)
    return ab, result_ref

def add_metrics_for_campaign_dir(campaign_dir, overwrite=False):
    base_dir = Path(campaign_dir)

    result_path = base_dir / 'metrics.json'

    if result_path.exists() and not overwrite:
        print(f"Adding no metrics to campaign directory '{base_dir}' because a 'metrics.json' already exists. Run with '--overwrite' to overwrite.")
        return

    print(f"computing metrics for '{base_dir}'")

    discovery2metrics = dict()

    unsubsumed_absblocks = []

    actx = None
    mdb = None

    discovery_files = list(os.listdir(base_dir / 'discoveries'))
    with ProgressBar(f"progress:",
            suffix = '%(percent).1f%%',
            max=len(discovery_files)) as pb:
        for fn in discovery_files:
            discovery_id, ext = os.path.splitext(fn)
            assert ext == '.json'
            full_path = base_dir / 'discoveries' / f'{discovery_id}.json'

            absblock, result_ref = load_absblock(full_path, actx=actx)
            if actx is None:
                actx = absblock.actx
                mdb = actx.measurement_db
                mdb._init_con()

            with Timer.Sub('get_series'):
                # with actx.measurement_db as mdb:
                meas_series = mdb.get_series(result_ref)

            with Timer.Sub('compute_interestingness'):
                # get interestingness
                ints = []
                for entry in meas_series['measurements']:
                    eval_res = dict()
                    for r in entry['predictor_runs']:
                        eval_res[r['predictor']] = {'TP': r['result']}
                    interestingness = actx.interestingness_metric.compute_interestingness(eval_res)
                    ints.append(interestingness)

            if len(ints) == 0 or any(map(lambda x: not math.isfinite(x), ints)) or any(map(lambda x: x <= 0, ints)):
                mean_interestingness = math.inf
            else:
                mean_interestingness = geometric_mean(ints)

            with Timer.Sub('subsumption_check'):
                # check if this discovery subsumes any of the previous ones
                # The other direction should not be possible, because such
                # cases should be prevented by the subsumption check in the
                # discovery algorithm.
                next_unsubsumed_absblocks = []
                for prev_id, prev_ab in unsubsumed_absblocks:
                    if check_subsumed_aa(prev_ab, absblock):
                        discovery2metrics[prev_id]['subsumed_by'] = discovery_id
                        continue
                    next_unsubsumed_absblocks.append((prev_id, prev_ab))
                unsubsumed_absblocks = next_unsubsumed_absblocks

                unsubsumed_absblocks.append((discovery_id, absblock))

            metrics = {
                    'mean_interestingness' : mean_interestingness,
                    'interestingness_series': ints,
                    'subsumed_by': None,
                }

            discovery2metrics[discovery_id] = metrics
            pb.next()

    if mdb is not None:
        mdb._deinit_con()
    store_json_config(discovery2metrics, result_path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    ap.add_argument('-s', '--seed', type=int, default=424242, metavar="SEED", help="Seed for the random number generator.")
    ap.add_argument('--overwrite', action='store_true', help="if specified, overwrite existing 'metrics.json' files with newly computed data")

    # ap.add_argument('--covnum', type=int, default=10000, help="number of samples to use for computing absblock coverage")
    ap.add_argument('campaigndirs', metavar='DIR', nargs='+', help='path(s) to a campaign result directory')

    args = ap.parse_args()

    Timer.enabled = True

    random.seed(args.seed)

    with Timer('total') as timer:
        for campaign_dir in args.campaigndirs:
            add_metrics_for_campaign_dir(campaign_dir, overwrite=args.overwrite)

    print(timer.get_result())


if __name__ == "__main__":
    main()
