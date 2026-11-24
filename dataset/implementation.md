# DyUI eval dataset: how it was built, and how to continue

This directory holds a **ground-truth evaluation dataset** for models that write DyUI 1.3.0 *without* the component
catalog in their prompt, plus the **evaluator** that scores a model's answers against it. It is for testing only,
not for training.

- The specification is in [`../MODEL_EVAL.md`](../MODEL_EVAL.md): record format, 14 categories, decision policy,
  hard gates, targets.
- The background plan (the fine-tuning dataset this eval supports) is in [`../DATASET_PLAN.md`](../DATASET_PLAN.md).

Current state: **2,089 records** in `data/eval.jsonl`, all passing the hard gates. The evaluator scores the
dataset's own references at 2,089 of 2,089 with every target met. It was built in two runs (600 seeds with seed 1,
then 1,500 seeds with seed 2), merged without duplicates, and put through a variety pass. See
[Agile loop](#agile-loop-how-the-second-run-was-done) and [Continuing](#continuing-the-work).

## 1. The idea: code owns facts, Sonnet owns language

A reference answer is only trustworthy if every number, URL, prop and action name in it is right. A language model is
good at natural prose and poor at being exactly right, so the work is split:

| Code decides (must be exact) | Sonnet writes (must be natural) |
|---|---|
| category, policy row, coverage cell | the user turn (except action turns) |
| domain, persona/system prompt, header, language, style | the gold reference reply: prose before, the `dyui` blocks, takeaway |
| all data: numbers, rows, series, URLs, tool calls and results | rewrites of replies that failed a gate |
| the 278 custom component classes and signatures | |
| history blocks (real `serialize_history`) | |
| action turns and quick-reply taps (real `action_text()`) | |
| the `expected` checks, gates, dedupe, manifest | |

Sonnet is given each seed's data and a target component structure and must reproduce the data exactly, in its own
words. A gate rejects the reply if it doesn't.

## 2. Pipeline

```
spec.py ─▶ seeds.py ─▶ [Sonnet writers] ─▶ assemble + gates.py ─▶ [Sonnet rewrites, ≤3 rounds] ─▶ finalize
```

1. **`prepare`** builds `work/seeds_all.jsonl`, per-batch seed files `work/seeds/<batch>.jsonl` (about 30 seeds per
   batch, see `work/batches.json`) and the writer brief `work/brief.md`. It is deterministic for a given `--n` and
   `--seed`.
2. **Sonnet writers.** One Sonnet subagent per batch reads `brief.md` plus its seed file and writes the user turn and
   gold reply for every seed into `work/out/<batch>.pN.txt`. Writers run in parallel; they are the only step that
   needs a model.
3. **`assemble --round N`** parses the outputs, builds the full records (`make_record`), and runs every gate. Records
   that pass go to `work/passed.jsonl`. Failures are written to `work/rewrite/roundN/` with the gate error messages.
4. **Rewrite loop.** A Sonnet subagent gets each failing seed plus its errors and writes a new reply. Repeat assemble
   with the next round number. The 600 run needed two rounds: 576 of 591 passed first time, and 9 seeds had no
   output because of an id remap.
5. **`finalize`** de-duplicates (MinHash over the user turn plus component sequence), prints the coverage report,
   and writes `data/eval.jsonl` and `data/manifest.json` (dyui version, spec hash, seed, counts, coverage).

## 2b. Agile loop: how the second run was done

The second run (1,500 seeds, `--seed 2`, scratch in `work_s2/`) was built in short sprints where creating and testing
overlapped, instead of one write-everything-then-check pass.

| Sprint | What ran in parallel | Result |
|---|---|---|
| 0. Write | 14 Sonnet writers, 4 batches each (about 120 seeds) | all 1,500 seeds written |
| 1. Test while writing | `assemble` and `quality.py` ran on the batches already finished | 1,406 of 1,500 passed the gates at that point; the quality report found the "Here is/are the…" opener on 32–80% of replies in several categories |
| Retro | the still-running writers were sent a variety directive | fewer templated openers in later batches |
| 2. Fix | 9 Sonnet rewriters, one per failing batch, each given its gate errors | 1,499 of 1,500 passed; one more rewrite cleared the last |
| 3. Merge | `finalize` (dedupe inside the run), then `merge.py` against the original 600 | 7 dropped inside the run, 4 at the merge (1 same-ask, 3 near-duplicate), 2,089 records |
| 4. Variety | `variety.py`: 10 Sonnet agents rewrote only the intro and outro of 485 records whose opener was over-represented | all 485 re-gated, none rejected; category-level opener warnings cleared |
| 5. Verify | gates over every record, evaluator `--use-reference`, `quality.py`, evaluator tests | gates 0 failures, evaluator 2,089 of 2,089, tests 38 of 38 |

What the verification step caught:
- The evaluator ignored the generator's `block_optional` flag and reported 21 false over-use failures. It now honours
  the flag (except under `[dyui off]`).
- One record ended with "just ask", a filler phrase the generator's gate list did not contain. The phrase is now in
  `spec.FILLER_PHRASES`, and that sentence was trimmed from the record (`meta.trimmed_filler`).
- One record in the first run had the id `` `A-0004 `` (markdown left by a writer). `merge.py` and `variety.py` now
  normalise ids, and it is stored as `A-0004`.

## 3. The gates (`gates.py`)

A reference must pass all of them or it is discarded and rewritten:

- `dyui.genui.parser.parse_text` raises no `ComponentError` against the item's effective catalog, which means the
  built-ins, restricted by the header, plus any custom classes.
- Components are inside the header's allowed set; no block at all for J, `[dyui off]` and no-component items.
- Non-empty prose before the first and after the last block; no filler phrases ("Feel free to ask…").
- Single-line JSON, no HTML, no blocklisted component or prop names (the section N wrong-name table).
- Grounding: every number and URL in a block appears in the conversation context. String-level grounding (names,
  cells) is enforced for G, F and I.
- F edits: values outside the requested change are byte-identical to the history block (checked on code-computed
  fragments).
- E actions: the action name exists in the previous turn's component and the payload matches.
- Limits: at most 3 blocks, 6 components, 4 `quick_replies` options.

`gates.py` is strict on purpose: DyUI's own parser is lenient (it silently ignores unknown props, drops bad optional
values and turns a bad child into an `invalid` node), so the gates re-validate on top of it.

## 4. What each file is

### Core pipeline

| File | Role |
|---|---|
| `spec.py` | Single source of truth. Reads `dyui.catalog()` and each class's `model_json_schema()` to build component specs (required/optional props, enums, signatures). Also holds the category shares, the policy table, the wrong-name blocklist and the spec hash. Nothing about the language is hand-copied. |
| `seeds.py` | The seed builder. One `gen_<category>` function per category (`gen_A_slot`, `gen_B_pair`, `gen_C`, `gen_D`, `gen_E`, `gen_F`, `gen_G`, …), plus the `Coverage` scheduler that guarantees every component, enum value and nesting pair meets its floor. Produces seeds with data, history, action turns and `expected` checks. |
| `generate.py` | The CLI and orchestration: `prepare`, `assemble`, `finalize`, `selftest`. Writes the writer brief, parses Sonnet's output files, builds records, runs gates, dedupes, prints coverage and writes the manifest. |
| `gates.py` | The hard gates above. `check(record)` returns a list of failures (empty means pass); `check(record, reply=...)` runs the reply-quality gates on any other reply. |

### Generator support (used by `seeds.py`)

| File | Role |
|---|---|
| `kit.py` | Generator toolkit: the `Ctx` object, number/series/table/entity generators, URL generator, `Piece` (user facts + gold component objects + intro/outro), reply assembly and user-turn styling. |
| `fam_data.py` | Piece builders for content and data components: `stat`, `stats`, `chart_*`, `table`, `keyvalue`, `timeline`, `plan`, `progress`, `json`, `callout`, `code`, `markdown`, `quote`, … |
| `fam_ui.py` | Piece builders for media, interactive, agent and layout components: `image`, `gallery`, `video`, `buttons`, `form`, `confirm`, `rating`, `step`, `reasoning`, `card`, `grid`, `tabs`, `accordion`, … |
| `bank.py` | Pure data: names, places, the 25 domains (3 are held out) and the app personas. |
| `lang.py` | Non-English prose frames (es, fr, de, pt, it). JSON keys, enums and component names always stay English. |
| `customs.py` | The fixed pool of 278 synthetic custom components. Each is exec'd and registered through the real component mechanism, so signatures come from DyUI itself. 60 are held out; the pool does not depend on `--seed`, so the held-out set is stable. |
| `gold.py` | Hand-written gold examples, 3 per category. Used as few-shots for the writers and as a sanity check for the gates (`selftest`). |

### Dataset-quality tools

| File | Role |
|---|---|
| `merge.py` | Merges a new run into an existing dataset without duplicates (base records always win): exact match, same-ask match, then MinHash near-duplicate. Renumbers the new ids per category after the highest base id (old id kept in `meta.source_id`) and asserts ids are unique. |
| `quality.py` | Variety report: opener concentration, repeated 5-word phrases, near-duplicates, length spread, domain/style/language mix. Warns above fixed thresholds (opener 12%, phrase 6%, near-dup 2%). Complements the gates, which only say whether a record is correct. |
| `variety.py` | `prepare` picks records whose reply opener is over-represented (quota 8% per category) and writes batches; Sonnet rewrites only the intro and outro; `apply` splices them in and re-runs the gates, keeping the original text if a rewrite fails. |

### Evaluator

| File | Role |
|---|---|
| `evaluator.py` | Scores model answers against records. Extracts every `dyui` block and component, builds the item's effective catalog, runs the real `parse_text`, then per-item checks (see below), and aggregates the MODEL_EVAL.md metrics against targets. |
| `test_evaluator.py` | 38 pytest cases with hand-made fixtures. |

### Data and scratch

| Path | Role |
|---|---|
| `data/eval.jsonl` | The dataset. One record per line. |
| `data/manifest.json` | dyui version, spec hash, seed, per-category / split / language counts, coverage. |
| `work/` | Scratch of run 1 (seed 1, 600 seeds), kept so the run is reproducible and auditable: `seeds_all.jsonl` and `seeds/` (inputs), `brief.md` (the writer brief), `out/` (Sonnet writer outputs), `rewrite/roundN/` (failures sent back), `passed.jsonl`, `assemble_round*.json` (per-round gate stats). |
| `work_s2/` | The same layout for run 2 (seed 2, 1,500 seeds), plus `variety/` (batches sent to the variety pass) and `variety_out/` (Sonnet's new intros and outros). The derived files (`passed.jsonl`, `merged*.jsonl`, `data/`) are not committed; they are rebuilt by `finalize`, `merge.py` and `variety.py apply`. Note: the variety pass also rewrote prose of run-1 records, and that is recorded only in `data/eval.jsonl` (`meta.varied`), not in `work/out/`. |

## 5. Record format

```json
{
  "id": "B-0173", "category": "B", "dyui": "1.3.0", "header": null, "split": "main",
  "messages": [{"role": "system", "content": "…"}, {"role": "user", "content": "…"}],
  "reference": "…gold assistant reply…",
  "expected": {
    "policy_row": "shares", "components_any_of": ["chart"], "chart_kind_any_of": ["donut", "pie"],
    "allowed_components": null, "must_have_block": true, "grounding_values": ["4120", "2380"],
    "forbidden": ["invented URLs", "HTML", "filler"]
  }
}
```

- `messages` ends on the last user turn. G records carry real `tool_calls` and `tool` messages. When a header is
  set, it is the first line of `messages[0]` and is also stored in `header`.
- E records carry `expected.action` as `{stage, component, name, data, …}`. Only the `emit` stage constrains the
  model's answer. The `respond`, `quick_reply` and `ignore` stages describe the user's input.
- Held-out custom components have `"split": "heldout"`.

## 6. Running things

```bash
# scoring a model: answers.jsonl has {"id": ..., "answer": ...} per line
python -m dataset.evaluator --data dataset/data/eval.jsonl --answers answers.jsonl \
    --out results.jsonl --report report.json

# self-test: score the dataset's own references (should be about 100%)
python -m dataset.evaluator --data dataset/data/eval.jsonl --use-reference --no-fail

python -m pytest dataset/test_evaluator.py        # evaluator tests
python dataset/generate.py selftest               # gates vs the hand-written gold examples
```

The evaluator exits non-zero when a target is missed (`--no-fail` disables that). Useful flags: `--strict-numbers`
(ungrounded numbers become failures instead of warnings), `--count-nested` (count nested components toward the
6-component limit), `--limit N`, `--show-failures N`.

Per-item checks: parse and schema validity, unknown props (nested too), `invalid` nodes in the tree, single-line JSON,
header adherence, prose wrap and filler, block/component limits, over-use, selection (`components_any_of`,
`chart_kind_any_of`), grounding (numbers, strings, invented URLs), F edits, E actions and payloads.

## 7. Continuing the work

### Add another run

All commands need the DyUI package on the path (`PYTHONPATH=python` from the repo root).

```bash
# 1. new seeds: use a seed not yet used (1 and 2 are taken) and a fresh work dir
python dataset/generate.py prepare --n 1500 --seed 3 --work dataset/work_s3
# 2. one Sonnet writer per 3-4 batches: read work_s3/brief.md and work_s3/seeds/<batch>.jsonl,
#    write work_s3/out/<batch>.pN.txt. Give them the variety directive (never open with "Here is/are/'s",
#    do not reuse phrases) so the variety pass has less to fix.
# 3. gate; repeat with --round 1, 2 after Sonnet rewrites the cards in work_s3/rewrite/roundN/
#    (rewriters write out/R<round><cat><nn>.pN.txt)
python dataset/generate.py assemble --work dataset/work_s3 --round 0
python dataset/generate.py finalize --work dataset/work_s3 --out dataset/work_s3/data/eval.jsonl
# 4. merge with the current dataset (drops duplicates, renumbers ids), then the variety pass
python dataset/merge.py --base dataset/data/eval.jsonl --new dataset/work_s3/data/eval.jsonl --out dataset/work_s3/merged.jsonl
python dataset/variety.py prepare --in dataset/work_s3/merged.jsonl --work dataset/work_s3
#    Sonnet writes work_s3/variety_out/V<nn>.jsonl ({"id","intro","outro"} per line)
python dataset/variety.py apply --in dataset/work_s3/merged.jsonl --work dataset/work_s3 --out dataset/work_s3/merged_varied.jsonl
# 5. verify before replacing data/eval.jsonl
python dataset/quality.py dataset/work_s3/merged_varied.jsonl
python -m dataset.evaluator --data dataset/work_s3/merged_varied.jsonl --use-reference
```

The seed builder was also checked at 3,000 seeds in one run (at least 39 replies per component and 10 per enum
value), so a single larger run works too.

### Known gaps

- **2,089 records, not the 3,000 suggested.** Run another seed (see above) to scale up.
- **No judge pass and no human render review.** MODEL_EVAL.md asks for an LLM judge (≥ 4/5, calibrated on the gold
  set) and a human review through the real `NodeView`. The gates, `quality.py` and the evaluator are the only
  quality filters. For training use, the variety of *prose* is what `quality.py` measures; it does not measure
  whether a reply reads well.
- **Two phrase repeats remain in `quality.py`:** K ("have a link or file", 8% of K) and S ("a chart with kind
  donut", 14% of S). The S one comes from the shared topic (stacked and donut chart questions).
- **Variety rewrites saw truncated input in places:** a few variety agents only saw the first 200–300 characters of
  long user turns. All rewrites passed the gates again, so no number or URL is ungrounded, but the prose may lean on
  the old intro or outro for facts.
- **Optional-prop presence** lands in the 30–70% target for only 31 of the 63 measured props. For example
  `callout.level` is 100% and `chart.stacked` 8%. Fix it in the piece builders, then regenerate.
- **E and F history turns:** the user turn and intro/outro prose inside history assistant messages come from the
  earlier template code, not Sonnet.
- **E reply turns** after `choice`, `buttons`, `rating`, `quick_replies` and "ignore" are marked `block_optional`, so
  a reply with no block is accepted there.
- **One E record** is flagged `OVERUSE` by the evaluator when it scores its own reference. Not yet investigated.
- **Grounding of strings** (names, cells) is enforced only for G, F and I. Numbers and URLs are enforced everywhere.

### When DyUI changes

`spec.py` reads the installed package, so a new component or prop shows up in the spec hash. Re-run `prepare` and
regenerate only the affected cells. The manifest records the spec hash the dataset was built against.
