"""Variety / quality report for a dataset JSONL (a sprint-review check, run next to the hard gates).

    PYTHONPATH=python python dataset/quality.py dataset/work_s2/passed.jsonl [--top 12] [--json out.json]

Hard gates say a record is *correct*; this says whether the set is *varied*.  It reports, per category and overall:
  - opener concentration: share of user turns / reply intros that start with the same 3 words
  - repeated phrases: 5-word phrases that appear in many replies (template smell)
  - near-duplicates (MinHash, same rule as merge.py)
  - length spread of user turns and replies
  - distribution of domain, style, language, component count per reply
Flags ("WARN") use fixed thresholds so sprints are comparable.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from generate import dedupe  # noqa: E402

BLOCK = re.compile(r"```dyui.*?```", re.S)
OPENER_MAX = 0.12      # no 3-word opener may start more than 12% of a category's turns
PHRASE_MAX = 0.06      # no 5-word phrase may appear in more than 6% of a category's replies
NEAR_DUP_MAX = 0.02
MIN_CAT = 20           # skip warnings for tiny categories


def words(s: str) -> list[str]:
    return re.findall(r"[\w']+", s.lower())


def prose(reply: str) -> str:
    return BLOCK.sub(" ", reply)


def last_user(r: dict) -> str:
    return [m for m in r["messages"] if m["role"] == "user"][-1]["content"] or ""


def report(recs: list[dict], top: int) -> dict:
    out: dict = {"n": len(recs), "warnings": [], "categories": {}}
    by_cat = defaultdict(list)
    for r in recs:
        by_cat[r["category"]].append(r)
    for cat, rs in sorted(by_cat.items()):
        n = len(rs)
        user_open = Counter(" ".join(words(last_user(r))[:3]) for r in rs if not last_user(r).startswith("[action:"))
        reply_open = Counter(" ".join(words(prose(r["reference"]))[:3]) for r in rs)
        phrases: Counter = Counter()
        for r in rs:
            w = words(prose(r["reference"]))
            phrases.update({" ".join(w[i:i + 5]) for i in range(len(w) - 4)})
        user_len = sorted(len(words(last_user(r))) for r in rs)
        rep_len = sorted(len(words(prose(r["reference"]))) for r in rs)
        info = {
            "n": n,
            "user_opener_top": user_open.most_common(3),
            "reply_opener_top": reply_open.most_common(3),
            "phrase_top": [(p, c) for p, c in phrases.most_common(3) if c > 1],
            "distinct_user_openers": len(user_open),
            "user_words_p10_p50_p90": [user_len[n // 10], user_len[n // 2], user_len[(9 * n) // 10]],
            "reply_prose_words_p10_p50_p90": [rep_len[n // 10], rep_len[n // 2], rep_len[(9 * n) // 10]],
        }
        out["categories"][cat] = info
        if n >= MIN_CAT:
            for label, ctr in (("user opener", user_open), ("reply opener", reply_open)):
                if ctr and ctr.most_common(1)[0][1] / n > OPENER_MAX:
                    p, c = ctr.most_common(1)[0]
                    out["warnings"].append(f"{cat}: {label} '{p}' starts {c}/{n} ({c / n:.0%})")
            if phrases and phrases.most_common(1)[0][1] / n > PHRASE_MAX and phrases.most_common(1)[0][1] > 2:
                p, c = phrases.most_common(1)[0]
                out["warnings"].append(f"{cat}: phrase '{p}' appears in {c}/{n} replies ({c / n:.0%})")
    _, dropped = dedupe(list(recs))
    out["near_duplicates"] = dropped
    if recs and dropped / len(recs) > NEAR_DUP_MAX:
        out["warnings"].append(f"near-duplicates {dropped}/{len(recs)} ({dropped / len(recs):.1%})")
    meta = [r.get("meta", {}) for r in recs]
    for key in ("domain", "style", "lang_name"):
        c = Counter(m.get(key) for m in meta if m.get(key))
        if c:
            out[key] = dict(c.most_common())
    out["components_per_reply"] = dict(sorted(Counter(len(re.findall(r'\{"ui":', r["reference"])) for r in recs).items()))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--json")
    a = ap.parse_args()
    recs = [json.loads(l) for l in Path(a.path).read_text(encoding="utf-8").splitlines() if l.strip()]
    rep = report(recs, a.top)
    print(f"{rep['n']} records, near-duplicates: {rep['near_duplicates']}")
    for k in ("domain", "style", "lang_name"):
        if k in rep:
            print(f"{k}: {dict(list(rep[k].items())[:a.top])}")
    print("components per reply:", rep["components_per_reply"])
    for cat, i in rep["categories"].items():
        print(f"\n[{cat}] n={i['n']} distinct user openers={i['distinct_user_openers']} "
              f"user words p10/50/90={i['user_words_p10_p50_p90']} reply prose words={i['reply_prose_words_p10_p50_p90']}")
        print("  user openers:", i["user_opener_top"])
        print("  reply openers:", i["reply_opener_top"])
        if i["phrase_top"]:
            print("  repeated phrases:", i["phrase_top"])
    print("\nWARNINGS:" if rep["warnings"] else "\nno warnings")
    for w in rep["warnings"]:
        print(" -", w)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
