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


def handle_location(location, target_dir):

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

    except subprocess.CalledProcessError as e:
        print("command failed!")
        return False


    return True

def main():
    argparser = argparse.ArgumentParser(description=__doc__)

    argparser.add_argument('-c', '--config', metavar="CONFIG", default=None,
        help='a location config file')

    argparser.add_argument('-o', '--output', metavar="OUTFILE", default="./results",
        help='the directory to store the fetched runs')

    args = argparser.parse_args()

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
        handle_location(location, target_dir)

    return 0

if __name__ == "__main__":
    sys.exit(main())
