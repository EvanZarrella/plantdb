#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Import a file as a ``File`` in a known ``Fileset``.
"""
import argparse
import json
import os
from pathlib import Path

from plantdb.fsdb import FSDB


def parsing():
    parser = argparse.ArgumentParser(description="Import a file as a ``File`` in a known ``Fileset``.")
    parser.add_argument('--metadata', metavar='metadata', type=str, default=None,
                        help='JSON or TOML file with metadata.')
    parser.add_argument('file', metavar='file', type=str,
                        help='File to add to fileset. File name will be the file id.')
    parser.add_argument('fileset', metavar='fileset', type=str,
                        help='Fileset folder to add the file to (/path/to/db/scan_id/fileset_id).')
    return parser


def run():
    parser = parsing()

    args = parser.parse_args()
    if args.metadata is not None:
        metadata = json.loads(args.metadata)
    else:
        metadata = None

    fileset_dir = Path(args.fileset)

    fileset_id = os.path.basename(args.fileset)
    file_id = os.path.basename(os.path.splitext(args.file)[0])
    scan_id = os.path.basename(fileset_dir.parent)
    db_path = fileset_dir.parent.parent

    db = FSDB(db_path)
    db.connect()

    scan = db.get_scan(scan_id, create=True)
    fileset = scan.get_fileset(fileset_id, create=True)
    file = fileset.create_file(file_id)
    file.import_file(args.file)

    if metadata is not None:
        file.set_metadata(metadata)


if __name__ == '__main__':
    run()
