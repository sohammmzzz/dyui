"""genui: streaming fence parser, partial JSON, validation, prompt, schemas, history."""
from __future__ import annotations

import json
import logging

import pytest

import dyui
from dyui import genui, ui
from dyui.genui import (
    ComponentEnd,
    ComponentError,
    ComponentStart,
    ComponentUpdate,
    FenceParser,
    TextDelta,
    parse_partial,
    serialize_history,
)

CAT = genui.catalog()


# ------------------------------------------------------------------ helpers
def run_chunks(text: str, chunks: list[str], catalog=CAT):
    p = FenceParser(catalog)
    events = []
    for c in chunks:
        events += p.feed(c)
    events += p.close()
    return events


def split_at(text: str, i: int) -> list[str]:
    return [text[:i], text[i:]]


def summarize(events):
    """A chunking-independent view: full prose + final nodes (ids normalized)."""
    prose = "".join(e.text for e in events if isinstance(e, TextDelta))
    finals = []
    for e in events:
        if isinstance(e, ComponentEnd):
            finals.append(_strip_ids(e.node))
        elif isinstance(e, ComponentError):
            n = e.node()
            finals.append(("error", n["props"]["raw"]))
    return prose, finals


def _strip_ids(node):
    if isinstance(node, dict):
        return {k: _strip_ids(v) for k, v in node.items() if k != "id"}
    if isinstance(node, list):
        return [_strip_ids(v) for v in node]
    return node


