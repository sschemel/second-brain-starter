# Backup

`/eod` commits the vault and pushes it to GitHub **only** when this file says `backup: enabled` **and** the `origin` remote is a GitHub repo that `gh` confirms is private.

To turn it on: create a **private** GitHub repo, run `git remote add origin <url>`, make sure `gh auth status` succeeds, then change the line below to `backup: enabled`.

backup: disabled
