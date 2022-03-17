#!/usr/bin/env python3

""" Get AnICA campaign results from remote machines.
"""

import argparse
from datetime import datetime

import json
import os
from pathlib import Path
import subprocess
import sys

# import_path = os.path.join(os.path.dirname(__file__), "..")
# sys.path.append(import_path)

compress_command = "tar --force-local -czvf"
uncompress_command = "tar --force-local -xzvf"
compress_suffix = "tgz"


def dry_run_fun(*args, **kwargs):
    class DummyRetVal:
        returncode = 0

    print("    run command:")
    for a in args:
        print(f"      {a}")
    for k, v in kwargs.items():
        print(f"      {k}: {v}")
    return DummyRetVal()

repo_base = Path(__file__).parent.parent
add_metrics_command =  repo_base / 'tools' / 'add_metrics.py'
import_command =  repo_base / 'anica_ui' / 'manage.py'

def handle_location(location, target_dir, add_metrics=False, import_name=None):

    run_fun = dry_run_fun
    run_fun = subprocess.run


    name = location['name']
    url = location['url']
    result_dir = location['result_dir']
    archive_dir = location['archive_dir']

    timestamp = datetime.now().replace(microsecond=0).isoformat()

    archive_name = f"anica_{timestamp}_{name}.{compress_suffix}"

    print(f"fetching results from location {name}")

    try:
        print("  - looking for results on the remote machine")
        remote_command = f'cd {result_dir}; [ "$(ls -A)" ]'
        cmd = ["ssh", url, remote_command]
        res = run_fun(cmd)
        if res.returncode != 0:
            print("No results found!")
            return False

        print("  - compressing results on the remote machine")
        remote_command = f'cd {result_dir}; {compress_command} {archive_name} *'
        cmd = ["ssh", url, remote_command]
        run_fun(cmd, check=True)

        print("  - copying compressed results to the local machine")
        local_target_dir = target_dir / f"anica_{timestamp}_{name}"
        os.makedirs(local_target_dir)
        archive_address = f"{url}:{result_dir}/{archive_name}"
        cmd = ["scp", "-r", archive_address, str(local_target_dir) ]
        run_fun(cmd, check=True)

        print("  - uncompressing results on the local machine")
        cmd = list(uncompress_command.split())
        cmd.append(archive_name)
        run_fun(" ".join(cmd), cwd=local_target_dir, check=True, shell=True)

        if archive_dir is not None:
            print("  - archiving results on the remote machine")
            remote_command = f'cp {result_dir}/{archive_name} {archive_dir}'
            cmd = ["ssh", url, remote_command]
            run_fun(cmd, check=True)

        print("  - removing results on the remote machine")
        remote_command = f'cd {result_dir}; rm -rf ./*'
        cmd = ["ssh", url, remote_command]
        run_fun(cmd, check=True)

        if add_metrics:
            cmd = [add_metrics_command]
            dirs = list(sorted(map(str, filter(lambda x: x.is_dir(), local_target_dir.glob('*')))))
            cmd += dirs
            print("  - adding metrics to the following campaign directories:")
            for d in dirs:
                print(f"    - {d}")
            run_fun(cmd, check=True)

            if import_name is not None:
                tag = import_name.format(name=name)
                print(f"  - importing the campaigns under the tag '{tag}'")
                cmd = [import_command, 'import_campaign']
                cmd.append(tag)
                cmd += dirs
                run_fun(cmd, check=True)

    except subprocess.CalledProcessError as e:
        print("command failed!")
        return False


    return True

def main():
    argparser = argparse.ArgumentParser(description=__doc__)

    argparser.add_argument('-c', '--config', metavar="CONFIG", default=None,
        help='a location config file')

    argparser.add_argument('-a', '--add-metrics', action="store_true",
        help='do the add_metrics post-processing on the downloaded campaigns')

    argparser.add_argument('-i', '--import-name', metavar="TAG", default=None,
            help='import the downloaded campaigns with the specified tag to the ui. Requires -a. The tag can include a "{name}" place holder that is replaced with the corresponding name from the config. For example: "bughunt:{name}"')

    argparser.add_argument('-o', '--output', metavar="OUTFILE", default="./results",
        help='the directory to store the fetched runs')

    args = argparser.parse_args()

    if args.import_name is not None and not args.add_metrics:
        print("This script will only import campaigns with metrics added, add '-a' to do that.", file=sys.err)
        sys.exit(1)

    location_config = args.config
    if location_config is None:
        if os.path.isfile("./location.json"):
            location_config = "./location.json"
        else:
            print("No location config file found!", file=sys.stderr)
            sys.exit(1)

    with open(location_config) as f:
        locations = json.load(f)

    target_dir = Path(args.output)

    for location in locations:
        handle_location(location, target_dir, add_metrics=args.add_metrics, import_name=args.import_name)

    return 0

if __name__ == "__main__":
    sys.exit(main())
