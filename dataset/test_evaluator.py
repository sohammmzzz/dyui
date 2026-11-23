"""Tests for dataset/evaluator.py using hand-made fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataset import evaluator as ev  # noqa: E402


def rec(user="Q", *, header=None, category="A", expected=None, system="You are a helper.", extra_msgs=()):
    sys_text = f"{header}\n{system}" if header else system
    return {
        "id": f"{category}-0001",
        "category": category,
        "header": header,
        "messages": [{"role": "system", "content": sys_text}, {"role": "user", "content": user}, *extra_msgs],
        "expected": expected or {},
    }


def wrap(*lines, intro="Here is the view.", outro="That is the takeaway."):
    return f"{intro}\n```dyui\n" + "\n".join(lines) + f"\n```\n{outro}"


STAT = '{"ui":"stat","label":"Uptime","value":"99.97%"}'
CHART = '{"ui":"chart","kind":"donut","labels":["a","b"],"series":[{"name":"s","data":[1,2]}]}'


def codes(result):
    return result.codes


def test_valid_single_block():
    r = ev.evaluate_item(rec(expected={"components_any_of": ["stat"], "must_have_block": True}), wrap(STAT))
    assert r.passed, r.failures
    assert r.stats["n_blocks"] == 1 and r.stats["components"] == ["stat"]


def test_multiple_blocks_in_one_answer():
    ans = f"Intro.\n```dyui\n{STAT}\n```\nMiddle.\n```dyui\n{CHART}\n```\nDone."
    r = ev.evaluate_item(rec(), ans)
    assert r.passed, r.failures
    assert r.stats["n_blocks"] == 2 and r.stats["n_components"] == 2


def test_multiple_components_in_one_block():
    r = ev.evaluate_item(rec(), wrap(STAT, CHART))
    assert r.passed, r.failures
    assert r.stats["n_components"] == 2


def test_multiline_object_flagged_but_parses():
    pretty = '{\n  "ui": "stat",\n  "label": "Uptime",\n  "value": "99.97%"\n}'
    r = ev.evaluate_item(rec(), wrap(pretty))
    assert codes(r) == {"MULTILINE_JSON"}


def test_invalid_prop_value_reports_parse_error_with_message():
    bad = '{"ui":"chart","kind":"sphere","series":[{"name":"s","data":[1]}]}'
    r = ev.evaluate_item(rec(), wrap(bad))
    assert "PARSE_ERROR" in codes(r)
    msg = next(f.message for f in r.failures if f.code == "PARSE_ERROR")
    assert "kind" in msg and "block 1 line 2" in msg


def test_missing_required_prop():
    r = ev.evaluate_item(rec(), wrap('{"ui":"stat","label":"x"}'))
    assert "PARSE_ERROR" in codes(r)


def test_invented_prop_and_blocklist_hint():
    bad = '{"ui":"table","headers":["a"],"columns":["a"],"rows":[["1"]]}'
    r = ev.evaluate_item(rec(), wrap(bad))
    assert "INVENTED_PROP" in codes(r)
    assert any("columns" in f.message for f in r.failures if f.code == "INVENTED_PROP")


def test_invented_nested_prop():
    bad = '{"ui":"chart","kind":"bar","series":[{"name":"s","data":[1],"color":"red"}]}'
    r = ev.evaluate_item(rec(), wrap(bad))
    assert "INVENTED_PROP" in codes(r)


def test_unknown_component():
    r = ev.evaluate_item(rec(), wrap('{"ui":"alert","text":"hi"}'))
    assert "INVENTED_COMPONENT" in codes(r)
    assert "PARSE_ERROR" not in codes(r)  # reported once, by name
    assert any("callout" in f.message for f in r.failures)


def test_unknown_nested_child_is_flagged():
    tabs = '{"ui":"tabs","tabs":[{"label":"a","children":[{"ui":"bogus"}]}]}'
    r = ev.evaluate_item(rec(), wrap(tabs))
    assert "INVENTED_COMPONENT" in codes(r)


def test_nested_ok_layout():
    tabs = ('{"ui":"tabs","tabs":[{"label":"Python","children":[{"ui":"code","code":"import os\\nos.environ[\\"A\\"]","language":"python"}]},'
            '{"ui":"stat","label":"ignored-as-prop","value":1}]}')
    # second tab entry lacks "label"/"children" -> dropped silently by DyUI; strict check must object
    r = ev.evaluate_item(rec(), wrap(tabs))
    assert r.has("SCHEMA_STRICT", "INVENTED_PROP", "PARSE_ERROR", "SCHEMA_CHILD_INVALID")


def test_silently_dropped_optional_prop_is_caught():
    r = ev.evaluate_item(rec(), wrap('{"ui":"stat","label":"x","value":"1","trend":"sideways"}'))
    assert "SCHEMA_STRICT" in codes(r)


def test_restricted_header_leak():
    h = "[dyui: table, callout]"
    r = ev.evaluate_item(rec(header=h, category="H"), wrap(CHART))
    assert "HEADER_LEAK" in codes(r)
    ok = ev.evaluate_item(rec(header=h, category="H"), wrap('{"ui":"table","columns":["a"],"rows":[["1"]]}'))
    assert ok.passed, ok.failures


def test_restricted_header_leak_in_nested_child():
    h = "[dyui: card, markdown]"
    card = '{"ui":"card","title":"t","children":[{"ui":"stat","label":"x","value":"1"}]}'
    r = ev.evaluate_item(rec(header=h, category="H"), wrap(card))
    assert "HEADER_LEAK" in codes(r)


def test_header_off_with_block():
    r = ev.evaluate_item(rec(header="[dyui off]", category="H"), wrap(STAT))
    assert "HEADER_OFF_BLOCK" in codes(r)
    plain = ev.evaluate_item(rec(header="[dyui off]", category="H"), "Uptime was 99.97%, above the 99.9% SLO.")
    assert plain.passed, plain.failures


def test_header_mentioned_in_reply():
    r = ev.evaluate_item(rec(header="[dyui: table]", category="H"), "I can't use a chart because of the [dyui: table] setting.")
    assert "MENTIONS_RESTRICTION" in codes(r)


FLIGHT = "[dyui +flight(airline: string, depart: string, arrive?: string, price: number, cabin?: \"economy\"|\"business\")]"


def test_custom_component_valid():
    ans = wrap('{"ui":"flight","airline":"TAP","depart":"Fri 18:05","price":189,"cabin":"economy"}')
    r = ev.evaluate_item(rec(header=FLIGHT, category="I"), ans)
    assert r.passed, r.failures
    assert r.stats["components"] == ["flight"]


def test_custom_component_invalid():
    missing = ev.evaluate_item(rec(header=FLIGHT, category="I"), wrap('{"ui":"flight","airline":"TAP","price":189}'))
    assert "PARSE_ERROR" in codes(missing)
    badenum = ev.evaluate_item(rec(header=FLIGHT, category="I"),
                               wrap('{"ui":"flight","airline":"TAP","depart":"x","price":1,"cabin":"first"}'))
    assert "SCHEMA_STRICT" in codes(badenum)  # optional enum silently dropped by DyUI
    extra = ev.evaluate_item(rec(header=FLIGHT, category="I"),
                             wrap('{"ui":"flight","airline":"TAP","depart":"x","price":1,"gate":"A1"}'))
    assert "INVENTED_PROP" in codes(extra)


def test_custom_component_from_expected_metadata_and_restricted_combo():
    h = '[dyui: markdown, table +ticket(id: string, title: string, status: "open"\\|"closed")]'
    spec = ev.parse_header(h)
    assert spec.allowed == ["markdown", "table"] and spec.customs[0].startswith("ticket(")
    ok = ev.evaluate_item(rec(header=h, category="I"), wrap('{"ui":"ticket","id":"T-1","title":"x","status":"open"}'))
    assert ok.passed, ok.failures
    r = ev.evaluate_item(rec(category="I", expected={"custom_components": ["ticket(id: string, status: \"open\"|\"closed\")"]}),
                         wrap('{"ui":"ticket","id":"T-1","status":"open"}'))
    assert r.passed, r.failures


def test_custom_not_declared_is_invented():
    r = ev.evaluate_item(rec(category="I"), wrap('{"ui":"flight","airline":"TAP","depart":"x","price":1}'))
    assert "INVENTED_COMPONENT" in codes(r)


def test_parse_header_variants():
    assert ev.parse_header("[dyui off]").off
    assert ev.parse_header("[dyui: table, chart, callout, quick_replies]").allowed == ["table", "chart", "callout", "quick_replies"]
    h = ev.parse_header(FLIGHT)
    assert h.allowed is None and len(h.customs) == 1
    assert ev.parse_header(None).allowed is None


def test_missing_prose():
    r = ev.evaluate_item(rec(), f"```dyui\n{STAT}\n```")
    assert {"NO_LEAD_PROSE", "NO_TAIL_PROSE"} <= codes(r)
    r2 = ev.evaluate_item(rec(), f"Intro.\n```dyui\n{STAT}\n```")
    assert codes(r2) == {"NO_TAIL_PROSE"}


def test_filler_phrase():
    r = ev.evaluate_item(rec(), wrap(STAT, outro="Feel free to ask more."))
    assert "FILLER" in codes(r)


def test_overuse_on_j_and_ok_negative():
    j = rec("What does idempotent mean?", category="J", expected={"must_have_block": False})
    bad = ev.evaluate_item(j, wrap(STAT))
    assert "OVERUSE" in codes(bad)
    good = ev.evaluate_item(j, "An operation is idempotent if repeating it has the same effect as doing it once.")
    assert good.passed, good.failures


def test_missing_block_and_wrong_component():
    exp = {"must_have_block": True, "components_any_of": ["chart"], "chart_kind_any_of": ["donut", "pie"]}
    assert "MISSING_BLOCK" in codes(ev.evaluate_item(rec(category="B", expected=exp), "Organic is the biggest channel."))
    assert "WRONG_COMPONENT" in codes(ev.evaluate_item(rec(category="B", expected=exp), wrap(STAT)))
    wrong_kind = '{"ui":"chart","kind":"line","series":[{"name":"s","data":[1,2]}]}'
    assert "WRONG_CHART_KIND" in codes(ev.evaluate_item(rec(category="B", expected=exp), wrap(wrong_kind)))
    assert ev.evaluate_item(rec(category="B", expected=exp), wrap(CHART)).passed


def test_limits():
    five = [STAT] * 7
    r = ev.evaluate_item(rec(), wrap(*five))
    assert "LIMIT_COMPONENTS" in codes(r)
    blocks = "\n".join(f"P.\n```dyui\n{STAT}\n```" for _ in range(4)) + "\nEnd."
    assert "LIMIT_BLOCKS" in codes(ev.evaluate_item(rec(), blocks))
    qr = '{"ui":"quick_replies","options":["a","b","c","d","e"]}'
    assert "LIMIT_QUICK_REPLIES" in codes(ev.evaluate_item(rec(), wrap(qr)))


def test_bare_json_fence_and_bare_line():
    ans = 'Intro.\n```json\n{"ui":"stat","label":"x","value":"1"}\n```\nBye.'
    assert "BARE_JSON_FENCE" in codes(ev.evaluate_item(rec(), ans))
    plain_json = 'Intro.\n```json\n{"a":1}\n```\nBye.'
    r = ev.evaluate_item(rec(), plain_json)
    assert r.passed and r.stats["n_blocks"] == 0
    bare = 'Intro.\n{"ui":"stat","label":"x","value":"1"}\nBye.'
    assert "BARE_COMPONENT" in codes(ev.evaluate_item(rec(), bare))


def test_html_detection_but_code_component_allowed():
    html = ev.evaluate_item(rec(), "Use <div class='x'>hi</div> here.")
    assert "HTML" in codes(html)
    code = '{"ui":"code","language":"html","code":"<div class=\\"x\\">hi</div>"}'
    assert ev.evaluate_item(rec(), wrap(code)).passed
    md = ev.evaluate_item(rec(), wrap('{"ui":"markdown","text":"<script>alert(1)</script>"}'))
    assert "HTML" in codes(md)


def test_invented_url():
    ctx = rec("Docs are at https://example.com/docs", category="G", expected={"must_have_block": True})
    good = '{"ui":"link_preview","url":"https://example.com/docs","title":"Docs"}'
    bad = '{"ui":"link_preview","url":"https://made-up.dev/x","title":"Docs"}'
    assert ev.evaluate_item(ctx, wrap(good)).passed
    r = ev.evaluate_item(ctx, wrap(bad))
    assert "UNGROUNDED_URL" in codes(r)
    js = ev.evaluate_item(ctx, wrap('{"ui":"link_preview","url":"javascript:alert(1)","title":"x"}'))
    assert "UNSAFE_URL" in codes(js) or "PARSE_ERROR" in codes(js)


def test_grounding_values_and_numbers_warning():
    exp = {"grounding_values": ["4120", "2380"]}
    q = rec("organic 4,120 and paid 2,380", category="G", expected=exp)
    chart = '{"ui":"chart","kind":"bar","labels":["o","p"],"series":[{"name":"s","data":[4120,2380]}]}'
    assert ev.evaluate_item(q, wrap(chart)).passed
    short = '{"ui":"chart","kind":"bar","labels":["o","p"],"series":[{"name":"s","data":[4120,999]}]}'
    r = ev.evaluate_item(q, wrap(short))
    assert "MISSING_GROUNDING" in codes(r)
    assert any("999" in w for w in r.warnings)
    strict = ev.evaluate_item(q, wrap(chart.replace("2380", "2381")), strict_numbers=True)
    assert "UNGROUNDED_NUMBER" in codes(strict)


HIST = '{"ui":"chart","kind":"area","title":"MRR","labels":["Jun","Jul"],"series":[{"name":"MRR","data":[31.2,33.8]}]}'


def test_f_edit_preserved_vs_changed():
    exp = {"history_values": ["Jun", 31.2, 33.8, "MRR"], "components_any_of": ["chart"]}
    r0 = rec("Make that a bar chart and add Aug at 36.1", category="F", expected=exp,
             extra_msgs=())
    r0["messages"].insert(1, {"role": "assistant", "content": f"Here.\n```dyui\n{HIST}\n```\nDone."})
    ok = '{"ui":"chart","kind":"bar","title":"MRR","labels":["Jun","Jul","Aug"],"series":[{"name":"MRR","data":[31.2,33.8,36.1]}]}'
    assert ev.evaluate_item(r0, wrap(ok)).passed
    changed = ok.replace("33.8", "33.9")
    r = ev.evaluate_item(r0, wrap(changed))
    assert "EDIT_CHANGED" in codes(r)


CONFIRM_EXP = {"action": "cancel_subscription", "payload": {"plan": "pro"}, "components_any_of": ["confirm"]}


def test_e_action_match_and_wrong_action():
    good = '{"ui":"confirm","title":"Cancel Pro?","action":"cancel_subscription","data":{"plan":"pro"},"danger":true}'
    assert ev.evaluate_item(rec("Cancel my Pro plan", category="E", expected=CONFIRM_EXP), wrap(good)).passed
    wrong = good.replace("cancel_subscription", "delete_account")
    assert "ACTION_MISMATCH" in codes(ev.evaluate_item(rec(category="E", expected=CONFIRM_EXP), wrap(wrong)))
    badpayload = good.replace('"pro"', '"free"')
    assert "ACTION_PAYLOAD_MISMATCH" in codes(ev.evaluate_item(rec(category="E", expected=CONFIRM_EXP), wrap(badpayload)))


def test_e_default_action_and_button_items():
    exp = {"action": "confirm"}
    d = '{"ui":"confirm","title":"Sure?"}'
    assert ev.evaluate_item(rec(category="E", expected=exp), wrap(d)).passed
    btn = '{"ui":"buttons","items":[{"label":"Go","action":"go","data":{"x":1}}]}'
    assert ev.evaluate_item(rec(category="E", expected={"action": "go", "payload": {"x": 1}}), wrap(btn)).passed


def test_tolerates_empty_expected_and_empty_answer():
    assert ev.evaluate_item({"id": "X-1", "messages": []}, wrap(STAT)).passed
    assert "EMPTY_ANSWER" in codes(ev.evaluate_item(rec(), "  "))


def test_unclosed_block():
    r = ev.evaluate_item(rec(), f"Intro.\n```dyui\n{STAT}\n")
    assert "UNCLOSED_BLOCK" in codes(r)


def test_inline_fence_opener():
    r = ev.evaluate_item(rec(), f"Here you go ```dyui\n{STAT}\n```\nDone.")
    assert "INLINE_FENCE" in codes(r)


# ------------------------------------------------------------------ file level / CLI


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_evaluate_file_use_reference_and_answers(tmp_path):
    a = rec("Uptime?", category="B", expected={"components_any_of": ["stat"], "must_have_block": True})
    a["id"] = "B-1"
    a["reference"] = wrap(STAT)
    j = rec("hi", category="J", expected={"must_have_block": False})
    j["id"] = "J-1"
    j["reference"] = "Hello there, glad to see you."
    data = tmp_path / "eval.jsonl"
    _write_jsonl(data, [a, j])
    rep = ev.evaluate_file(data, use_reference=True, out=tmp_path / "res.jsonl", report_path=tmp_path / "rep.json")
    assert rep["n_items"] == 2 and rep["n_passed"] == 2 and rep["all_targets_met"]
    assert len((tmp_path / "res.jsonl").read_text().splitlines()) == 2
    saved = json.loads((tmp_path / "rep.json").read_text())
    assert any(m["key"] == "parse_valid" and m["passed"] for m in saved["metrics"])

    answers = tmp_path / "ans.jsonl"
    _write_jsonl(answers, [{"id": "B-1", "answer": wrap(CHART)}, {"id": "J-1", "answer": wrap(STAT)}])
    rep2 = ev.evaluate_file(data, answers_path=answers)
    assert rep2["n_passed"] == 0
    by_key = {m["key"]: m for m in rep2["metrics"]}
    assert by_key["overuse_j"]["passed"] is False and by_key["selection_b"]["passed"] is False
    assert rep2["by_category"]["J"]["failure_codes"]["OVERUSE"] == 1


def test_cli_exit_codes(tmp_path):
    a = rec("Uptime?", category="B", expected={"components_any_of": ["stat"]})
    a["reference"] = wrap(STAT)
    data = tmp_path / "eval.jsonl"
    _write_jsonl(data, [a])
    assert ev.main(["--data", str(data), "--use-reference", "--out", str(tmp_path / "o.jsonl")]) == 0
    bad = tmp_path / "bad.jsonl"
    a2 = dict(a)
    a2["reference"] = wrap(CHART)
    _write_jsonl(bad, [a2])
    assert ev.main(["--data", str(bad), "--use-reference", "--out", str(tmp_path / "o2.jsonl")]) == 1
    assert ev.main(["--data", str(bad), "--use-reference", "--out", str(tmp_path / "o3.jsonl"), "--no-fail"]) == 0
