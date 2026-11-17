""".env loading for `dyui run` and the missing-API-key error."""
from __future__ import annotations

import pytest

from dyui import cli
from dyui._env import find_dotenv, load_dotenv, parse_dotenv
from dyui.llm import MissingAPIKeyError, PROVIDERS
from dyui.llm import _stream


# ----------------------------------------------------------------- parser
def test_parse_basic_forms():
    text = (
        "# a comment\n"
        "\n"
        "NVIDIA_API_KEY=nvapi-abc\n"
        "export OPENAI_API_KEY=sk-123\n"
        "SPACED = padded value  \n"
        'DOUBLE="has # hash and \\"quotes\\"\\nnewline"\n'
        "SINGLE='literal \\n $HOME # kept'\n"
        "INLINE=value # trailing comment\n"
        "URL=https://x.test/#frag\n"
        "EMPTY=\n"
        "NO_INTERP=$HOME/x\n"
    )
    assert parse_dotenv(text) == {
        "NVIDIA_API_KEY": "nvapi-abc",
        "OPENAI_API_KEY": "sk-123",
        "SPACED": "padded value",
        "DOUBLE": 'has # hash and "quotes"\nnewline',
        "SINGLE": "literal \\n $HOME # kept",
        "INLINE": "value",
        "URL": "https://x.test/#frag",
        "EMPTY": "",
        "NO_INTERP": "$HOME/x",
    }


def test_parse_skips_malformed_lines():
    text = "just words\n=novalue\n1BAD=x\nOPEN=\"never closed\nJUNK=\"a\" b\nGOOD=1\r\n"
    assert parse_dotenv(text) == {"GOOD": "1"}


def test_load_never_overrides_by_default(tmp_path):
    f = tmp_path / ".env"
    f.write_text("A=from-file\nB=from-file\n", encoding="utf-8")
    env = {"A": "from-shell"}
    assert load_dotenv(f, environ=env) == ["B"]
    assert env == {"A": "from-shell", "B": "from-file"}
    assert load_dotenv(f, environ=env, override=True) == ["A", "B"]
    assert env["A"] == "from-file"


def test_load_missing_file_and_bom(tmp_path):
    assert load_dotenv(tmp_path / "nope.env", environ={}) == []
    f = tmp_path / ".env"
    f.write_bytes("\ufeffKEY=v\n".encode("utf-8"))  # Notepad's UTF-8 BOM
    env: dict[str, str] = {}
    assert load_dotenv(f, environ=env) == ["KEY"] and env == {"KEY": "v"}


