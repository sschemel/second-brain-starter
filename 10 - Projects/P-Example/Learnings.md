# P-Example Learnings

<!-- Lessons true only for this project. /freddie-learn writes here; /eod promotes a general version to AGENTS.md §7 only when it holds beyond this project. -->

### 📅 2026-01-10 - CSV header drift
- **Failure Mode**: A test fixture used `Title,Author` while the code wrote `title,author`, so the round-trip test passed on one machine and failed on another with a different locale setting.
- **Rule**: The CSV header is defined once in `reading/schema.py`; fixtures import it rather than retyping it.
