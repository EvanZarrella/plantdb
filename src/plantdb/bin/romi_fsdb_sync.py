#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Synchronize two ``FSDB`` databases.
"""
import argparse

from plantdb.sync import FSDBSync


def parsing():
    parser = argparse.ArgumentParser(description='Synchronize two FSDB databases')
    parser.add_argument('orig', metavar='orig', type=str,
                        help='Source database (path, local or remote)')
    parser.add_argument('target', metavar='target', type=str,
                        help='Target database (path, local or remote)')
    return parser


def run():
    parser = parsing()
    args = parser.parse_args()
    fsdb_sync = FSDBSync(args.orig, args.target)
    fsdb_sync.sync()


if __name__ == '__main__':
    run()
