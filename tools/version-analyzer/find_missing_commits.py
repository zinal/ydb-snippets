#!/usr/bin/env python3
"""
Find commits on a source (previous) branch that likely were not applied to a
destination (next) branch.

- Commits that are already in the history of the destination (reachable from
  the ``next`` ref) are not listed, using ``git log previous ^next`` (not
  N× ``merge-base`` per commit).
- If a commit has #123 (etc.) in its message, and every such id appears in some
  commit on the destination in the issue-matching range, the commit is not
  listed (squelch duplicate PR/issue work).
- If ``--base`` is set, commits that are already on the base branch (same
  object id, or the same #… ids as in the base message scan) are not listed.
- Commits that only change files under the skip prefix list are not listed.

The previous branch is scanned with ``git log --since`` through its tip. Use
``--all-next-issues`` to use the full destination history only for # matching.

Output lines: ``<committer-time-UTC-ISO>`` TAB commit-SHA TAB subject, sorted
by committer time then SHA.

By default, ``git fetch <remote> --prune`` runs first, then each short branch
name is fetched with an explicit refspec so ``refs/remotes/<remote>/<name>`` is
current (and created if missing). Use ``--no-fetch`` to only use what is already
in the local clone.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


ISSUE_RE = re.compile(r"#([0-9]+)")
FULL_SHA1_RE = re.compile(r"^[0-9a-fA-F]{40}$")
# Default worker count for ``git show`` when ``--name-only`` needs a merge fix-up
_DEFAULT_FILE_WORKERS = 16


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    subject: str
    # Full message (git %B) for #... matching; subject is the first line
    message: str
    # Committer time (``git`` %ct), seconds since epoch — used for output order
    commit_ts: int


def run_git(
    repo: Path,
    *args: str,
    check: bool = True,
) -> str:
    cmd = ("git", "-C", str(repo), *args)
    p = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and p.returncode != 0:
        sys.stderr.write(
            f"Command failed ({p.returncode}): {' '.join(cmd)}\n"
            f"{p.stderr or p.stdout}"
        )
        raise SystemExit(1)
    return p.stdout


def is_ancestor(repo: Path, commit: str, ref: str) -> bool:
    p = subprocess.run(
        ("git", "-C", str(repo), "merge-base", "--is-ancestor", commit, ref),
        capture_output=True,
    )
    if p.returncode == 0:
        return True
    if p.returncode == 1:
        return False
    sys.stderr.write((p.stderr or b"").decode())
    raise SystemExit(p.returncode)


def remote_is_configured(repo: Path, remote: str) -> bool:
    p = subprocess.run(
        ("git", "-C", str(repo), "remote", "get-url", remote),
        capture_output=True,
    )
    return p.returncode == 0


def _server_branch_name_for_fetch(remote: str, branch: str) -> str | None:
    """
    Branch name on the server (under refs/heads/) for an explicit fetch refspec.
    None if the argument is not a simple remote branch we can name with
    refs/heads/<name> (e.g. tags, arbitrary full refs we should not guess).
    """
    s = branch.strip()
    if not s:
        return None
    if s.startswith("refs/heads/"):
        return s.removeprefix("refs/heads/")
    if s.startswith("refs/tags/"):
        return None
    if s.startswith("refs/remotes/"):
        rest = s.removeprefix("refs/remotes/")
        if "/" not in rest:
            return None
        r, name = rest.split("/", 1)
        if r == remote:
            return name
        return None
    if s.startswith("remotes/"):
        return _server_branch_name_for_fetch(
            remote, s.replace("remotes/", "refs/remotes/", 1)
        )
    if s.startswith("refs/"):
        return None
    if s.startswith(f"{remote}/") and s.count("/") >= 1:
        return s.removeprefix(f"{remote}/")
    return s


def _ref_resolves(
    repo: Path,
    ref: str,
) -> bool:
    p = subprocess.run(
        (
            "git",
            "-C",
            str(repo),
            "rev-parse",
            "--verify",
            f"{ref}^{{commit}}",
        ),
        capture_output=True,
    )
    return p.returncode == 0


def fetch_one_remote_branch(
    repo: Path,
    remote: str,
    name: str,
) -> None:
    """
    Force-update ``refs/remotes/<remote>/<name>`` from
    ``refs/heads/<name>`` on the server, or if that ref is missing, keep using
    an existing local branch or remote-tracking ref and warn.
    """
    p = subprocess.run(
        (
            "git",
            "-C",
            str(repo),
            "fetch",
            remote,
            f"+refs/heads/{name}:refs/remotes/{remote}/{name}",
        ),
        capture_output=True,
        text=True,
    )
    if p.returncode == 0:
        return
    err = p.stderr or p.stdout or ""
    missing = "couldn't find remote ref" in err or "could not find" in err.lower()
    if missing:
        for fallback in (f"refs/heads/{name}", f"refs/remotes/{remote}/{name}"):
            if _ref_resolves(repo, fallback):
                sys.stderr.write(
                    f"Note: remote {remote!r} has no refs/heads/{name}; using "
                    f"existing local ref {fallback!r} (may be stale).\n"
                )
                return
    sys.stderr.write(
        f"Failed to update branch {name!r} from {remote}.\n" f"  {err}\n"
    )
    raise SystemExit(1)


def fetch_branches_for_analysis(
    repo: Path,
    remote: str,
    previous: str,
    next_branch: str,
    base_branch: str | None = None,
) -> None:
    """
    Update the remote: ``git fetch <remote> --prune``, then for each
    resolvable short branch name run an explicit
    ``refs/heads/<n> -> refs/remotes/<remote>/<n>`` fetch so analysis uses the
    current server tip. When the server has no such branch, keep an existing
    local ref and print a short notice.
    """
    if not remote_is_configured(repo, remote):
        sys.stderr.write(
            f"Remote {remote!r} is not configured in {repo}.\n"
            "Add it with: git remote add, or use --no-fetch with local refs only.\n"
        )
        raise SystemExit(1)
    run_git(repo, "fetch", remote, "--prune")
    names: set[str] = set()
    for b in (previous, next_branch) + (() if base_branch is None else (base_branch,)):
        n = _server_branch_name_for_fetch(remote, b)
        if n is not None:
            names.add(n)
    for n in sorted(names):
        fetch_one_remote_branch(repo, remote, n)


def resolve_ref(repo: Path, remote: str, branch: str) -> str:
    """Return a ref that `git log` and `merge-base` accept."""
    if (
        branch.startswith("refs/")
        or branch.startswith("remotes/")
        or "/remotes/" in branch
    ):
        run_git(repo, "rev-parse", "--verify", f"{branch}^{{commit}}")
        return branch
    for candidate in (
        f"refs/remotes/{remote}/{branch}",
        branch,
        f"refs/heads/{branch}",
    ):
        p = subprocess.run(
            (
                "git",
                "-C",
                str(repo),
                "rev-parse",
                "--verify",
                f"{candidate}^{{commit}}",
            ),
            capture_output=True,
        )
        if p.returncode == 0:
            return candidate
    run_git(
        repo,
        "rev-parse",
        "--verify",
        f"{remote}/{branch}^{{commit}}",
    )
    return f"{remote}/{branch}"


def load_skip_prefixes(path: Path) -> list[str]:
    if not path.is_file():
        sys.stderr.write(f"Skip file not found: {path}\n")
        raise SystemExit(1)
    out: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        out.append(line)
    return out


def path_matches_skip(path_str: str, prefixes: Sequence[str]) -> bool:
    if not prefixes:
        return False
    s = path_str.replace("\\", "/")
    for pr in prefixes:
        p = pr.rstrip("/")
        if s == p or s == pr:
            return True
        if s.startswith(p + "/"):
            return True
    return False


def _file_list_from_show(repo: Path, commit: str) -> list[str]:
    out = run_git(
        repo,
        "show",
        "--pretty=format:",
        "--name-only",
        "--no-renames",
        commit,
    )
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def _file_lists_from_name_only_log(
    out: str,
) -> dict[str, list[str]]:
    """
    Parse `git log --name-only --format=%H` (lines: hash, then file paths, repeat).
    """
    by: dict[str, list[str]] = {}
    cur: str | None = None
    for line in out.splitlines():
        line = line.rstrip()
        if not line:
            continue
        if FULL_SHA1_RE.match(line):
            cur = line
            if cur not in by:
                by[cur] = []
        elif cur is not None:
            by[cur].append(line)
    return by


def all_paths_only_skipped_from_file_list(
    files: list[str] | None,
    skip_prefixes: list[str],
) -> bool:
    if not skip_prefixes:
        return False
    if files is None:
        return False
    if not files:
        return True
    return all(path_matches_skip(f, skip_prefixes) for f in files)


def list_commits_on_previous_not_ancestor_of_next(
    repo: Path,
    previous_ref: str,
    next_ref: str,
    since: str,
) -> list[CommitInfo]:
    """
    Commits reachable from *previous* since *since*, but not an ancestor of
    *next* (same as ``log previous ^next``). One ``git log``; replaces
    N× ``merge-base --is-ancestor`` and matches ``A ^B`` / ``A --not B``.
    """
    # %B + %ct: message and committer time (for sort / first output column)
    fmt = "%H%x00%B%x00%ct%x00"
    raw = run_git(
        repo,
        "log",
        previous_ref,
        f"^{next_ref}",
        f"--since={since}",
        "--reverse",
        "--format=" + fmt,
    )
    if not raw.strip():
        return []
    tokens = raw.rstrip("\n").rstrip("\x00").split("\x00")
    if len(tokens) % 3 != 0 and tokens:
        sys.stderr.write(
            "Warning: unexpected git log field count; messages may be incomplete.\n"
        )
    commits: list[CommitInfo] = []
    for i in range(0, len(tokens) - (len(tokens) % 3), 3):
        sha, fullm, cts = tokens[i], tokens[i + 1], tokens[i + 2]
        sha = (sha or "").strip()
        if not sha or len(sha) < 7:
            continue
        first = (fullm or "").split("\n", 1)[0]
        try:
            cti = int((cts or "0").strip() or 0)
        except ValueError:
            cti = 0
        commits.append(
            CommitInfo(sha=sha, subject=first, message=fullm or "", commit_ts=cti)
        )
    return commits


def _file_list_map_for_same_range(
    repo: Path,
    previous_ref: str,
    next_ref: str,
    since: str,
) -> dict[str, list[str]]:
    """
    One ``git log`` over ``previous`` ``^next`` with same ``--since`` as
    the message list; per-commit file paths. Merge commits may be empty
    in ``--name-only``; caller may fall back to ``git show`` for those SHAs.
    """
    out = run_git(
        repo,
        "log",
        previous_ref,
        f"^{next_ref}",
        f"--since={since}",
        "--reverse",
        "--name-only",
        "--no-renames",
        "--pretty=format:%H",
    )
    return _file_lists_from_name_only_log(out)


def extract_issue_ids(text: str) -> frozenset[str]:
    return frozenset(ISSUE_RE.findall(text or ""))


def build_ref_issue_set(
    repo: Path,
    ref: str,
    since: str | None,
) -> frozenset[str]:
    """
    Issue/PR # ids in commit messages on *ref* (e.g. destination or base).
    If *since* is set, only commits from that date (git log --since) are
    considered; if None, the full history of *ref* is scanned.
    """
    args: list[str] = ["log", ref, "--format=%B"]
    if since is not None:
        args.append(f"--since={since}")
    raw = run_git(repo, *args)
    return frozenset(ISSUE_RE.findall(raw))


# Backwards name for call sites
def build_next_ref_issue_set(
    repo: Path,
    next_ref: str,
    next_since: str | None,
) -> frozenset[str]:
    return build_ref_issue_set(repo, next_ref, next_since)


def _resolve_file_lists_with_fallback(
    repo: Path,
    commits: list[CommitInfo],
    file_map: dict[str, list[str]],
    skip_prefixes: list[str],
    file_workers: int,
) -> dict[str, list[str]]:
    """
    Build per-SHA file lists from a ``--name-only`` map; for missing/empty
    records (merge quirks), use ``git show`` in a small thread pool.
    """
    if not skip_prefixes:
        return {}
    need_show: set[str] = set()
    for c in commits:
        fl = file_map.get(c.sha, None)
        if fl is not None and len(fl) > 0:
            continue
        # Missing, or name-only is empty: needs ``show`` to match the old
        # single-commit path (merge and empty commits).
        need_show.add(c.sha)
    resolved: dict[str, list[str]] = dict(file_map)
    if need_show:
        def show_files(sha: str) -> tuple[str, list[str]]:
            return (sha, _file_list_from_show(repo, sha))

        n = len(need_show)
        w = min(max(1, file_workers), 64)
        with ThreadPoolExecutor(
            max_workers=w,
        ) as ex:
            for _sha, fls in ex.map(
                show_files, sorted(need_show), chunksize=max(1, n // 8)
            ):
                resolved[_sha] = fls
    return {c.sha: list(resolved.get(c.sha) or []) for c in commits}


def find_probable_missing(
    repo: Path,
    previous_ref: str,
    next_ref: str,
    since: str,
    next_since: str | None,
    skip_prefixes: list[str],
    file_workers: int = _DEFAULT_FILE_WORKERS,
    base_ref: str | None = None,
    base_since: str | None = None,
) -> list[CommitInfo]:
    """
    Uses a single range ``log previous ^next`` (and optional second ``log``
    for name-only) instead of N× ``merge-base --is-ancestor`` and N×
    ``git show``. Fetches the destination (and optional base) issue set in
    parallel with the range work.
    """
    def do_next() -> frozenset[str]:
        return build_ref_issue_set(repo, next_ref, next_since)

    def do_base() -> frozenset[str]:
        assert base_ref is not None
        return build_ref_issue_set(repo, base_ref, base_since)

    def do_commits() -> list[CommitInfo]:
        return list_commits_on_previous_not_ancestor_of_next(
            repo, previous_ref, next_ref, since
        )

    def do_name_map() -> dict[str, list[str]]:
        if not skip_prefixes:
            return {}
        return _file_list_map_for_same_range(
            repo, previous_ref, next_ref, since
        )

    n_tasks = 1 + (1 if base_ref is not None else 0) + (1 if skip_prefixes else 0) + 1
    with ThreadPoolExecutor(max_workers=n_tasks) as ex:
        fut_n = ex.submit(do_next)
        fut_b = ex.submit(do_base) if base_ref is not None else None
        fut_c = ex.submit(do_commits)
        fut_m = ex.submit(do_name_map) if skip_prefixes else None
        next_issues = fut_n.result()
        base_issues: frozenset[str] = (
            fut_b.result() if fut_b is not None else frozenset()
        )
        commits = fut_c.result()
        file_map = fut_m.result() if fut_m is not None else {}

    file_by: dict[str, list[str]] = _resolve_file_lists_with_fallback(
        repo, commits, file_map, skip_prefixes, file_workers
    )

    out: list[CommitInfo] = []
    for c in commits:
        if skip_prefixes:
            if all_paths_only_skipped_from_file_list(
                file_by.get(c.sha, []), skip_prefixes
            ):
                continue
        prev_ids = extract_issue_ids(c.message)
        if prev_ids and prev_ids <= next_issues:
            continue
        if base_ref is not None:
            if is_ancestor(repo, c.sha, base_ref):
                continue
            if prev_ids and prev_ids <= base_issues:
                continue
        out.append(c)
    out.sort(key=lambda c: (c.commit_ts, c.sha))
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="List commits on the previous branch that are probably "
        "missing from the next (destination) branch."
    )
    p.add_argument(
        "repo",
        type=Path,
        help="Path to the git repository",
    )
    p.add_argument(
        "--remote",
        default="upstream",
        help="Remote name for resolving short branch names (default: upstream)",
    )
    p.add_argument(
        "previous",
        help="Source branch (commits considered here, compared to 'next')",
    )
    p.add_argument(
        "next",
        help="Destination branch: commits that appear here (by rules) are not reported",
    )
    p.add_argument(
        "since",
        help="Start date (passed to git log --since=), e.g. 2024-01-01 or '2024-01-01 00:00:00'",
    )
    p.add_argument(
        "--skip-file",
        type=Path,
        help="File with path prefixes to ignore: commits touching only those "
        "paths are not considered missing (one prefix per line, # for comments)",
    )
    p.add_argument(
        "--next-since",
        default=None,
        metavar="DATE",
        help="Only commit messages on the destination from this date are used to "
        "match #... links (git log --since). Default: same as the 'since' argument",
    )
    p.add_argument(
        "--all-next-issues",
        action="store_true",
        help="When matching #... links, scan the full history of the destination "
        "branch (ignore --next-since and use all commits on the branch for # ids)",
    )
    p.add_argument(
        "--base",
        default=None,
        metavar="REF",
        help="Optional third branch: commits already present on it (same commit id "
        "in history, or the same #… as in a git log of this ref) are not reported",
    )
    p.add_argument(
        "--base-since",
        default=None,
        metavar="DATE",
        help="Only base commit messages from this date are used for #… matching. "
        "Default when --base is set: same as the main 'since' date. "
        "Ignored with --all-base-issues",
    )
    p.add_argument(
        "--all-base-issues",
        action="store_true",
        help="When matching #… on the base ref, scan its full history for issue ids",
    )
    p.add_argument(
        "--no-fetch",
        action="store_true",
        help="Do not run git fetch: use only local refs (no contact with the remote). "
        "The requested branches must already be present, or you must use full ref names.",
    )
    p.add_argument(
        "--file-workers",
        type=int,
        default=_DEFAULT_FILE_WORKERS,
        metavar="N",
        help="Parallel ``git show`` invocations for skip-path fallbacks (merge/empty "
        f"``--name-only``); 1–64, default { _DEFAULT_FILE_WORKERS }",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    repo = args.repo.resolve()
    if not (repo / ".git").is_dir() and not (repo / ".git").is_file():
        sys.stderr.write(
            f"Not a git repository (no .git): {repo}\n"
        )
        raise SystemExit(1)

    skip: list[str] = []
    if args.skip_file is not None:
        skip = load_skip_prefixes(args.skip_file.resolve())

    if not args.no_fetch:
        fetch_branches_for_analysis(
            repo,
            args.remote,
            args.previous,
            args.next,
            base_branch=args.base,
        )

    previous_ref = resolve_ref(repo, args.remote, args.previous)
    next_ref = resolve_ref(repo, args.remote, args.next)
    base_ref: str | None = None
    if args.base is not None:
        base_ref = resolve_ref(repo, args.remote, args.base)

    next_for_issues: str | None
    if args.all_next_issues:
        next_for_issues = None
    elif args.next_since is not None:
        next_for_issues = args.next_since
    else:
        next_for_issues = args.since

    if base_ref is not None:
        if args.all_base_issues:
            base_for_issues: str | None = None
        elif args.base_since is not None:
            base_for_issues = args.base_since
        else:
            base_for_issues = args.since
    else:
        base_for_issues = None

    w = min(max(1, args.file_workers), 64)
    missing = find_probable_missing(
        repo,
        previous_ref,
        next_ref,
        args.since,
        next_for_issues,
        skip,
        file_workers=w,
        base_ref=base_ref,
        base_since=base_for_issues,
    )
    for c in missing:
        tstr = datetime.fromtimestamp(
            c.commit_ts, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"{tstr}\t{c.sha}\t{c.subject}")


if __name__ == "__main__":
    main()
