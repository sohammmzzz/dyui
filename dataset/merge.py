"""Merge a new generation run into an existing dataset without duplicates.

    PYTHONPATH=python python dataset/merge.py --base dataset/data/eval.jsonl \
        --new dataset/work_s2/data/eval.jsonl --out dataset/data/eval_merged.jsonl

Base records always win; only new records are dropped.  Three layers, cheapest first:
  1. exact:      same category + same conversation (all user/tool turns) + same reference after whitespace/case folding
  2. same-ask:   same category + same conversation text (the user asked the identical thing), whatever the reference
  3. near:       MinHash over last user turn + component sequence (generate.dedupe, Jaccard >= 0.8 inside a category)
New ids are renumbered per category after the highest base id, so the two runs never collide.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from generate import dedupe  # noqa: E402


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _convo(r: dict) -> str:
    return " | ".join(_norm(str(m.get("content") or "")) for m in r["messages"] if m["role"] != "system")


def clean_id(i: str) -> str:
    """Writers occasionally left markdown around an id (e.g. '`A-0004'); keep only the id itself."""
    m = re.search(r"[A-Z]-\d{4}", i)
    return m.group(0) if m else i


def load(path: Path) -> list[dict]:
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in recs:
        r["id"] = clean_id(r["id"])
    return recs


def merge(base: list[dict], new: list[dict]) -> tuple[list[dict], Counter]:
    drops: Counter = Counter()
    seen_exact = {(r["category"], _convo(r), _norm(r["reference"])) for r in base}
    seen_ask = {(r["category"], _convo(r)) for r in base}
    survivors = []
    for r in new:
        ex, ask = (r["category"], _convo(r), _norm(r["reference"])), (r["category"], _convo(r))
        if ex in seen_exact:
            drops["exact"] += 1
        elif ask in seen_ask:
            drops["same_ask"] += 1
        else:
            seen_exact.add(ex)
            seen_ask.add(ask)
            survivors.append(r)
    # near-duplicate pass: base first so base records are the ones kept
    combined, _ = dedupe(base + survivors)
    kept_ids = {id(r) for r in combined}
    kept_new = [r for r in survivors if id(r) in kept_ids]
    drops["near"] = len(survivors) - len(kept_new)
    # renumber new ids per category after the highest base id
    top: dict[str, int] = {}
    for r in base:
        n = int(r["id"].split("-")[-1])
        top[r["category"]] = max(top.get(r["category"], 0), n)
    for r in sorted(kept_new, key=lambda x: (x["category"], x["id"])):
        top[r["category"]] = top.get(r["category"], 0) + 1
        r["meta"] = {**r.get("meta", {}), "source_id": r["id"]}
        r["id"] = f"{r['category']}-{top[r['category']]:04d}"
    return base + kept_new, drops


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    base, new = load(Path(a.base)), load(Path(a.new))
    merged, drops = merge(base, new)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.sort(key=lambda r: (r["category"], r["id"]))
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n", encoding="utf-8")
    ids = [r["id"] for r in merged]
    assert len(ids) == len(set(ids)), "duplicate ids after merge"
    print(f"base {len(base)} + new {len(new)} -> {len(merged)} records "
          f"(dropped: exact {drops['exact']}, same_ask {drops['same_ask']}, near {drops['near']})")
    print("per category:", dict(sorted(Counter(r["category"] for r in merged).items())))


if __name__ == "__main__":
    main()
