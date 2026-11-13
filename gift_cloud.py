#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""欢乐钓鱼大师 · 双号每日兑码（云端单文件版，纯标准库、零 AI 调用）"""
import datetime
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
PROXY = "https://customer-openapi.tuyoo.com/api/customer-service-api/proxy"
GAME = "https://158-xxdyw-gamehttp-online01.bjxuejing.cn/gm/fishon/useActivationCode"
HDR = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://fishing.bjxuejing.cn/",
}
CREATED = "2026-11-12"
ROLES = {
    "1011059970": {
        "name": "～被情绪左右#1",
        "done": ["gzgzh666", "fisher6666", "fishmaster666", "vip6666", "vip7777",
                 "vip8888", "super8888", "diaoyu9999", "fish666888",
                 "king88888", "hldyds99999"],
    },
    "3045919893": {
        "name": "方生方死方死方生",
        "done": ["gzgzh666", "fisher6666", "diaoyu9999"],
    },
}
PENDING_INIT = {"3045919893": [["fish666888", 7], ["king88888", 14], ["hldyds99999", 30]]}
DEAD_INIT = [
    "vip666", "vip777", "vip888", "super888", "diaoyu999", "fish6688",
    "king8888", "hldyds9999", "happy2026", "fishmode", "jwst888",
    "1122happy", "1122vip", "fishon1122", "fisher666", "alt999",
    "xueer520", "xueer999", "888vvvip", "hldyds666", "hldyds888",
]
HUNT_URLS = [
    "https://www.ali213.net/zt/hldy/",
    "https://m.ali213.net/aznew/611149.html",
]
INTERVAL = 14


