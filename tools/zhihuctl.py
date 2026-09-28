#!/usr/bin/env python3
"""zhihu-lab 管理脚本。

命令：
  new      新建问题登记到 questions/inbox/
  validate 校验所有问题文件
  index    重建 questions/INDEX.md
  promote  inbox -> active（或 active -> answered）
  drop     移到 dropped/
  show     打印一个问题
  scan     定期检查：km-harness 有没有新条目可以用到哪些问题上

依赖 PyYAML。对 ../km-harness 只读。
"""
import argparse
import datetime
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("需要 PyYAML：pip3 install pyyaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QDIR = os.path.join(ROOT, "questions")
STATE = os.path.join(ROOT, "state", "scan.json")
KM = os.path.abspath(os.path.join(ROOT, "..", "km-harness", "knowledge"))

DIRS = {"inbox": "inbox", "active": "active", "answered": "answered", "dropped": "dropped"}
SERIES = {
    "S-01": "AI 嵌进工作流",
    "S-02": "治理思维",
    "S-03": "向上管理与方案沟通",
    "S-04": "复盘与个人操作系统",
    "S-05": "职业竞争力与生态位",
}
# km-harness 的 domain -> 本库系列。一个 domain 可落到多个系列。
DOMAIN_SERIES = {
    "S-01": ["Agent", "AI", "Skills", "Harness", "Loop", "工作流"],
    "S-02": ["团队管理", "变更管理", "稳定性", "监控", "SRE", "K8s", "精益敏捷", "架构"],
    "S-03": ["沟通", "汇报", "协作", "决策", "方案设计", "需求"],
    "S-04": ["复盘", "知识管理", "卡片笔记", "工作方法", "规划", "目标管理", "学习方法", "习惯", "阅读"],
    "S-05": ["职业发展", "个人成长", "心态", "升维思考", "优先级", "问题解决"],
}
SECTIONS = ["为什么适合", "回答角度", "可用条目", "竞品观察", "备注"]
URL_RE = re.compile(r"^https://www\.zhihu\.com/question/\d+")
TODAY = datetime.date.today().isoformat()


# ---------- 读写 ----------

def split_fm(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return None, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def load_questions():
    out = []
    for d in DIRS:
        p = os.path.join(QDIR, d)
        if not os.path.isdir(p):
            continue
        for fn in sorted(os.listdir(p)):
            if not fn.endswith(".md") or fn in ("SCHEMA.md", "REVIEW.md", "INDEX.md"):
                continue
            path = os.path.join(p, fn)
            fm, body = split_fm(open(path, encoding="utf-8").read())
            if fm is None:
                print(f"! 无 frontmatter：{path}", file=sys.stderr)
                continue
            out.append({"fm": fm, "body": body, "path": path, "dir": d, "file": fn})
    return out


def dump(q):
    fm = yaml.safe_dump(q["fm"], allow_unicode=True, sort_keys=False, default_flow_style=False)
    open(q["path"], "w", encoding="utf-8").write(f"---\n{fm}---\n{q['body']}")


def slug(s):
    s = re.sub(r"[\s/\\:*?\"<>|]+", "", s)
    return s[:40]


def next_id(qs):
    n = max([int(q["fm"]["id"].split("-")[1]) for q in qs] + [0])
    return f"Q-{n + 1:04d}"


# ---------- km-harness ----------

def load_km():
    """读 km-harness 条目。返回 {id: {...}}。只读。"""
    if not os.path.isdir(KM):
        return {}
    out = {}
    for sub in ("principles", "rules", "templates", "frameworks", "checklists"):
        p = os.path.join(KM, sub)
        if not os.path.isdir(p):
            continue
        for fn in os.listdir(p):
            if not fn.endswith(".md"):
                continue
            fm, _ = split_fm(open(os.path.join(p, fn), encoding="utf-8").read())
            if not fm or "id" not in fm:
                continue
            doms = fm.get("domains") or []
            if isinstance(doms, str):
                doms = [d.strip() for d in doms.strip("[]").split(",") if d.strip()]
            out[fm["id"]] = {
                "id": fm["id"],
                "title": fm.get("title", ""),
                "one_liner": fm.get("one_liner", ""),
                "domains": doms,
                "status": fm.get("status", ""),
                "updated": str(fm.get("updated", "")),
            }
    return out


def series_for(domains):
    hit = []
    for s, ds in DOMAIN_SERIES.items():
        if set(domains) & set(ds):
            hit.append(s)
    return hit


def read_state():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return {"last_scan": None, "entries": {}}


# ---------- 命令 ----------

def cmd_new(a):
    qs = load_questions()
    if not URL_RE.match(a.url):
        sys.exit("url 必须是 https://www.zhihu.com/question/<数字>；专栏 zhuanlan 不能回答")
    for q in qs:
        if q["fm"].get("url") == a.url:
            sys.exit(f"已存在：{q['fm']['id']} {q['fm']['title']}")
    qid = next_id(qs)
    fm = {
        "id": qid, "kind": "question", "title": a.title, "url": a.url,
        "series": a.series, "status": "inbox", "priority": a.priority,
        "followers": None, "answers_count": None, "checked": None,
        "matched_entries": a.entries.split(",") if a.entries else [],
        "angle": a.angle or "", "answer_id": None, "published_url": None,
        "created": TODAY, "updated": TODAY,
    }
    body = "\n" + "\n\n".join(f"## {s}\n" for s in SECTIONS)
    path = os.path.join(QDIR, "inbox", f"{qid}-{slug(a.title)}.md")
    dump({"fm": fm, "body": body, "path": path})
    print(f"创建 {path}")


def cmd_validate(a, quiet=False):
    qs = load_questions()
    km = load_km()
    errs, warns, seen = [], [], {}
    for q in qs:
        fm, f = q["fm"], q["file"]
        for k in ("id", "kind", "title", "url", "status", "priority", "created", "updated"):
            if k not in fm or fm[k] in (None, ""):
                errs.append(f"{f}: 缺字段 {k}")
        qid = fm.get("id", "")
        if qid in seen:
            errs.append(f"{f}: id 与 {seen[qid]} 重复")
        seen[qid] = f
        if not f.startswith(qid):
            errs.append(f"{f}: 文件名前缀与 id 不一致")
        if fm.get("status") != q["dir"]:
            errs.append(f"{f}: status={fm.get('status')} 与目录 {q['dir']}/ 不一致")
        if not URL_RE.match(str(fm.get("url", ""))):
            errs.append(f"{f}: url 不是知乎问题页")
        if fm.get("series") and fm["series"] not in SERIES:
            errs.append(f"{f}: series={fm['series']} 未定义")
        if fm.get("priority") not in ("P0", "P1", "P2"):
            errs.append(f"{f}: priority 必须是 P0/P1/P2")
        for s in SECTIONS:
            if f"## {s}" not in q["body"]:
                errs.append(f"{f}: 缺小节「{s}」")
        for e in fm.get("matched_entries") or []:
            if km and e not in km:
                errs.append(f"{f}: matched_entries 里的 {e} 在 km-harness 中不存在")
        if q["dir"] == "active" and not (fm.get("matched_entries") or []):
            warns.append(f"{f}: 已进 active 但没有 matched_entries")
        if q["dir"] == "active" and not fm.get("angle"):
            warns.append(f"{f}: 已进 active 但 angle 为空")
        if q["dir"] == "answered" and not fm.get("published_url"):
            warns.append(f"{f}: 已 answered 但没有 published_url")
    for w in warns:
        print("warn " + w)
    for e in errs:
        print("ERR  " + e)
    if not quiet:
        print(f"\n{len(qs)} 个问题，{len(errs)} 个错误，{len(warns)} 个提醒")
    return 1 if errs else 0


def cmd_index(a):
    qs = load_questions()
    km = load_km()
    L = ["# 知乎问题索引", "",
         f"生成时间：{datetime.datetime.now():%Y-%m-%d %H:%M}　由 `tools/zhihuctl.py index` 自动生成，请勿手改。", ""]

    cnt = {d: sum(1 for q in qs if q["dir"] == d) for d in DIRS}
    L += ["## 统计", "", "| 状态 | 数量 |", "|---|---|"]
    for d, label in (("inbox", "待评估 inbox"), ("active", "在写 active"),
                     ("answered", "已发布 answered"), ("dropped", "已放弃 dropped")):
        L.append(f"| {label} | {cnt[d]} |")
    L.append(f"| **合计** | **{len(qs)}** |")
    L.append("")

    for sid, sname in SERIES.items():
        sub = [q for q in qs if q["fm"].get("series") == sid and q["dir"] != "dropped"]
        if not sub:
            continue
        L += [f"## {sid}　{sname}（{len(sub)}）", "",
              "| 编号 | 优先级 | 状态 | 问题 | 可用条目 | 角度 |", "|---|---|---|---|---|---|"]
        for q in sorted(sub, key=lambda x: (x["fm"].get("priority", "P9"), x["fm"]["id"])):
            fm = q["fm"]
            rel = os.path.relpath(q["path"], QDIR)
            ents = "、".join(fm.get("matched_entries") or []) or "—"
            ang = (fm.get("angle") or "—").replace("|", "／")
            L.append(f"| [{fm['id']}]({rel}) | {fm['priority']} | {fm['status']} | "
                     f"[{fm['title']}]({fm['url']}) | {ents} | {ang} |")
        L.append("")

    misc = [q for q in qs if not q["fm"].get("series") and q["dir"] != "dropped"]
    if misc:
        L += ["## 未归系列", "", "| 编号 | 状态 | 问题 |", "|---|---|---|"]
        for q in misc:
            rel = os.path.relpath(q["path"], QDIR)
            L.append(f"| [{q['fm']['id']}]({rel}) | {q['fm']['status']} | "
                     f"[{q['fm']['title']}]({q['fm']['url']}) |")
        L.append("")

    dropped = [q for q in qs if q["dir"] == "dropped"]
    if dropped:
        L += ["## 已放弃", "", "| 编号 | 问题 | 原因 |", "|---|---|---|"]
        for q in dropped:
            rel = os.path.relpath(q["path"], QDIR)
            L.append(f"| [{q['fm']['id']}]({rel}) | {q['fm']['title']} | {q['fm'].get('drop_reason', '')} |")
        L.append("")

    # 条目使用度：哪些条目已经被用上，哪些还没
    used = {}
    for q in qs:
        if q["dir"] == "dropped":
            continue
        for e in q["fm"].get("matched_entries") or []:
            used.setdefault(e, []).append(q["fm"]["id"])
    if used:
        L += ["## 条目使用情况", "", "| 条目 | 标题 | 用在 |", "|---|---|---|"]
        for e in sorted(used):
            L.append(f"| {e} | {km.get(e, {}).get('title', '?')} | {'、'.join(used[e])} |")
        L.append("")

    open(os.path.join(QDIR, "INDEX.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"已写入 {os.path.join(QDIR, 'INDEX.md')}（{len(qs)} 个问题）")


def _move(qid, dest, extra=None):
    for q in load_questions():
        if q["fm"]["id"] == qid:
            q["fm"]["status"] = dest
            q["fm"]["updated"] = TODAY
            if extra:
                q["fm"].update(extra)
            new = os.path.join(QDIR, dest, q["file"])
            old = q["path"]
            q["path"] = new
            dump(q)
            if os.path.abspath(old) != os.path.abspath(new):
                os.remove(old)
            print(f"{qid} -> {dest}/")
            return
    sys.exit(f"找不到 {qid}")


def cmd_promote(a):
    cur = {q["fm"]["id"]: q["dir"] for q in load_questions()}.get(a.id)
    if cur is None:
        sys.exit(f"找不到 {a.id}")
    nxt = {"inbox": "active", "active": "answered"}.get(cur)
    if not nxt:
        sys.exit(f"{a.id} 当前在 {cur}/，无法继续 promote")
    extra = {"published_url": a.url} if (nxt == "answered" and a.url) else None
    if nxt == "answered" and not a.url:
        print("提醒：进 answered 建议同时用 --url 填发布链接")
    _move(a.id, nxt, extra)


def cmd_drop(a):
    _move(a.id, "dropped", {"drop_reason": a.reason})


def cmd_show(a):
    for q in load_questions():
        if q["fm"]["id"] == a.id:
            print(open(q["path"], encoding="utf-8").read())
            return
    sys.exit(f"找不到 {a.id}")


# 第一人称检查：「我」作为叙述者不得出现，见 CLAUDE.md「人称与口吻」。
# 允许的例外：引述读者内心话、引述他人原话、引用条目原文摘录。
FIRST_PERSON = re.compile(r"(?<![你他她自])我")
# 脱敏红线关键词，见 CLAUDE.md
REDLINE = re.compile(
    r"shoplazza|飞书|lark|open\.feishu|monitor\.|\.site|\.internal|"
    r"ntn_[A-Za-z0-9]|webhook|sk-[A-Za-z0-9]|"
    r"刘心曲|冰哥|佳明|CTO|技术总监|\d{3,}\s*台(机器|服务器)?|\d{3,}\s*个\s*[Pp]od",
    re.I)


def _answer_files():
    out = []
    for sub in ("drafts", "published"):
        p = os.path.join(ROOT, "answers", sub)
        if not os.path.isdir(p):
            continue
        for fn in sorted(os.listdir(p)):
            if fn.endswith(".md") and fn != "TEMPLATE.md":
                out.append(os.path.join(p, fn))
    return out


def cmd_lint(a):
    """检查回答草稿：人称、脱敏红线、条目引用、字数。"""
    km = load_km()
    files = [os.path.join(ROOT, a.file)] if a.file else _answer_files()
    if not files:
        print("answers/ 下没有稿件")
        return 0
    bad = 0
    for path in files:
        raw = open(path, encoding="utf-8").read()
        fm, body = split_fm(raw)
        fm = fm or {}
        # 去掉 frontmatter 与 HTML 注释后才是正文
        text = re.sub(r"<!--.*?-->", "", body, flags=re.S)
        n = len(re.sub(r"[#>|`*\s\-]", "", text))
        print(f"\n=== {os.path.relpath(path, ROOT)}　{n} 字 ===")

        fp = [(i, l.strip()) for i, l in enumerate(text.split("\n"), 1)
              if FIRST_PERSON.search(l)]
        if fp:
            print(f"  人称：发现 {len(fp)} 处「我」，逐条确认是否属于允许的例外")
            for i, l in fp:
                print(f"    L{i}  {l[:64]}")
        else:
            print("  人称：无第一人称 ✓")

        rl = [(i, l.strip()) for i, l in enumerate(text.split("\n"), 1)
              if REDLINE.search(l)]
        if rl:
            bad += 1
            print(f"  脱敏：命中 {len(rl)} 处红线，必须处理")
            for i, l in rl:
                print(f"    L{i}  {l[:64]}")
        else:
            print("  脱敏：未命中红线 ✓")

        miss = [e for e in (fm.get("used_entries") or []) if km and e not in km]
        if miss:
            bad += 1
            print(f"  条目：{'、'.join(miss)} 在 km-harness 中不存在")
        else:
            print(f"  条目：{len(fm.get('used_entries') or [])} 条，均存在 ✓")

        if fm.get("word_count") not in (None, n):
            print(f"  字数：frontmatter 写的是 {fm['word_count']}，实际 {n}"
                  f"（用 --fix 同步）")
            if a.fix:
                raw = re.sub(r"^word_count: .*$", f"word_count: {n}", raw, flags=re.M)
                open(path, "w", encoding="utf-8").write(raw)
                print("        已同步")
    print()
    return 1 if bad else 0


def cmd_scan(a):
    """定期检查：km-harness 新增 / 更新了哪些职场条目，能用到哪些问题上。"""
    km = load_km()
    if not km:
        sys.exit(f"读不到 km-harness：{KM}")
    st = read_state()
    known = st.get("entries", {})
    qs = load_questions()

    career = {i: e for i, e in km.items() if series_for(e["domains"])}
    new = {i: e for i, e in career.items() if i not in known}
    upd = {i: e for i, e in career.items()
           if i in known and known[i] != e["updated"]}

    matched = set()
    for q in qs:
        if q["dir"] != "dropped":
            matched.update(q["fm"].get("matched_entries") or [])

    print(f"检查时间：{TODAY}")
    print(f"上次检查：{st.get('last_scan') or '（首次）'}")
    print(f"km-harness 职场条目 {len(career)} 条｜新增 {len(new)}｜有更新 {len(upd)}｜"
          f"已被问题引用 {len(matched & set(career))}\n")

    def report(title, items):
        if not items:
            return
        print(f"—— {title} ——")
        for i in sorted(items):
            e = items[i]
            ss = series_for(e["domains"])
            print(f"\n{i} {e['title']}")
            print(f"  {e['one_liner'][:90]}")
            print(f"  domains: {'、'.join(e['domains'])}　-> 系列 {'、'.join(ss) or '无'}")
            for s in ss:
                cand = [q for q in qs if q["fm"].get("series") == s
                        and q["dir"] in ("inbox", "active")]
                for q in sorted(cand, key=lambda x: x["fm"]["id"])[:4]:
                    print(f"    · {q['fm']['id']} [{q['fm']['priority']}/{q['dir']}] {q['fm']['title'][:38]}")
        print()

    report("新增条目", new)
    report("内容有更新的条目", upd)

    unused = {i: e for i, e in career.items() if i not in matched}
    print(f"—— 尚未被任何问题引用的职场条目：{len(unused)} 条 ——")
    if a.verbose:
        for i in sorted(unused):
            print(f"  {i} {career[i]['title']}　({'、'.join(series_for(career[i]['domains']))})")
    else:
        print("  用 --verbose 列出全部")
    print()

    print("—— 待办 ——")
    p0 = [q for q in qs if q["dir"] == "inbox" and q["fm"]["priority"] == "P0"]
    for q in p0:
        print(f"  inbox 里的 P0 未启动：{q['fm']['id']} {q['fm']['title'][:40]}")
    for q in qs:
        if q["dir"] == "active" and not q["fm"].get("answer_id"):
            print(f"  active 但还没开始写：{q['fm']['id']} {q['fm']['title'][:40]}")
    stale = [q for q in qs if q["dir"] in ("inbox", "active") and not q["fm"].get("checked")]
    if stale:
        print(f"  还没人工核对过热度（followers 为空）：{len(stale)} 个")

    if a.commit:
        st = {"last_scan": TODAY, "entries": {i: e["updated"] for i, e in career.items()}}
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n已更新 {STATE}")
    else:
        print("\n（未写入状态。确认看过之后加 --commit，下次就只报更新的部分）")


def main():
    ap = argparse.ArgumentParser(prog="zhihuctl")
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="新建问题登记")
    n.add_argument("--title", required=True)
    n.add_argument("--url", required=True)
    n.add_argument("--series", default=None)
    n.add_argument("--priority", default="P2", choices=["P0", "P1", "P2"])
    n.add_argument("--entries", default="", help="逗号分隔的 km-harness 条目 id")
    n.add_argument("--angle", default="")
    n.set_defaults(fn=cmd_new)

    sub.add_parser("validate", help="校验").set_defaults(fn=cmd_validate)
    sub.add_parser("index", help="重建 INDEX.md").set_defaults(fn=cmd_index)

    p = sub.add_parser("promote", help="inbox->active->answered")
    p.add_argument("id")
    p.add_argument("--url", default=None, help="发布链接，进 answered 时填")
    p.set_defaults(fn=cmd_promote)

    d = sub.add_parser("drop", help="放弃")
    d.add_argument("id")
    d.add_argument("--reason", required=True)
    d.set_defaults(fn=cmd_drop)

    s = sub.add_parser("show")
    s.add_argument("id")
    s.set_defaults(fn=cmd_show)

    li = sub.add_parser("lint", help="检查回答草稿：人称、脱敏、条目、字数")
    li.add_argument("--file", default=None, help="只检查某一篇，相对仓库根目录的路径")
    li.add_argument("--fix", action="store_true", help="自动同步 word_count")
    li.set_defaults(fn=cmd_lint)

    sc = sub.add_parser("scan", help="定期检查")
    sc.add_argument("--commit", action="store_true", help="把本次结果写进 state/scan.json")
    sc.add_argument("--verbose", action="store_true")
    sc.set_defaults(fn=cmd_scan)

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
