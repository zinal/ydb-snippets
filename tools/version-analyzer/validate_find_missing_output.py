#!/usr/bin/env python3
"""
External validation of ``find_missing_commits.py`` output using ``git`` directly.

Checks (commit SHA parsed from each line: ``time TAB sha TAB subject`` or
legacy ``sha TAB subject``; subject is ignored):
1) Every output SHA appears in
   ``git log <previous> ^<next> --since=<date> --format=%H`` (candidate set).
2) ``git merge-base --is-ancestor <sha> <next>`` fails (commit not in dest history).
3) ``git merge-base --is-ancestor <sha> <previous>`` succeeds (commit is on source).

Optional:
4) ``--recompute-expected`` — same SHA set as ``find_probable_missing`` (same rules).
5) With ``--base``, no output SHA may be an ancestor of the base ref (same id on base).
6) ``--self-check-outputs`` — heuristic using ``git show`` paths + next/base ``git log``
   for # ids (may disagree on rare merges; informational).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_TOOL_DIR = Path(__file__).resolve().parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from find_missing_commits import (  # noqa: E402
    build_ref_issue_set,
    find_probable_missing,
    load_skip_prefixes,
    resolve_ref,
)

ISSUE_RE = re.compile(r"#([0-9]+)")


def run_git(repo: Path, *args: str) -> str:
    p = subprocess.run(
        ("git", "-C", str(repo), *args),
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        sys.stderr.write(
            f"git failed ({p.returncode}): {' '.join(args)}\n{p.stderr or p.stdout}\n"
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
    sys.stderr.write(p.stderr or "")
    raise SystemExit(p.returncode)


def candidate_shas(
    repo: Path,
    previous_ref: str,
    next_ref: str,
    since: str,
) -> set[str]:
    out = run_git(
        repo,
        "log",
        previous_ref,
        f"^{next_ref}",
        f"--since={since}",
        "--format=%H",
    )
    return {ln.strip() for ln in out.splitlines() if len(ln.strip()) >= 7}


def build_next_issue_set_external(
    repo: Path,
    next_ref: str,
    next_since: str | None,
) -> set[str]:
    args: list[str] = ["log", next_ref, "--format=%B"]
    if next_since is not None:
        args.append(f"--since={next_since}")
    raw = run_git(repo, *args)
    return set(ISSUE_RE.findall(raw))


def all_paths_match_skip(
    files: list[str],
    skip_prefixes: list[str],
) -> bool:
    if not files:
        return True
    for f in files:
        s = f.replace("\\", "/")
        ok = False
        for pr in skip_prefixes:
            p = pr.rstrip("/")
            if s == p or s == pr or s.startswith(p + "/"):
                ok = True
                break
        if not ok:
            return False
    return True


def file_list_from_show(repo: Path, sha: str) -> list[str]:
    out = run_git(
        repo, "show", "--pretty=format:", "--name-only", "--no-renames", sha
    )
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def message_from_show(repo: Path, sha: str) -> str:
    return run_git(repo, "show", "-s", "--format=%B", sha)


def _sha_from_output_line(line: str) -> str:
    """
    New: ``<committer-iso>T…Z`` TAB 40-hex SHA TAB subject.
    Legacy: SHA TAB subject.
    """
    parts = [p.strip() for p in line.split("\t") if p is not None]
    if not parts:
        return ""
    p0 = parts[0]
    if len(parts) >= 2 and re.match(
        r"^\d{4}-\d{2}-\d{2}T", p0
    ):
        cand = parts[1]
    else:
        cand = parts[0]
    if re.match(r"^[0-9a-fA-F]{7,40}$", cand, re.IGNORECASE):
        return cand.lower() if len(cand) == 40 else cand
    return ""


def parse_output_lines(text: str) -> list[str]:
    shas: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        sha = _sha_from_output_line(line)
        if not sha or not re.match(
            r"^[0-9a-fA-F]{7,40}$", sha, re.IGNORECASE
        ):
            sys.stderr.write(
                f"Line {i}: could not parse commit SHA: {line!r}\n"
            )
            raise SystemExit(1)
        shas.append(sha)
    return shas


def load_output_shas(path: Path | None, repo: Path) -> list[str]:
    text = path.read_text() if path is not None else sys.stdin.read()
    shas = parse_output_lines(text)
    out: list[str] = []
    for s in shas:
        out.append(run_git(repo, "rev-parse", s).strip())
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Validate find_missing_commits.py output with raw git checks."
    )
    ap.add_argument("repo", type=Path, help="Path to git repository")
    ap.add_argument("--remote", default="upstream", help="Remote for ref resolution")
    ap.add_argument("previous", help="Source branch (same as main tool)")
    ap.add_argument("next", help="Destination branch")
    ap.add_argument("since", help="--since= date (same as main tool)")
    ap.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=None,
        help="File from find_missing_commits (sha TAB subject). Omit: read stdin.",
    )
    ap.add_argument(
        "--skip-file",
        type=Path,
        default=None,
        help="Same as main tool; used for --recompute-expected",
    )
    ap.add_argument(
        "--next-since",
        default=None,
        metavar="DATE",
    )
    ap.add_argument(
        "--all-next-issues",
        action="store_true",
    )
    ap.add_argument(
        "--base",
        default=None,
        metavar="REF",
    )
    ap.add_argument(
        "--base-since",
        default=None,
        metavar="DATE",
    )
    ap.add_argument(
        "--all-base-issues",
        action="store_true",
    )
    ap.add_argument(
        "--recompute-expected",
        action="store_true",
    )
    ap.add_argument(
        "--self-check-outputs",
        action="store_true",
    )
    ap.add_argument(
        "--file-workers",
        type=int,
        default=16,
    )
    args = ap.parse_args()
    repo = args.repo.resolve()

    skip: list[str] = []
    if args.skip_file is not None:
        skip = load_skip_prefixes(args.skip_file.resolve())

    out_shas = load_output_shas(args.output, repo)
    previous_ref = resolve_ref(repo, args.remote, args.previous)
    next_ref = resolve_ref(repo, args.remote, args.next)
    base_ref: str | None = None
    if args.base is not None:
        base_ref = resolve_ref(repo, args.remote, args.base)
    if args.all_next_issues:
        next_for_issues: str | None = None
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

    cand = candidate_shas(repo, previous_ref, next_ref, args.since)
    errs: list[str] = []
    for sha in out_shas:
        if sha not in cand:
            errs.append(
                f"{sha}: not in raw candidate set (git log {previous_ref!r} ^{next_ref!r} --since)"
            )
        if is_ancestor(repo, sha, next_ref):
            errs.append(
                f"{sha}: is ancestor of {next_ref!r} — should not be reported as missing"
            )
        if not is_ancestor(repo, sha, previous_ref):
            errs.append(
                f"{sha}: is not an ancestor of {previous_ref!r} — not on source branch"
            )
        if base_ref is not None:
            if is_ancestor(repo, sha, base_ref):
                errs.append(
                    f"{sha}: is on base {base_ref!r} (same id) — should be filtered as present on base"
                )
    if errs:
        sys.stderr.write("External git checks failed:\n")
        for e in errs:
            sys.stderr.write(f"  {e}\n")
        raise SystemExit(1)

    extra = ""
    if base_ref is not None:
        extra = f" Also: not the same object as an ancestor of {base_ref!r} when --base is used."
    print(
        f"OK: {len(out_shas)} SHAs: each is in the candidate set, is not an "
        f"ancestor of {next_ref!r}, and is on {previous_ref!r}.{extra}"
    )

    if args.recompute_expected:
        w = min(max(1, args.file_workers), 64)
        expect = find_probable_missing(
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
        e_set = {c.sha for c in expect}
        o_set = set(out_shas)
        if e_set != o_set:
            only_o = sorted(o_set - e_set)[:10]
            only_e = sorted(e_set - o_set)[:10]
            sys.stderr.write("SHA set != find_probable_missing recompute.\n")
            if only_o:
                sys.stderr.write(
                    f"  In file only (showing up to 10): {only_o!r}\n"
                )
            if only_e:
                sys.stderr.write(
                    f"  In recompute only (showing up to 10): {only_e!r}\n"
                )
            raise SystemExit(1)
        print(
            f"OK: recompute-expected: matches find_probable_missing ({len(e_set)} SHAs)."
        )

    if args.self_check_outputs and (skip or base_ref is not None):
        n_issues = build_next_issue_set_external(
            repo, next_ref, next_for_issues
        )
        b_issues: set[str] = set()
        if base_ref is not None:
            b_issues = set(
                build_ref_issue_set(repo, base_ref, base_for_issues)
            )
        bad: list[str] = []
        for sha in out_shas:
            if skip and all_paths_match_skip(
                file_list_from_show(repo, sha), skip
            ):
                bad.append(
                    f"{sha}: all paths under skip (git show) — tool may use batched name-only; check if merge"
                )
            msg = message_from_show(repo, sha)
            ids = set(ISSUE_RE.findall(msg))
            if ids and ids.issubset(n_issues):
                bad.append(
                    f"{sha}: issue id(s) {ids} all on next in issue window"
                )
            if base_ref is not None and ids and ids.issubset(b_issues):
                bad.append(
                    f"{sha}: issue id(s) {ids} all on base in # scan — should be filtered as present on base"
                )
        if bad:
            for b in bad[:40]:
                sys.stderr.write(f"self-check note: {b}\n")
            if len(bad) > 40:
                sys.stderr.write(
                    f"... {len(bad) - 40} more (merge/path differences possible)\n"
                )
        else:
            print(
                "OK: self-check-outputs: no sha-only obvious contradictions with "
                "git show + next/base # scan."
            )


if __name__ == "__main__":
    main()