def load_state():
    p = os.path.join(BASE, "state.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    st = {"accounts": {}, "pending": {}, "dead": list(DEAD_INIT), "runs": []}
    for rid, info in ROLES.items():
        st["accounts"][rid] = {"name": info["name"], "done": list(info["done"])}
        st["pending"][rid] = [list(x) for x in PENDING_INIT.get(rid, [])]
    return st


def save_state(st):
    with open(os.path.join(BASE, "state.json"), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def http(url, timeout=25):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=timeout) as r:
            return r.read().decode("utf-8", "replace").strip()
    except Exception as e:
        return json.dumps({"NET_ERR": "%s: %s" % (type(e).__name__, e)}, ensure_ascii=False)


def submit(rid, code):
    target = "%s?simpleId=%s&code=%s" % (GAME, rid, urllib.parse.quote(code, safe=""))
    return http(PROXY + "?url=" + urllib.parse.quote(target, safe=""))


def classify(body):
    if '"success":true' in body or body.strip().startswith('{"success":true'):
        return "OK"
    for key, tag in (("1071", "USED"), ("1546", "DAYS"), ("1070", "EXPIRED"),
                     ("1005", "MISSING"), ("1412", "BUSY")):
        if key in body:
            return tag
    if "NET_ERR" in body:
        return "NET_ERR"
    return "UNKNOWN"


def hunt(st):
    """抓公开攻略页找新候选码。只认「字母串+2~6位数字」这种官方码格式，
    最多 4 个，且只给老账号试一次，避免抓到网页杂词时空刷服务器。"""
    stop = set(st["dead"])
    for info in st["accounts"].values():
        stop |= set(info["done"])
    bad = {"android", "iphone", "chrome", "github", "https", "http", "base64",
           "utf8", "cookie", "webkit", "windows", "master", "pikafish"}
    pat = re.compile(r"(?<![A-Za-z0-9])([a-z]{3,12}\d{2,6})(?![A-Za-z0-9])", re.I)
    found = []
    for url in HUNT_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": HDR["User-Agent"]})
            with urllib.request.urlopen(req, timeout=12) as r:
                text = r.read().decode("utf-8", "ignore")
            for m in pat.findall(text):
                c = m.lower()
                if c in stop or c in found or c in bad or not 6 <= len(c) <= 14:
                    continue
                found.append(c)
        except Exception:
            pass
    return found[:4]


def build_jobs(st, day, new_codes, hunt_codes):
    jobs, seen = [], set()
    for rid, plist in st["pending"].items():
        for item in plist:
            code, need = item[0], item[1]
            if day >= need and code not in seen:
                jobs.append((rid, code, "天数档 ≥%d" % need))
                seen.add(code)
    # 手工/已确认的新码：两个号都试
    for c in new_codes:
        c = c.strip().lower()
        if not c or c in seen or c in st["dead"]:
            continue
        if any(c in a["done"] for a in st["accounts"].values()):
            continue
        seen.add(c)
        for rid in ROLES:
            jobs.append((rid, c, "新候选码"))
    # 网页自动抓到的疑似码：只给老账号试一次，验明正身
    for c in hunt_codes:
        if c and c not in seen and c not in st["dead"]:
            seen.add(c)
            jobs.append(("1011059970", c, "公开页疑似码"))
    return jobs[:26]


def main():
    today = datetime.date.today()
    day = (today - datetime.date(*map(int, CREATED.split("-")))).days + 1
    st = load_state()
    dry = "--dry-run" in sys.argv
    if "--probe" in sys.argv:
        for rid in ROLES:
            t = "https://158-xxdyw-gamehttp-online01.bjxuejing.cn/gm/fishon/playerAccountQuery?simpleId=" + rid
            print(rid, http(PROXY + "?url=" + urllib.parse.quote(t, safe=""))[:200])
        return

    cand_file = os.path.join(BASE, "candidates.txt")
    manual = []
    if os.path.exists(cand_file):
        with open(cand_file, encoding="utf-8") as f:
            manual = [x.strip() for x in f if x.strip() and not x.startswith("#")]
    hunt_codes = [] if dry else hunt(st)
    jobs = build_jobs(st, day, manual, hunt_codes)

    print("日期 %s · 建号第 %d 天 · 计划 %d 次提交" % (today, day, len(jobs)), flush=True)
    for rid, code, why in jobs:
        print("  %s  %-16s %s" % (rid, code, why), flush=True)
    if dry:
        print("[dry-run] 未向服务器提交任何请求。", flush=True)
        return

    lines, ok = [], []
    for n, (rid, code, why) in enumerate(jobs):
        if n:
            time.sleep(INTERVAL)
        body = submit(rid, code)
        tag = classify(body)
        if tag == "BUSY":
            time.sleep(22)
            body = submit(rid, code)
            tag = classify(body)
        if tag == "MISSING" and code != code.lower():
            body = submit(rid, code.lower())
            tag = classify(body)
            code = code.lower()
        if tag == "OK":
            time.sleep(16)
            verify = classify(submit(rid, code))
            if verify == "USED":
                st["accounts"][rid]["done"].append(code)
                ok.append((rid, code))
                tag = "OK(已复核)"
            else:
                tag = "OK(复核:" + verify + ")"
        elif tag == "USED":
            if code not in st["accounts"][rid]["done"]:
                st["accounts"][rid]["done"].append(code)
        elif tag in ("EXPIRED", "MISSING"):
            if code not in st["dead"]:
                st["dead"].append(code)
        if tag.startswith("OK") or tag == "USED":
            st["pending"][rid] = [x for x in st["pending"].get(rid, []) if x[0] != code]
        lines.append("| %s | %s | %s | %s |" % (code, rid, tag, why))
        print("  %-16s %-10s %s" % (code, rid, tag), flush=True)
        save_state(st)

    st["runs"].append({"date": str(today), "day": day, "jobs": len(jobs), "ok": len(ok)})
    save_state(st)

    with open(os.path.join(BASE, "RESULT.md"), "w", encoding="utf-8") as f:
        f.write("# 今日兑换结果 · %s（第 %d 天）\n\n" % (today, day))
        f.write("**新成功 %d 个**\n\n" % len(ok))
        if ok:
            for rid, code in ok:
                f.write("- `%s` → %s（%s）\n" % (code, rid, st["accounts"][rid]["name"]))
            f.write("\n⚠️ 奖励 10 分钟内到游戏邮箱，邮件有存放时限，尽快上线领。\n")
        else:
            f.write("本次提交 %d 次。无可兑项时脚本不空刷服务器。\n" % len(jobs))
        f.write("\n| 兑换码 | 角色 ID | 结果 | 来源 |\n|---|---|---|---|\n")
        f.write("\n".join(lines) + "\n" if lines else "| — | — | 今天无可兑项 | — |\n")
        f.write("\n返回码：OK=成功(已复核) / USED=已领过 / DAYS=天数不够(保留待兑) / EXPIRED=全服过期 / MISSING=码不存在 / BUSY=限流 / NET_ERR=网络异常\n")

    pend = sum(len(v) for v in st["pending"].values())
    summary = "%s 第%d天 提交%d 成功%d 待天数%d 候选%d(自动%d)\n" % (today, day, len(jobs), len(ok), pend, len(manual) + len(hunt_codes), len(hunt_codes))
    with open(os.path.join(BASE, "HISTORY.md"), "a", encoding="utf-8") as f:
        f.write("- " + summary)
    print(summary, flush=True)


if __name__ == "__main__":
    main()
