"""Validate all GitHub Actions workflow YAML files (run before every push).

The 2026 trap: a colon inside a quoted default in a ${{ }} expression breaks
the whole workflow silently (all triggers die, GitHub shows the file path as
the workflow name). This catches that class of bug.
"""
import glob
import sys

try:
    import yaml
except ImportError:
    print("pyyaml not installed -> pip install pyyaml")
    sys.exit(2)

REQUIRED_JOBS = {"jobs"}
KNOWN_TRIGGERS = {
    "schedule",
    "workflow_dispatch",
    "repository_dispatch",
    "push",
    "pull_request",
    "workflow_call",
}


def main() -> int:
    bad = 0
    files = sorted(glob.glob(".github/workflows/*.yml") + glob.glob(".github/workflows/*.yaml"))
    if not files:
        print("no workflow files found")
        return 0
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                d = yaml.safe_load(fh)
        except Exception as e:
            print(f"YAML FAIL  {f}: {str(e)[:160]}")
            bad += 1
            continue
        if not isinstance(d, dict) or not REQUIRED_JOBS & d.keys():
            print(f"NO JOBS    {f}")
            bad += 1
            continue
        on = d.get(True, d.get("on", {}))
        trig = list(on.keys()) if isinstance(on, dict) else []
        unknown = set(trig) - KNOWN_TRIGGERS
        if unknown:
            print(f"BAD TRIGGER {f}: {sorted(unknown)}")
            bad += 1
        if not isinstance(d.get("name"), str) or "/" in str(d.get("name", "")):
            print(f"BAD NAME   {f}: name={d.get('name')!r} (file path leaked into name)")
            bad += 1
        print(
            f"ok {f.split('/')[-1]:<22} name={d.get('name'):<18} "
            f"triggers={','.join(trig) or '-'}"
        )
    if bad:
        print(f"\n{bad} workflow file(s) BROKEN - do not push")
        return 1
    print(f"\nall {len(files)} workflows valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
