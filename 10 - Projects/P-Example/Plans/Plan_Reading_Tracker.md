# Plan: Reading Tracker
**Date**: 2026-01-10 · **Status**: Draft · **Research**: [[Research_Reading_Tracker]]

## Goal
Log finished books to a local CSV from the command line, with no dependencies beyond Python 3.

## Design
- `reading/schema.py`: the CSV header, defined once.
- `reading/store.py`: append and read rows; creates the file with a header on first write.
- `reading/cli.py`: `add` and `list [--year YYYY]` subcommands via `argparse`.

## Trade-offs
- CSV over SQLite: opens in any spreadsheet (owner asked), at the cost of no concurrent writers. Acceptable for one user.
- Weekly email: out of scope until the owner decides (Owner Queue).
