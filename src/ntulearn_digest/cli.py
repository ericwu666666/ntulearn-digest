"""Command line entry point: ntulearn auth | sync | build | classes | demo"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from . import __version__
from .auth import AuthError, load_token, minutes_left, normalize_token, prompt_token, read_clipboard, save_token
from .build import build_outputs, load_events
from .client import ApiError, Blackboard
from .crawl import sync as run_sync
from .report import diff_snapshots
from .schedule import class_meetings, fetch_schedule_html, parse_schedule, select_rows
from .util import from_iso, get_tz, read_json, write_json

DEFAULT_BASE = "https://ntulearn.ntu.edu.sg"
DEFAULT_OUT = "ntulearn-output"
DEFAULT_TZ = "Asia/Singapore"


def _say(msg: str) -> None:
    print(msg, flush=True)


def cmd_auth(args) -> int:
    if args.stdin:
        raw = sys.stdin.read()
    else:
        raw = read_clipboard() if args.clipboard else prompt_token()
    token = normalize_token(raw)
    bb = Blackboard(args.base_url, token, retries=2)
    try:
        me = bb.get("users/me")
    except ApiError as e:
        _say(f"token 验证失败（HTTP {e.status}）。请在已登录的 NTULearn 标签页重新复制。")
        return 1
    path = save_token(token, Path(args.token_file) if args.token_file else None)
    left = minutes_left(token)
    name = (me.get("name") or {}).get("given") or me.get("userName") or "你"
    _say(f"已登录：{name}。token 保存在 {path}（仅本机可读）" + (f"，大约还能用 {left} 分钟。" if left is not None else "。"))
    return 0


def _client(args) -> Blackboard:
    token = load_token(path=Path(args.token_file) if args.token_file else None)
    left = minutes_left(token)
    if left is not None and left <= 0:
        raise AuthError("token 已过期（大约 1 小时有效）。重新复制后运行 `ntulearn auth`。")
    return Blackboard(args.base_url, token)


def _build(out: Path, tz_name: str, diff: Optional[dict] = None) -> int:
    snapshot = read_json(out / "snapshot.json")
    if not snapshot:
        _say(f"{out}/snapshot.json 不存在，先运行 `ntulearn sync`。")
        return 1
    if diff is None:
        diff = read_json(out / "changes.json")
    events = load_events(out / "events.json")
    classes = read_json(out / "classes.json", default=[]) or []
    written = build_outputs(out, snapshot, diff, events, classes, tz_name)
    _say("已生成：")
    for p in written.values():
        _say(f"  {p}")
    return 0


def _print_urgent(out: Path, tz_name: str) -> None:
    items = read_json(out / "items.json", default=[]) or []
    tz = get_tz(tz_name)
    now = datetime.now(timezone.utc).astimezone(tz)
    urgent = [i for i in items if i["kind"] in ("deadline", "exam") and not i.get("done")
              and now <= from_iso(i["start"], tz) <= now + timedelta(days=3)]
    if urgent:
        _say("\n三天内：")
        for i in urgent:
            _say(f"  {from_iso(i['start'], tz):%m/%d %H:%M}  {i['title']}")


def cmd_sync(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bb = _client(args)
    old = read_json(out / "snapshot.json")
    snapshot = run_sync(bb, out, term=args.term, all_terms=args.all_terms, download=not args.no_download,
                        workers=args.workers, log=_say, only=args.course)
    if old:
        hist = out / "history"
        hist.mkdir(exist_ok=True)
        stamp = (old.get("generated_at") or "old").replace(":", "").replace("-", "")[:15]
        shutil.copyfile(out / "snapshot.json", hist / f"snapshot-{stamp}.json")
        for extra in sorted(hist.glob("snapshot-*.json"))[:-20]:
            extra.unlink()
    diff = diff_snapshots(old, snapshot)
    write_json(out / "snapshot.json", snapshot)
    write_json(out / "changes.json", diff)
    _say(f"同步完成，共 {bb.requests} 次请求。")
    code = _build(out, args.tz, diff)
    _print_urgent(out, args.tz)
    return code


def cmd_build(args) -> int:
    code = _build(Path(args.out), args.tz)
    if code == 0:
        _print_urgent(Path(args.out), args.tz)
    return code


def cmd_classes(args) -> int:
    out = Path(args.out)
    week1 = date.fromisoformat(args.week1)
    if week1.weekday() != 0:
        _say("--week1 需要是教学第 1 周的周一。")
        return 1
    skip = [date.fromisoformat(x) for x in args.skip.split(",")] if args.skip else []
    meetings: List[dict] = []
    for spec in args.courses:
        code, _, sel = spec.partition(":")
        rows = parse_schedule(fetch_schedule_html(code, args.acadsem))
        if not rows:
            _say(f"{code}：课表里没找到，检查课程代码和 --acadsem。")
            continue
        index = sel if sel.isdigit() else None
        groups = [g for g in sel.split(",") if g] if sel and not sel.isdigit() else None
        picked = select_rows(rows, code, index=index, groups=groups)
        if not picked:
            options = sorted({f"{r['index']} {r['type']} {r['group']}" for r in rows if r["code"] == code.upper()})
            _say(f"{code}：没有匹配 {sel!r} 的课。可选：" + "；".join(options[:12]))
            continue
        _say(f"{code}：" + "；".join(f"{r['type']} {r['group']} {r['day']} {r['start']}-{r['end']} {r['venue']}" for r in picked))
        meetings += class_meetings(picked, week1, args.recess_after, skip)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "classes.json", meetings)
    _say(f"写入 {len(meetings)} 次课到 {out / 'classes.json'}")
    return _build(out, args.tz) if (out / "snapshot.json").exists() else 0


def cmd_demo(args) -> int:
    from .demo import demo_data

    out = Path(args.out)
    tz = get_tz(args.tz)
    now = datetime.now(timezone.utc).astimezone(tz)
    old, new, events, classes = demo_data(now)
    write_json(out / "snapshot.json", new)
    write_json(out / "events.json", {"events": events})
    write_json(out / "classes.json", classes)
    written = build_outputs(out, new, diff_snapshots(old, new), events, classes, args.tz, now=now)
    _say("示例数据（全部虚构）已生成：")
    for p in written.values():
        _say(f"  {p}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ntulearn", description="把 NTULearn 整理成日历、看板和 AI 可读的笔记。")
    p.add_argument("--version", action="version", version=f"ntulearn-digest {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-o", "--out", default=DEFAULT_OUT, help=f"输出文件夹（默认 {DEFAULT_OUT}）")
    common.add_argument("--tz", default=DEFAULT_TZ, help=f"时区（默认 {DEFAULT_TZ}）")
    net = argparse.ArgumentParser(add_help=False)
    net.add_argument("--base-url", default=DEFAULT_BASE, help="Blackboard Ultra 网址")
    net.add_argument("--token-file", help="token 文件位置（默认 ~/.config/ntulearn-digest/token）")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("auth", parents=[net], help="保存从浏览器复制的 token")
    a.add_argument("--clipboard", action="store_true", help="直接从剪贴板读取")
    a.add_argument("--stdin", action="store_true", help="从标准输入读取（给脚本或 AI 助手用）")
    a.set_defaults(func=cmd_auth)

    s = sub.add_parser("sync", parents=[common, net], help="抓取课程、文件、成绩簿、公告，并生成全部输出")
    s.add_argument("--term", help="学期代码，如 26S1（默认自动选最新学期）")
    s.add_argument("--all-terms", action="store_true", help="不过滤学期")
    s.add_argument("--course", action="append", metavar="CODE", help="只同步这门课，可重复，如 --course HE3001")
    s.add_argument("--no-download", action="store_true", help="只抓数据，不下载文件")
    s.add_argument("--workers", type=int, default=4, help="并发数（默认 4，请不要调太高）")
    s.set_defaults(func=cmd_sync)

    b = sub.add_parser("build", parents=[common], help="只根据已有数据重新生成日历和看板（改完 events.json 后用）")
    b.set_defaults(func=cmd_build)

    c = sub.add_parser("classes", parents=[common], help="从 NTU 公开课表生成每周上课时间")
    c.add_argument("courses", nargs="+", help="课程代码:index 或 课程代码:组别，如 HE3001:19541 或 HW0218:GP12")
    c.add_argument("--acadsem", required=True, help="学年;学期，如 2026;1")
    c.add_argument("--week1", required=True, help="教学第 1 周的周一，如 2026-08-10")
    c.add_argument("--recess-after", type=int, default=7, help="第几周之后是 recess week（默认 7）")
    c.add_argument("--skip", help="不上课的日期，逗号分隔，如公共假期 2026-11-09")
    c.set_defaults(func=cmd_classes)

    d = sub.add_parser("demo", parents=[common], help="用虚构数据生成示例输出，不需要账号")
    d.set_defaults(func=cmd_demo, out="demo-output")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except AuthError as e:
        _say(str(e))
        return 2
    except ApiError as e:
        if e.status == 401:
            _say("NTULearn 拒绝了 token（401），多半是过期了。重新复制后运行 `ntulearn auth`。")
            return 2
        _say(f"请求失败：{e}")
        return 1
    except KeyboardInterrupt:
        _say("已中断。")
        return 130
