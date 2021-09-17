#!/usr/bin/env python3
""" This script adds a metrics.json file with additional discovery metrics to
campaign directories.
"""

import argparse
import json
import os
from pathlib import Path
import random
from statistics import geometric_mean

from devidisc.abstractblock import AbstractBlock
from devidisc.abstractioncontext import AbstractionContext
from devidisc.configurable import load_json_config, store_json_config

from devidisc.satsumption import ab_coverage

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

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    ap.add_argument('-s', '--seed', type=int, default=424242, metavar="SEED", help="Seed for the random number generator.")
    ap.add_argument('--overwrite', action='store_true', help="if specified, overwrite existing 'metrics.json' files with newly computed data")

    ap.add_argument('--covnum', type=int, default=10000, help="number of samples to use for computing absblock coverage")
    ap.add_argument('campaigndirs', metavar='DIR', nargs='+', help='path(s) to a campaign result directory')

    args = ap.parse_args()

    random.seed(args.seed)

    for campaign_dir in args.campaigndirs:
        base_dir = Path(campaign_dir)

        result_path = base_dir / 'metrics.json'

        if result_path.exists() and not args.overwrite:
            print(f"Skipping campaign directory '{base_dir}' because a 'metrics.json' already exists. Run with '--overwrite' to overwrite.")
            continue

        discovery2metrics = dict()

        actx = None
        for fn in os.listdir(base_dir / 'discoveries'):
            discovery_id, ext = os.path.splitext(fn)
            assert ext == '.json'
            full_path = base_dir / 'discoveries' / f'{discovery_id}.json'

            absblock, result_ref = load_absblock(full_path, actx=actx)
            if actx is None:
                actx = absblock.actx

            with actx.measurement_db as mdb:
                meas_series = mdb.get_series(result_ref)

            # get interestingness
            ints = []
            for entry in meas_series['measurements']:
                eval_res = dict()
                for r in entry['predictor_runs']:
                    eval_res[r['predictor']] = {'TP': r['result']}
                ints.append(actx.interestingness_metric.compute_interestingness(eval_res))

            mean_interestingness = geometric_mean(ints)

            # compute coverage
            coverage = ab_coverage(absblock, args.covnum)

            metrics = {
                    'mean_interestingness' : mean_interestingness,
                    'interestingness_series': ints,
                    'ab_coverage': coverage,
                }

            discovery2metrics[discovery_id] = metrics

        store_json_config(discovery2metrics, result_path)


if __name__ == "__main__":
    main()
