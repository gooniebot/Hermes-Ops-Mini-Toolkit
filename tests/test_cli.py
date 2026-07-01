from hermes_ops_mini_toolkit.cli import _run_cmd, _has_cmd


def test_git_command_exists():
    assert _has_cmd("git") is True


def test_run_cmd_returns_completed_process():
    p = _run_cmd(["python", "-V"])
    assert p.returncode == 0
