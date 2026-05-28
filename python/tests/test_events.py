from dyui import UIEvent, DYUI_KEY, is_dyui_payload, parse_envelope


def test_event_defaults():
    ev = UIEvent(component="table")
    assert ev.component == "table"
    assert ev.status == "done"
    assert ev.surface == "default"
    assert len(ev.id) == 12
    assert ev.props == {}


def test_envelope_roundtrip():
    ev = UIEvent(component="stat", props={"value": 42}, status="active", title="T")
    env = ev.envelope()
    assert DYUI_KEY in env
    assert is_dyui_payload(env)
    back = parse_envelope(env)
    assert back.id == ev.id
    assert back.props == {"value": 42}
    assert back.status == "active"
    assert back.title == "T"


def test_is_dyui_payload_negative():
    assert not is_dyui_payload({"foo": 1})
    assert not is_dyui_payload("string")
    assert not is_dyui_payload(None)
