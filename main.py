import argparse
import json
import sys
from pathlib import Path
import config
import state


def cmd_short(_args):
    _run_kind("short")


def cmd_long(_args):
    _run_kind("long")


def _run_kind(kind: str):
    from runner import run_one

    try:
        rec = run_one(kind)
        print(json.dumps(rec, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"FAILED [{kind}]: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_plan(args):
    from pipeline.plan import run as plan_run

    ideas = plan_run(args.count)
    print(json.dumps(ideas, indent=2, ensure_ascii=False))


def cmd_dashboard(_args):
    import runpy
    import sys as _sys

    _sys.path.insert(0, str(config.ROOT))
    runpy.run_path(str(config.ROOT / "dashboard" / "app.py"), run_name="__main__")


def cmd_retry(args):
    from runner import run_one

    rec = state.get(args.id)
    if not rec:
        print(f"no record {args.id}", file=sys.stderr)
        sys.exit(1)
    kind = rec.get("kind", "short")
    state.update(args.id, status="retry_queued", error="")
    try:
        new_rec = run_one(kind)
        print(json.dumps(new_rec, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"retry failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_delete(args):
    from pipeline import upload as upload_mod

    try:
        upload_mod.delete_video(args.id)
        print(f"deleted {args.id}")
    except Exception as e:
        print(f"delete failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_sync(_args):
    import subprocess

    subprocess.run(["git", "fetch", "origin", "logs"], capture_output=True)
    proc = subprocess.run(
        ["git", "show", "origin/logs:state.json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        print("no logs branch state yet", file=sys.stderr)
        sys.exit(1)
    (config.ROOT / "state_from_logs.json").write_text(proc.stdout, encoding="utf-8")
    print(f"synced {len(proc.stdout)} chars from logs branch")


def cmd_bank_build(args):
    from pipeline import bank as bank_mod

    bank_mod.build(args.topics, args.per_topic, args.source)


def cmd_bank_list(_args):
    import json as _json
    from pipeline import bank as bank_mod

    print(_json.dumps(bank_mod.stats(), indent=2, ensure_ascii=False))


def cmd_backfill(args):
    import backfill as bf

    bf.backfill(args.max)


def cmd_burst(args):
    import backfill as bf

    bf.burst(args.count, args.kind)


def cmd_backfill(args):
    import backfill as bf

    bf.backfill(args.max)


def cmd_burst(args):
    import backfill as bf

    bf.burst(args.count, args.kind)


def cmd_accounts(args):
    from pipeline import yt_auth as yt

    for a in yt.check_all(force=args.force):
        status = "OK" if a["readonly_ok"] else ("TOKEN_OK" if a["token_ok"] else "FAIL")
        flag = f" DUPLICATE_OF_SLOT_{a['duplicate_of']}" if a.get("duplicate_of") else ""
        print(
            f"[slot {a['slot']}] {a['display']} <{a['email']}> :: {status}{flag} "
            f"subs={a['subs']} views={a['views']} videos={a['videos']} err={a['error']}"
        )


def cmd_status(_args):
    print(json.dumps(state.load(), indent=2, ensure_ascii=False))


def cmd_kill(_args):
    if config.KILL_FILE.exists():
        config.KILL_FILE.unlink()
        print("kill switch cleared")
    else:
        config.KILL_FILE.write_text("1", encoding="utf-8")
        print("kill switch ON")


def main():
    p = argparse.ArgumentParser(prog="moneyprint", description="ReZain YT autopilot")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("short", help="run one <60s video").set_defaults(fn=cmd_short)
    sub.add_parser("long", help="run one >5min video").set_defaults(fn=cmd_long)

    sp = sub.add_parser("plan", help="generate idea bank")
    sp.add_argument("--count", type=int, default=5)
    sp.set_defaults(fn=cmd_plan)

    sub.add_parser("dashboard", help="local log dashboard").set_defaults(fn=cmd_dashboard)
    ap = sub.add_parser("accounts", help="check YouTube login status")
    ap.add_argument("--force", action="store_true")
    ap.set_defaults(fn=cmd_accounts)

    bf = sub.add_parser("backfill", help="top-up channels to daily target")
    bf.add_argument("--max", type=int, default=40)
    bf.set_defaults(fn=cmd_backfill)
    bu = sub.add_parser("burst", help="make N videos back to back on this channel")
    bu.add_argument("count", type=int, nargs="?", default=3)
    bu.add_argument("--kind", default="short")
    bu.set_defaults(fn=cmd_burst)
    sub.add_parser("sync", help="pull state.json from logs branch").set_defaults(fn=cmd_sync)

    bp = sub.add_parser("bank-build", help="curate clips into bank/clips.json")
    bp.add_argument("--topics", nargs="*", default=None)
    bp.add_argument("--per-topic", type=int, default=10)
    bp.add_argument("--source", default="nasa", choices=["nasa", "commons"])
    bp.set_defaults(fn=cmd_bank_build)
    sub.add_parser("bank-list", help="show clip bank stats").set_defaults(fn=cmd_bank_list)
    sub.add_parser("status", help="dump state.json").set_defaults(fn=cmd_status)
    sub.add_parser("kill", help="toggle kill switch").set_defaults(fn=cmd_kill)

    rp = sub.add_parser("retry", help="rerun pipeline fresh for a failed id")
    rp.add_argument("id")
    rp.set_defaults(fn=cmd_retry)

    dp = sub.add_parser("delete", help="delete a YouTube video by id")
    dp.add_argument("id")
    dp.set_defaults(fn=cmd_delete)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
