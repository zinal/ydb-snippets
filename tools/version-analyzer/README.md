# Version analyzer (missing commits)

Small utilities to list commits on a **source** Git branch that are **probably not** present on a **destination** branch, with optional path ignore lists and issue/PR number heuristics.

## Requirements

- Python 3.10+ (uses `str | None` style types)
- `git` on `PATH`

## `find_missing_commits.py`

### What it reports

Candidates are commits reachable from **previous** since a start date, but **not** in the history of **next** (same idea as `git log previous ^next --since=...`).

A commit is **not** listed if any of these hold:

- It is already an ancestor of **next** (fully merged by identity in history).
- Every `#1234`-style id in the commit **message** also appears in some commit message on **next** (within the issue window you configure), so the work is treated as already tracked on the destination.
- **`--base`**: the commit is already on the **base** ref (same SHA in that history) *or* all of its `#…` ids appear in the base message scan.
- **`--skip-file`**: the commit only touches paths under allowed **prefixes** in the skip file (e.g. docs you do not care about for this check).

### Output format

One line per “probably missing” commit, **tab-separated**, **sorted** by **committer time** (UTC), then SHA:

```text
2025-01-15T12:30:45Z	<full-40-hex-sha>	<first line of commit message>
```

### Usage

```text
find_missing_commits.py [options] REPO PREVIOUS NEXT SINCE
```

| Argument / option | Meaning |
|-------------------|--------|
| `REPO` | Path to the repository |
| `PREVIOUS` | Source branch (short name or full ref) |
| `NEXT` | Destination branch |
| `SINCE` | Start of the analysis window (`git log --since=`), e.g. `2025-01-01` |
| `--remote NAME` | Remote used to resolve short names to `refs/remotes/NAME/...` (default: `upstream`) |
| `--skip-file PATH` | File of path **prefixes** to ignore (one per line; `#` starts a comment) |
| `--next-since DATE` | Only scan **next** for `#…` from this date; default: same as `SINCE` |
| `--all-next-issues` | Scan **entire** **next** history for `#…` ids (ignore `--next-since`) |
| `--base REF` | Optional third branch; if work is on **base** (SHA or `#` match), do not list |
| `--base-since DATE` | **Base** message scan window for `#…`; default: `SINCE` if `--base` is set |
| `--all-base-issues` | Full **base** history for `#…` (ignore `--base-since`) |
| `--no-fetch` | Do not run `git fetch` (use only local refs) |
| `--file-workers N` | Parallel `git show` count for rare merge/skip path resolution (1–64, default: 16) |

By default the script runs `git fetch <remote> --prune` and fetches the explicit branches you name so `refs/remotes/<remote>/…` is up to date.

### Skip file

Plain text: one path prefix per line, repository-relative, POSIX-style. Lines whose first non-space character is `#` are comments. A commit is **skipped** (treated as not “missing” for reporting) if **every** path it changes lies under at least one listed prefix. Empty path list for a commit is treated as “only ignored paths”.

Example:

```text
# doc-only
ydb/docs/
.github/
```

### Example

```bash
cd tools/version-analyzer
python3 find_missing_commits.py /path/to/ydb \
  --remote origin \
  --skip-file ./skip.txt \
  --base stable-25-2-0 \
  stable-25-2-1 stable-25-3-1 2025-01-01
```

## `validate_find_missing_output.py`

Optionally check a saved report (or stdin) with **plain `git`** commands, and/or compare to a fresh run of the same rules.

```text
validate_find_missing_output.py [options] REPO PREVIOUS NEXT SINCE [OUTPUT_FILE]
```

Omit `OUTPUT_FILE` to read lines from **stdin**.

Useful flags: `--recompute-expected` (SHA set must match `find_missing_commits` for the same parameters), `--self-check-outputs` (heuristic), plus the same `--base` / issue-window flags as the main tool when you used them.

```bash
python3 find_missing_commits.py --no-fetch /path/to/repo --remote origin \
  old-branch new-branch 2025-01-01 > report.txt

python3 validate_find_missing_output.py /path/to/repo --remote origin \
  --recompute-expected \
  old-branch new-branch 2025-01-01 report.txt
```

## Limitations

Heuristics can miss edge cases: cherry-picks with new SHAs, squash merges, rewrites, or issues referenced differently in messages. The tool is meant to **narrow** a manual review list, not replace it.
