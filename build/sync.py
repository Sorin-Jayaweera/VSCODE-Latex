#!/usr/bin/env python3
"""
sync.py -- Commit and push this workspace to GitHub.

Safe to run on a timer: it does nothing when there is nothing to commit, and
it refuses to act in the middle of a merge or rebase rather than making a mess.

    python build/sync.py                 # commit changes and push
    python build/sync.py --message "..."  # custom commit message
    python build/sync.py --dry-run
    python build/sync.py --pull-only     # just fetch and rebase
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args, check=True, quiet=False):
    proc = subprocess.run(
        ["git"] + list(args),
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        errors="replace",
    )
    if check and proc.returncode != 0:
        if not quiet:
            sys.stderr.write((proc.stdout or "") + (proc.stderr or ""))
        raise SystemExit("git %s failed (%d)" % (" ".join(args), proc.returncode))
    return proc.stdout.strip()


def in_progress():
    """True if a merge, rebase, cherry-pick or bisect is half-finished."""
    gitdir = ROOT / ".git"
    markers = [
        "MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD",
        "BISECT_LOG", "rebase-merge", "rebase-apply",
    ]
    return [m for m in markers if (gitdir / m).exists()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pull-only", action="store_true")
    ap.add_argument("--no-pull", action="store_true")
    args = ap.parse_args()

    if not (ROOT / ".git").exists():
        raise SystemExit("Not a git repository: %s" % ROOT)

    stuck = in_progress()
    if stuck:
        raise SystemExit(
            "A git operation is already in progress (%s).\n"
            "Finish or abort it before syncing." % ", ".join(stuck)
        )

    def rebase_onto_remote():
        """Replay local commits on top of GitHub. Requires a clean tree."""
        if args.no_pull:
            return
        git("fetch", "origin", quiet=True)
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        remote = git("rev-parse", "--verify", "--quiet",
                     "origin/%s" % branch, check=False)
        if not remote:
            return
        proc = subprocess.run(
            ["git", "rebase", "origin/%s" % branch],
            cwd=str(ROOT), capture_output=True, text=True, errors="replace",
        )
        if proc.returncode != 0:
            subprocess.run(["git", "rebase", "--abort"], cwd=str(ROOT),
                           capture_output=True)
            detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
            raise SystemExit(
                "Could not rebase onto origin/%s. Your commits conflict with "
                "what is on GitHub; resolve by hand.\n\n%s"
                % (branch, "\n".join(detail.splitlines()[:8]))
            )

    if args.pull_only:
        if git("status", "--porcelain"):
            raise SystemExit(
                "You have uncommitted changes. Commit them first "
                "(just run sync.py with no flags), or stash them."
            )
        rebase_onto_remote()
        print("Pulled.")
        return 0

    status = git("status", "--porcelain")
    if not status:
        rebase_onto_remote()
        # Still push if we have local commits that never made it up.
        ahead = git("rev-list", "--count", "@{upstream}..HEAD", check=False)
        if ahead and ahead != "0":
            if args.dry_run:
                print("Would push %s existing commit(s)." % ahead)
                return 0
            git("push")
            print("Pushed %s existing commit(s)." % ahead)
        else:
            print("Nothing to sync.")
        return 0

    changed = len(status.splitlines())
    if args.dry_run:
        print("Would commit %d change(s):" % changed)
        for line in status.splitlines()[:20]:
            print("   ", line)
        return 0

    message = args.message or (
        "Notes sync %s" % datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    # Commit first, THEN rebase: git refuses to rebase a dirty working tree.
    git("add", "-A")
    git("commit", "-m", message)
    rebase_onto_remote()
    git("push")
    print("Synced %d change(s): %s" % (changed, message))
    return 0


if __name__ == "__main__":
    sys.exit(main())
