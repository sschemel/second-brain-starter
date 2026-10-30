# Spec: Reading Tracker
**Date**: 2026-01-10 · **Status**: Draft (waits on plan approval) · **Plan**: [[Plan_Reading_Tracker]]

## Acceptance Criteria
- AC1: `reading add "Dune" --author "Frank Herbert"` appends one row with today's date to `~/reading.csv`, creating the file with a header if missing.
- AC2: `reading list` prints every row, newest first.
- AC3: `reading list --year 2025` prints only rows finished in 2025.
- AC4: The header comes from `reading/schema.py` in both code and tests (see the project's `Learnings.md`).
