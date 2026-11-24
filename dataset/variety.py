"""Variety pass: Sonnet re-writes the prose around the blocks of over-represented replies.

    PYTHONPATH=python python dataset/variety.py prepare --in dataset/work_s2/passed.jsonl --work dataset/work_s2
    # Sonnet writers: read work/variety/V*.jsonl, write work/variety_out/V*.jsonl  ({"id","intro","outro"} per line)
    PYTHONPATH=python python dataset/variety.py apply   --in dataset/work_s2/passed.jsonl --work dataset/work_s2 --out dataset/work_s2/passed_varied.jsonl

Only the text before the first ```dyui block (intro) and after the last one (outro) is replaced; the blocks, the middle prose,
the user turns and the `expected` checks are untouched.  Every rewritten reply goes through gates.check again; a reply
that fails keeps its original text.  Records are selected when their reply opens with a "Here is / Here are / Here's"
frame or any 3-word opener that exceeds its category's quota (OPENER_QUOTA of the category, the rest are kept as is).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gates  # noqa: E402

OPENER_QUOTA = 0.08
BATCH = 25
FENCE_OPEN = "```dyui"
HERE_FRAME = re.compile(r"^\W*here(\W|\s)(is|are|'s|’s)\b", re.I)


def split_reply(reply: str):
    i = reply.find(FENCE_OPEN)
    j = reply.rfind("```")
    if i < 0 or j <= i:
        return None
    return reply[:i], reply[i:j + 3], reply[j + 3:]


def opener(reply: str) -> str:
    parts = split_reply(reply)
    intro = parts[0] if parts else reply
    return " ".join(re.findall(r"[\w']+", intro.lower())[:3])


def clean_id(i: str) -> str:
    m = re.search(r"[A-Z]-\d{4}", i)
    return m.group(0) if m else i


def load(p: Path) -> list[dict]:
    recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in recs:
        r["id"] = clean_id(r["id"])
    return recs


def pick(recs: list[dict]) -> list[dict]:
    by_cat = defaultdict(list)
    for r in recs:
        if split_reply(r["reference"]):
            by_cat[r["category"]].append(r)
    chosen = []
    for cat, rs in by_cat.items():
        quota = max(1, int(OPENER_QUOTA * len(rs)))
        groups = defaultdict(list)
        for r in rs:
            key = "HERE" if HERE_FRAME.match(r["reference"]) else opener(r["reference"])
            groups[key].append(r)
        for key, g in groups.items():
            g.sort(key=lambda r: hashlib.md5(r["id"].encode()).hexdigest())
            chosen += g[quota:]
    return chosen


def prepare(a) -> None:
    recs = load(Path(a.inp))
    chosen = pick(recs)
    work = Path(a.work) / "variety"
    work.mkdir(parents=True, exist_ok=True)
    chosen.sort(key=lambda r: (r["category"], r["id"]))
    for n, i in enumerate(range(0, len(chosen), BATCH), 1):
        rows = []
        for r in chosen[i:i + BATCH]:
            intro, _, outro = split_reply(r["reference"])
            user = [m for m in r["messages"] if m["role"] == "user"][-1]["content"]
            rows.append({"id": r["id"], "category": r["category"], "lang": r.get("meta", {}).get("lang_name", "English"),
                         "user": user, "intro": intro.strip(), "block": split_reply(r["reference"])[1], "outro": outro.strip()})
        (work / f"V{n:02d}.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
    print(f"selected {len(chosen)} of {len(recs)} records in {-(-len(chosen) // BATCH)} batches -> {work}")
    print("by category:", dict(Counter(r["category"] for r in chosen)))


def apply(a) -> None:
    recs = load(Path(a.inp))
    new: dict[str, dict] = {}
    for f in sorted((Path(a.work) / "variety_out").glob("V*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                new[clean_id(d["id"])] = d
    changed = rejected = 0
    reasons: Counter = Counter()
    for r in recs:
        d = new.get(r["id"])
        parts = split_reply(r["reference"])
        if not d or not parts or not d.get("intro", "").strip() or not d.get("outro", "").strip():
            continue
        cand = d["intro"].strip() + "\n" + parts[1] + "\n" + d["outro"].strip()
        trial = dict(r, reference=cand)
        fails = gates.check(trial)
        if fails:
            rejected += 1
            reasons.update(f.gate for f in fails)
            continue
        r["reference"] = cand
        r.setdefault("meta", {})["varied"] = True
        changed += 1
    Path(a.out).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
    print(f"rewritten {changed}, rejected by gates (kept original) {rejected} {dict(reasons)}; wrote {a.out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "apply"])
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    prepare(a) if a.cmd == "prepare" else apply(a)


if __name__ == "__main__":
    main()