FIXTURES = {
    "basic": 'Intro **bold**.\n```dyui\n{"ui":"stat","label":"Revenue","value":"$48k","delta":"+12%"}\n'
             '{"ui":"quick_replies","options":["A","B"]}\n```\nOutro.',
    "array_line": 'Two:\n```dyui\n[{"ui":"stat","label":"A","value":1},{"ui":"stat","label":"B","value":2}]\n```\n',
    "json_tag": 'Here\n```json\n{"ui":"divider","label":"x"}\n```\nafter',
    "json_tag_not_ui": 'Code:\n```json\n{"a": 1}\n```\nend',
    "unterminated": 'Start\n```dyui\n{"ui":"stat","label":"Done","value":3}\n{"ui":"stat","label":"Cut',
    "nested": '```dyui\n{"ui":"card","title":"T","children":[{"ui":"stat","label":"A","value":1},'
              '{"ui":"tabs","tabs":[{"label":"x","children":[{"ui":"markdown","text":"hi"}]}]}]}\n```\n',
    "llm_id": '```dyui\n{"id":"my_stat","ui":"stat","label":"A","value":1}\n```\n',
    "unknown_and_bad": '```dyui\n{"ui":"nope"}\nnot json at all\n{"ui":"stat"}\n```\ntail',
    "unicode": 'Café ☕\n```dyui\n{"ui":"callout","text":"Ünïcödé — ok ✓","level":"success"}\n```\n日本語',
    "crlf": 'a\r\n```dyui\r\n{"ui":"divider"}\r\n```\r\nb',
}


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_every_split_point_gives_same_result(name):
    text = FIXTURES[name]
    whole = summarize(run_chunks(text, [text]))
    for i in range(len(text) + 1):
        assert summarize(run_chunks(text, split_at(text, i))) == whole, f"split at {i}"


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_char_by_char_and_three_way_splits(name):
    text = FIXTURES[name]
    whole = summarize(run_chunks(text, [text]))
    assert summarize(run_chunks(text, list(text))) == whole
    n = len(text)
    for a in range(0, n, max(1, n // 7)):
        for b in range(a, n, max(1, n // 5)):
            assert summarize(run_chunks(text, [text[:a], text[a:b], text[b:]])) == whole


def test_fence_lines_never_leak_into_prose():
    prose, finals = summarize(run_chunks(FIXTURES["basic"], list(FIXTURES["basic"])))
    assert "```" not in prose and '"ui"' not in prose
    assert prose.replace("\n", "") == "Intro **bold**.Outro."
    assert [f["ui"] for f in finals] == ["stat", "quick_replies"]


def test_array_line_yields_each_component():
    _, finals = summarize(run_chunks(FIXTURES["array_line"], [FIXTURES["array_line"]]))
    assert [f["props"]["label"] for f in finals] == ["A", "B"]


def test_json_tag_only_when_it_is_a_component():
    _, finals = summarize(run_chunks(FIXTURES["json_tag"], [FIXTURES["json_tag"]]))
    assert finals and finals[0]["ui"] == "divider"
    prose, finals = summarize(run_chunks(FIXTURES["json_tag_not_ui"], [FIXTURES["json_tag_not_ui"]]))
    assert not finals and '"a": 1' in prose  # ordinary JSON code stays prose


def test_unterminated_block_finalizes_complete_lines_and_errors_partial():
    ev = run_chunks(FIXTURES["unterminated"], [FIXTURES["unterminated"]])
    ends = [e for e in ev if isinstance(e, ComponentEnd)]
    errs = [e for e in ev if isinstance(e, ComponentError)]
    assert ends[0].node["props"]["label"] == "Done"
    assert len(errs) == 1


def test_nested_layout_children_validated():
    _, finals = summarize(run_chunks(FIXTURES["nested"], [FIXTURES["nested"]]))
    card = finals[0]
    assert card["ui"] == "card"
    assert [c["ui"] for c in card["children"]] == ["stat", "tabs"]
    tab_child = card["children"][1]["props"]["tabs"][0]["children"][0]
    assert tab_child["ui"] == "markdown"


def test_llm_supplied_id_kept_when_unique_and_replaced_when_duplicate():
    ev = run_chunks(FIXTURES["llm_id"], [FIXTURES["llm_id"]])
    assert [e for e in ev if isinstance(e, ComponentEnd)][0].node["id"] == "my_stat"
    p = FenceParser(CAT, used_ids={"my_stat"})
    ev = p.feed(FIXTURES["llm_id"]) + p.close()
    nid = [e for e in ev if isinstance(e, ComponentEnd)][0].node["id"]
    assert nid != "my_stat" and nid.startswith("c_")
    # ids reach the DOM: anything outside [A-Za-z0-9_-]{1,64} is replaced
    for bad in ('"><img onerror=1>', "a b", "x" * 65, ""):
        text = "```dyui\n" + json.dumps({"id": bad, "ui": "divider"}) + "\n```\n"
        nid = [e for e in run_chunks(text, [text]) if isinstance(e, ComponentEnd)][0].node["id"]
        assert nid.startswith("c_") and nid != bad


def test_generated_ids_are_unique_and_well_formed():
    text = "```dyui\n" + "\n".join('{"ui":"divider"}' for _ in range(50)) + "\n```\n"
    ids = [e.node["id"] for e in run_chunks(text, [text]) if isinstance(e, ComponentEnd)]
    assert len(set(ids)) == 50
    assert all(i.startswith("c_") and len(i) == 10 for i in ids)


def test_unknown_and_malformed_lines_become_errors_and_prose_survives():
    ev = run_chunks(FIXTURES["unknown_and_bad"], [FIXTURES["unknown_and_bad"]])
    prose = "".join(e.text for e in ev if isinstance(e, TextDelta))
    assert "tail" in prose
    errs = [e for e in ev if isinstance(e, ComponentError)]
    assert len(errs) >= 2  # unknown ui + stat missing required props
    assert all(e.node()["ui"] == "invalid" and e.node()["status"] == "error" for e in errs)


def test_streaming_start_update_end_sequence():
    text = '```dyui\n{"ui":"table","columns":["a","b"],"rows":[[1,2],[3,4],[5,6]],"caption":"' + "x" * 80 + '"}\n```\n'
    ev = run_chunks(text, list(text))
    starts = [e for e in ev if isinstance(e, ComponentStart)]
    updates = [e for e in ev if isinstance(e, ComponentUpdate)]
    ends = [e for e in ev if isinstance(e, ComponentEnd)]
    assert len(starts) == 1 and len(ends) == 1 and updates
    assert starts[0].id == ends[0].node["id"] and all(u.id == starts[0].id for u in updates)
    assert all(u.node["status"] == "streaming" for u in updates)
    assert len(updates) < len(text) // 4  # throttled


def test_parse_text_convenience():
    ev = genui.parse_text(FIXTURES["basic"])
    assert any(isinstance(e, ComponentEnd) for e in ev)


# ------------------------------------------------------------------ partial JSON
@pytest.mark.parametrize("text,expected", [
    ('{"a": 1', {}),            # a trailing number may still be growing: dropped
    ('{"a": 1,', {"a": 1}),
    ('{"a": "hel', {"a": "hel"}),
    ('{"a": [1, 2', {"a": [1]}),
    ('{"a": [1, 2]', {"a": [1, 2]}),
    ('{"a": {"b": [ {"c": tr', {"a": {"b": [{}]}}),
    ('{"a": 12', {}),            # an incomplete number is dropped
    ('{"a": 1, "b', {"a": 1}),   # an incomplete key is dropped
    ('{"a": "x\\u00', {"a": "x"}),
    ('[{"ui":"stat"', [{"ui": "stat"}]),
    ('{"t": "line\\nbreak", "n": null, "f": false', {"t": "line\nbreak", "n": None, "f": False}),
])
def test_parse_partial(text, expected):
    value = parse_partial(text)
    plain = json.loads(json.dumps(value, default=str))
    assert plain == expected


def test_parse_partial_marks_open_strings():
    v = parse_partial('{"src": "https://exa')
    assert isinstance(v["src"], genui.PartialStr)
    done = parse_partial('{"src": "https://example.com"}')
    assert not isinstance(done["src"], genui.PartialStr)


def test_partial_nodes_never_carry_half_urls():
    text = '```dyui\n{"ui":"image","src":"https://example.com/very/long/path/image.png","alt":"a"}\n```\n'
    for e in run_chunks(text, list(text)):
        if isinstance(e, ComponentUpdate):
            src = e.node["props"].get("src")
            assert src in (None, "https://example.com/very/long/path/image.png")


@pytest.mark.parametrize("text", ['{"a": "javascript:alert(1)"', '{"href": "javascript:alert(1)"}'])
def test_partial_unsafe_urls_dropped(text):
    stream = '```dyui\n{"ui":"link_preview","url":"javascript:alert(1)","title":"x"}\n```\n'
    for e in run_chunks(stream, list(stream)):
        if isinstance(e, ComponentUpdate):
            assert "javascript" not in json.dumps(e.node)


# ------------------------------------------------------------------ validation
def test_unknown_props_dropped_and_values_coerced():
    node = CAT.validate({"ui": "stat", "label": 5, "value": "12", "bogus": 1, "__x": 2})
    assert node["ui"] == "stat" and node["props"]["label"] == "5"
    assert "bogus" not in node["props"] and "__x" not in node["props"]
    t = CAT.validate({"ui": "progress", "value": "42", "max": "100"})
    assert t["props"]["value"] == 42


def test_invalid_optional_prop_dropped_not_fatal():
    node = CAT.validate({"ui": "callout", "text": "hi", "level": "purple"})
    assert node["ui"] == "callout" and "level" not in node["props"] or node["props"]["level"] in ("info",)


def test_unknown_component_is_invalid():
    node = CAT.validate({"ui": "spaceship"})
    assert node["ui"] == "invalid" and "unknown" in node["props"]["error"]


@pytest.mark.parametrize("obj", [
    {"ui": "image", "src": "javascript:alert(1)"},
    {"ui": "image", "src": "data:image/png;base64,AAAA"},
    {"ui": "video", "src": "vbscript:x"},
    {"ui": "file", "name": "a", "url": "javascript:x"},
])
def test_unsafe_required_urls_make_component_invalid(obj):
    assert CAT.validate(obj)["ui"] == "invalid"


def test_unsafe_optional_and_nested_urls_dropped():
    node = CAT.validate({"ui": "card", "title": "t", "image": "javascript:x",
                         "children": [{"ui": "link_preview", "url": "https://ok.com", "image": "data:x"}]})
    assert "image" not in node["props"]
    child = node["children"][0]
    assert child["ui"] == "link_preview" and "image" not in child["props"]
    src = CAT.validate({"ui": "sources", "items": [{"title": "a", "url": "javascript:1"},
                                                   {"title": "b", "url": "https://b.com"}]})
    assert [i["url"] for i in src["props"]["items"]] == ["https://b.com"]
    gal = CAT.validate({"ui": "gallery", "images": [{"src": "javascript:1"}, {"src": "https://i.com/a.png"}]})
    assert [i["src"] for i in gal["props"]["images"]] == ["https://i.com/a.png"]


def test_markdown_links_left_to_the_client_renderer():
    node = CAT.validate({"ui": "markdown", "text": "[x](javascript:alert(1))"})
    assert node["ui"] == "markdown"  # the web renderer sanitizes link hrefs (no raw HTML, safe protocols)


def test_custom_component_expands_with_component_marker():
    app = dyui.App(persist=False)

    @app.component
    class Flight(dyui.Component):
        """A bookable flight."""
        airline: str
        price: float

        def render(self):
            return ui.Card(self.airline, ui.Stat("Price", f"${self.price:.0f}"),
                           actions=[ui.Button("Book", action="book", data={"airline": self.airline})])

    node = app.untrusted_catalog.validate({"ui": "flight", "airline": "TAP", "price": "189"})
    assert node["ui"] == "card" and node["props"]["__component__"] == "flight"
    assert node["children"][0]["props"]["value"] == "$189"
    bad = app.untrusted_catalog.validate({"ui": "flight", "airline": "TAP"})
    assert bad["ui"] == "invalid"


def test_custom_render_failure_is_invalid_not_crash():
    app = dyui.App(persist=False)

    @app.component
    class Boom(dyui.Component):
        """Explodes."""
        x: int

        def render(self):
            raise RuntimeError("secret detail")

    node = app.untrusted_catalog.validate({"ui": "boom", "x": 1})
    assert node["ui"] == "invalid" and "secret detail" not in json.dumps(node)


def test_repair_message_shape():
    node = CAT.validate({"ui": "stat"})
    msg = json.loads(genui.repair_message(node["props"]["error"], component="stat"))
    assert msg["error"] == "VALIDATION_FAILED" and msg["component"] == "stat"


# ------------------------------------------------------------------ prompt
def test_prompt_structure_and_determinism():
    p1 = CAT.prompt()
    p2 = genui.catalog().prompt()
    assert p1 == p2
    assert p1.startswith("## UI components")
    assert "```dyui" in p1 and '{"ui":' in p1
    names_in_order = [line.split("(")[0] for line in p1.splitlines() if "(" in line and line[:1].isalpha()]
    assert "table" in names_in_order and "stat" in names_in_order
    assert "html(" not in p1 and "invalid(" not in p1


def test_prompt_order_builtins_then_customs_in_registration_order():
    app = dyui.App(persist=False)

    @app.component
    class Zeta(dyui.Component):
        """Z."""
        a: str

        def render(self):
            return ui.Markdown(self.a)

    @app.component
    class Alpha(dyui.Component):
        """A."""
        a: str

        def render(self):
            return ui.Markdown(self.a)

    names = app.catalog.names
    assert names[-2:] == ["zeta", "alpha"]
    assert names[:-2] == [c for c in genui.catalog().names]
    p = app.catalog.prompt()
    assert p.index("zeta(") < p.index("alpha(")


def test_tools_mode_prompt_has_no_fence_instructions():
    p = CAT.prompt(mode="tools")
    assert "render_" in p and "```dyui" not in p


def test_only_without_and_groups():
    sub = CAT.only("stat", ui.Table)
    assert sub.names == ["table", "stat"] or set(sub.names) == {"table", "stat"}
    assert "chart" not in CAT.without("chart").names
    data = dyui.catalog("data")
    assert "table" in data.names and "card" not in data.names


def test_token_estimate_and_warning(caplog):
    small = CAT.only("stat")
    assert 0 < small.token_estimate() < CAT.token_estimate()
    app = dyui.App(persist=False)
    for i in range(40):
        app.component(type(f"Big{i}", (dyui.Component,), {
            "__doc__": "A very long description " * 20, "__annotations__": {"a": str},
            "render": lambda self: ui.Markdown("x"), "__module__": "tests.fake"}))
    with caplog.at_level(logging.WARNING, logger="dyui"):
        app.catalog.prompt()
    assert any("tokens" in r.getMessage() for r in caplog.records)


# ------------------------------------------------------------------ strict schemas / tools
def _walk_objects(schema):
    if isinstance(schema, dict):
        if schema.get("type") == "object" or "properties" in schema:
            yield schema
        for v in schema.values():
            yield from _walk_objects(v)
    elif isinstance(schema, list):
        for v in schema:
            yield from _walk_objects(v)


@pytest.mark.parametrize("name", genui.catalog().names)
def test_strict_schema_rules(name):
    schema = CAT.json_schema()[name]
    for obj in _walk_objects(schema):
        if "properties" in obj:
            assert obj.get("additionalProperties") is False, name
            assert set(obj.get("required", [])) == set(obj["properties"]), name
    def keys(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "properties" and isinstance(v, dict):  # property *names* aren't keywords
                    for sub in v.values():
                        yield from keys(sub)
                    continue
                yield k
                yield from keys(v)
        elif isinstance(x, list):
            for v in x:
                yield from keys(v)

    assert "default" not in set(keys(schema)), name


def test_tool_schemas_openai_and_anthropic():
    oa = CAT.tool_schemas("openai")
    an = CAT.tool_schemas("anthropic")
    assert len(oa) == len(an) == len(CAT.names)
    assert all(t["type"] == "function" and t["function"]["name"].startswith("render_") for t in oa)
    assert all(t["function"].get("strict") is True for t in oa)
    assert all(t["name"].startswith("render_") and "input_schema" in t for t in an)
    assert {t["function"]["name"] for t in oa} == {t["name"] for t in an}
    json.dumps(oa), json.dumps(an)


def test_tool_call_args_round_trip_through_validation():
    # strict mode sends every key; optionals as null, children as JSON text
    args = {"title": "T", "subtitle": None, "image": None, "badge": None,
            "children": [json.dumps({"ui": "stat", "label": "A", "value": 1})], "actions": None}
    node = CAT.validate({"ui": "card", **args})
    assert node["ui"] == "card" and node["children"][0]["ui"] == "stat"


# ------------------------------------------------------------------ history
def test_history_serialization():
    msgs = [
        {"id": "m1", "role": "user", "parts": [{"type": "text", "text": "hi"}]},
        {"id": "m2", "role": "assistant", "parts": [
            {"type": "reasoning", "text": "thinking..."},
            {"type": "text", "text": "Here you go."},
            {"type": "step", "step": {"id": "s", "title": "search", "status": "done"}},
            {"type": "ui", "node": {"id": "c_1", "ui": "stat", "props": {"label": "A", "value": 1,
                                                                          "__resolved__": {"label": "x"}},
                                    "status": "done"}},
            {"type": "ui", "node": {"id": "c_2", "ui": "invalid", "props": {"raw": "x", "error": "e"}}},
        ]},
        {"id": "m3", "role": "user", "parts": [{"type": "text", "text": "Book"}],
         "meta": {"llm_text": '[action:book] {"n":1}'}},
    ]
    h = serialize_history(msgs)
    assert [m["role"] for m in h] == ["user", "assistant", "user"]
    a = h[1]["content"]
    assert "Here you go." in a and "thinking" not in a and "search" not in a
    assert '```dyui\n{"ui":"stat","label":"A","value":1}\n```' in a
    assert "c_1" not in a and "__resolved__" not in a and "invalid" not in a
    assert h[2]["content"].startswith("[action:book]")


def test_action_text():
    assert genui.action_text("pick", {"a": 1}, {"b": "x"}) == '[action:pick] {"a":1,"b":"x"}'


def test_history_round_trips_through_parser():
    node = ui.Card("T", ui.Stat("A", 1)).to_node()
    msgs = [{"id": "m", "role": "assistant", "parts": [{"type": "ui", "node": node}]}]
    text = serialize_history(msgs)[0]["content"]
    _, finals = summarize(run_chunks(text, [text]))
    assert _strip_ids(finals[0]) == _strip_ids(dict(node, status="done"))