def test_find_dotenv_order(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert find_dotenv([a, b]) is None
    (b / ".env").write_text("X=1\n", encoding="utf-8")
    assert find_dotenv([a, b]) == (b / ".env").resolve()
    (a / ".env").write_text("X=2\n", encoding="utf-8")
    assert find_dotenv([a, b]) == (a / ".env").resolve()


# ----------------------------------------------------------------- dyui run
@pytest.fixture
def run_app(tmp_path, monkeypatch):
    """A project dir with app.py, the CWD elsewhere, and _serve stubbed out."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "app.py").write_text("import dyui\napp = dyui.App(title='T', persist=False)\n", encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    served = []
    monkeypatch.setattr(cli, "_serve", lambda *a, **k: served.append(a))
    for k in ("DYUI_TEST_KEY", "DYUI_TEST_OTHER"):
        monkeypatch.setenv(k, "x")  # recorded, so whatever the test loads is undone afterwards
        monkeypatch.delenv(k)
    return proj, cwd, served


def test_run_loads_env_next_to_app(run_app, capsys, monkeypatch):
    import os

    proj, cwd, served = run_app
    (proj / ".env").write_text("DYUI_TEST_KEY=secret-value-123\n", encoding="utf-8")
    (cwd / ".env").write_text("DYUI_TEST_OTHER=from-cwd\n", encoding="utf-8")
    assert cli.main(["run", str(proj / "app.py")]) == 0
    out = capsys.readouterr().out
    assert os.environ["DYUI_TEST_KEY"] == "secret-value-123"
    assert "DYUI_TEST_OTHER" not in os.environ  # the app's own .env wins over the CWD's
    assert "DYUI_TEST_KEY" in out and "1 key" in out
    assert "secret-value-123" not in out  # names only, never values
    assert served


def test_run_falls_back_to_cwd_env(run_app, capsys):
    import os

    proj, cwd, _ = run_app
    (cwd / ".env").write_text("DYUI_TEST_OTHER=from-cwd\n", encoding="utf-8")
    assert cli.main(["run", str(proj / "app.py")]) == 0
    assert os.environ["DYUI_TEST_OTHER"] == "from-cwd"


def test_run_does_not_override_shell(run_app, capsys, monkeypatch):
    import os

    proj, _, _ = run_app
    monkeypatch.setenv("DYUI_TEST_KEY", "from-shell")
    (proj / ".env").write_text("DYUI_TEST_KEY=from-file\n", encoding="utf-8")
    assert cli.main(["run", str(proj / "app.py")]) == 0
    assert os.environ["DYUI_TEST_KEY"] == "from-shell"
    out = capsys.readouterr().out
    assert "0 keys" in out and "kept: DYUI_TEST_KEY" in out and "from-file" not in out


def test_run_no_env_file(run_app, capsys):
    import os

    proj, _, served = run_app
    (proj / ".env").write_text("DYUI_TEST_KEY=x\n", encoding="utf-8")
    assert cli.main(["run", str(proj / "app.py"), "--no-env-file"]) == 0
    assert "DYUI_TEST_KEY" not in os.environ and served
    assert "loaded" not in capsys.readouterr().out


def test_run_explicit_env_file(run_app, capsys, tmp_path):
    import os

    proj, _, _ = run_app
    custom = tmp_path / "prod.env"
    custom.write_text("DYUI_TEST_OTHER=custom\n", encoding="utf-8")
    (proj / ".env").write_text("DYUI_TEST_KEY=x\n", encoding="utf-8")
    assert cli.main(["run", str(proj / "app.py"), "--env-file", str(custom)]) == 0
    assert os.environ["DYUI_TEST_OTHER"] == "custom" and "DYUI_TEST_KEY" not in os.environ
    assert cli.main(["run", str(proj / "app.py"), "--env-file", str(tmp_path / "missing.env")]) == 2


def test_env_is_loaded_before_the_app_imports(run_app, capsys):
    proj, _, _ = run_app
    (proj / "app.py").write_text(
        "import os, dyui\napp = dyui.App(title=os.environ['DYUI_TEST_KEY'], persist=False)\n", encoding="utf-8")
    (proj / ".env").write_text("DYUI_TEST_KEY=Titled\n", encoding="utf-8")
    assert cli.main(["run", str(proj / "app.py")]) == 0


# ----------------------------------------------------------------- missing key
@pytest.mark.parametrize("name", ["nvidia", "openai", "groq", "gemini"])
def test_missing_key_error_names_the_variable(monkeypatch, name):
    provider = PROVIDERS[name]
    for env in provider.key_envs:
        monkeypatch.delenv(env, raising=False)
    with pytest.raises(MissingAPIKeyError) as e:
        _stream._make_openai_client(provider, None, None)
    msg = str(e.value)
    assert all(env in msg for env in provider.key_envs)
    assert ".env" in msg and "api-keys" in msg
    assert isinstance(e.value, RuntimeError)  # back-compat: it used to be a RuntimeError


def test_missing_anthropic_key(monkeypatch):
    for env in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
        monkeypatch.delenv(env, raising=False)
    pytest.importorskip("anthropic")
    with pytest.raises(MissingAPIKeyError, match="ANTHROPIC_API_KEY"):
        _stream._make_anthropic_client(PROVIDERS["anthropic"], None, None)
    # a gateway at a custom URL may authenticate differently: no early error
    _stream._make_anthropic_client(PROVIDERS["anthropic"], "http://gateway.test", None)
    # an explicit key is enough
    _stream._make_anthropic_client(PROVIDERS["anthropic"], None, "sk-ant-test")


def test_keyless_provider_still_works(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    client = _stream._make_openai_client(PROVIDERS["ollama"], None, None)
    assert client is not None


async def test_missing_key_reaches_the_chat(monkeypatch):
    """The chat shows the missing-key message (it holds env var names, never values)."""
    import httpx

    import dyui

    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    app = dyui.App(persist=False)

    @app.on_message
    async def reply(msg, chat):
        async for part in dyui.llm.stream("nvidia/some/model", chat.history, components=app.catalog):
            yield part

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/chat", json={"message": {"text": "hi"}})
    assert "event: error" in r.text and "NVIDIA_API_KEY is not set" in r.text


def test_public_error_for_401():
    from dyui.app import _public_error

    class Unauthorized(Exception):
        status_code = 401

    assert "401" in _public_error(Unauthorized("key sk-leak"))
    assert "sk-leak" not in _public_error(Unauthorized("key sk-leak"))


@pytest.mark.parametrize("template", ["basic", "nvidia", "openai", "anthropic", "langgraph"])
def test_templates_ignore_env_and_document_auto_loading(tmp_path, template, capsys):
    dest = tmp_path / template
    assert cli.main(["new", str(dest), "--template", template]) == 0
    ignore = (dest / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignore and ".dyui/" in ignore
    readme = (dest / "README.md").read_text(encoding="utf-8")
    assert "grep" not in readme and "xargs" not in readme  # the old bash-only one-liner
    if (dest / ".env.example").exists():
        assert "loads .env" in readme
