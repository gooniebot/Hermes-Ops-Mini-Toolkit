from hermes_ops_mini_toolkit.cli import PRESETS, check_dns, check_smoke, resolve_smoke_endpoints, _has_cmd, _run_cmd


def test_git_command_exists():
    assert _has_cmd("git") is True


def test_run_cmd_returns_completed_process():
    p = _run_cmd(["python", "-V"])
    assert p.returncode == 0


def test_smoke_without_endpoints_warns():
    result = check_smoke([])
    assert result["status"] == "warn"
    assert result["name"] == "smoke"
    assert result["data"]["endpoints"] == {}


def test_dns_without_host_warns():
    result = check_dns("")
    assert result["status"] == "warn"
    assert result["name"] == "dns"


def test_resolve_smoke_prefers_explicit_smoke_over_preset():
    assert resolve_smoke_endpoints("example.com,openai.com", "neutral-web") == ["example.com", "openai.com"]


def test_resolve_smoke_from_preset():
    assert resolve_smoke_endpoints("", "neutral-web") == PRESETS["neutral-web"]


def test_resolve_smoke_unknown_preset_returns_empty():
    assert resolve_smoke_endpoints("", "not-a-real-preset") == []
