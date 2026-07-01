"""Hermes Ops Mini-Toolkit CLI.

Small, dependency-light toolkit for quick operational pre-deploy checks.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path
import socket


def _run_cmd(cmd: List[str], cwd: str = ".", check: bool = False, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def _clean_result(name: str, status: str, details: str, data: Optional[dict] = None) -> Dict:
    payload = {
        "name": name,
        "status": status,
        "details": details,
    }
    if data is not None:
        payload["data"] = data
    return payload


def _has_cmd(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def check_git(cwd: str = ".") -> Dict:
    if not _has_cmd("git"):
        return _clean_result("git", "fail", "git command not found")

    ok = True
    details = []
    data = {}

    try:
        r = _run_cmd(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
        if r.returncode != 0:
            return _clean_result("git", "fail", "not a git repository", {"cmd": "git rev-parse --show-toplevel", "stderr": r.stderr.strip()})
        data["toplevel"] = r.stdout.strip()

        r = _run_cmd(["git", "remote", "-v"], cwd=cwd)
        data["remotes"] = [line.strip() for line in r.stdout.splitlines() if line.strip()]

        r = _run_cmd(["git", "branch", "--show-current"], cwd=cwd)
        data["branch"] = r.stdout.strip() or "<none>"

        status = _run_cmd(["git", "status", "-sb"], cwd=cwd)
        data["status"] = status.stdout.strip().splitlines() or []

        # ahead/behind if upstream exists
        r = _run_cmd(["git", "rev-parse", "--abbrev-ref", "@{upstream}"], cwd=cwd)
        if r.returncode == 0:
            upstream = r.stdout.strip()
            drift = _run_cmd(["git", "rev-list", "--left-right", "--count", f"{upstream}...HEAD"], cwd=cwd)
            if drift.returncode == 0:
                behind, ahead = drift.stdout.strip().split("	")
                data["behind_ahead"] = {"behind": int(behind), "ahead": int(ahead)}
                if int(ahead) > 0:
                    details.append(f"branch {data['branch']} is ahead by {ahead} commit(s)")
                if int(behind) > 0:
                    details.append(f"branch {data['branch']} is behind by {behind} commit(s)")
            if data["behind_ahead"].get("behind",0) > 0:
                ok = False
        else:
            details.append("no upstream set for current branch")
            ok = False

        if not ok:
            return _clean_result("git", "warn", "; ".join(details), data)
        return _clean_result("git", "pass", "git context looks ready for publish", data)
    except Exception as exc:  # pragma: no cover
        return _clean_result("git", "fail", f"unexpected error: {exc}")


def check_ssh(host: str) -> Dict:
    r = _run_cmd(["ssh", "-o", "BatchMode=yes", "-T", host], capture=True)
    output = (r.stdout or "") + (r.stderr or "")

    if "successfully authenticated" in output or "Hi " in output:
        return _clean_result("ssh", "pass", "SSH auth successful", {"host": host, "stdout": output.strip(), "code": r.returncode})

    if r.returncode == 0 and output.strip() == "":
        return _clean_result("ssh", "fail", "SSH command returned success but no auth marker", {"host": host})

    return _clean_result("ssh", "fail", "SSH auth failed", {"host": host, "code": r.returncode, "output": output.strip()})


def check_dns(name: str, expected_txt: Optional[str] = None) -> Dict:
    info = {}

    if not name.strip():
        return _clean_result("dns", "warn", "TXT host not provided", {"host": name})

    # A/AAAA via socket
    try:
        infos = socket.getaddrinfo(name, None)
        addrs = sorted({x[4][0] for x in infos})
        info["resolved_ips"] = addrs
    except Exception as exc:
        info["resolved_ips_error"] = str(exc)

    txt_values = []
    if _has_cmd("dig"):
        r = _run_cmd(["dig", "+short", "TXT", name], capture=True)
        txt_values = [line.strip('"') for line in r.stdout.splitlines() if line.strip()]
        info["txt"] = txt_values
        if r.returncode != 0:
            return _clean_result("dns", "fail", "dig failed", {"host": name, **info})
    else:
        return _clean_result("dns", "warn", "dig command unavailable; cannot read TXT records", {"host": name, **info})

    if expected_txt:
        if expected_txt in txt_values:
            return _clean_result("dns", "pass", "TXT value present", {"host": name, "txt": txt_values, "expected_txt": expected_txt})
        return _clean_result("dns", "fail", "Expected TXT value missing", {"host": name, "expected_txt": expected_txt, "txt": txt_values})

    return _clean_result("dns", "pass", "DNS lookup succeeded", {"host": name, **info})


def _http_get(url: str, timeout: int = 8) -> Dict:
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "hermes-ops-mini-toolkit")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"status": r.status, "reason": r.reason}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "reason": getattr(e, "reason", "HTTPError")}
    except Exception as exc:
        return {"error": str(exc)}


def check_smoke(endpoints: List[str], timeout: int = 8) -> Dict:
    if not endpoints:
        return _clean_result(
            "smoke",
            "warn",
            "No smoke endpoints provided",
            {"endpoints": {}},
        )

    results = {}
    all_ok = True
    for url in endpoints:
        if "://" not in url:
            url = f"https://{url}"
        r = _http_get(url, timeout=timeout)
        if "error" in r:
            all_ok = False
            results[url] = {"status": "error", **r}
        else:
            results[url] = r
            if r["status"] >= 400:
                all_ok = False

    return _clean_result(
        "smoke",
        "pass" if all_ok else "warn",
        "all endpoints returned success" if all_ok else "one or more endpoint checks failed",
        {"endpoints": results},
    )


def run_build(project_path: str, command: str, base_cwd: str = ".") -> Dict:
    cwd = str(Path(base_cwd) / project_path)
    if not Path(cwd).is_dir():
        return _clean_result("build", "warn", f"build path not found", {"command": command, "path": cwd})

    if not _has_cmd(command.split()[0]):
        return _clean_result("build", "fail", f"command '{command.split()[0]}' not found", {"cwd": cwd})

    r = _run_cmd(command.split(), cwd=cwd)
    if r.returncode == 0:
        return _clean_result("build", "pass", "build command succeeded", {"command": command, "cwd": cwd})
    return _clean_result("build", "fail", "build command failed", {
        "command": command,
        "cwd": cwd,
        "stdout": r.stdout[-800:],
        "stderr": r.stderr[-800:],
    })


def check_build(projects: List[str], command: str, base_cwd: str = ".") -> List[Dict]:
    results = []
    for p in projects:
        results.append(run_build(p, command, base_cwd))
    return results


def format_output(results: List[Dict], json_mode: bool = False) -> None:
    if json_mode:
        print(json.dumps(results, indent=2))
        return

    for result in results:
        status = result["status"].upper().ljust(5)
        print(f"[{status}] {result['name']}: {result['details']}")
        if "data" in result:
            print(f"  -> {json.dumps(result['data'])}")


@dataclass
class CLIConfig:
    cwd: str
    json: bool
    host: str
    txt_host: str
    txt_value: Optional[str]
    smoke_endpoints: List[str]
    build_projects: List[str]
    build_command: str


def parse_args(argv: Optional[List[str]] = None):
    p = argparse.ArgumentParser(description="Hermes Ops Mini-Toolkit")
    p.add_argument("--cwd", default=".", help="Working directory")
    p.add_argument("--json", action="store_true", help="Machine-readable output")
    p.add_argument("--host", default="git@github.com", help="SSH host to test")
    p.add_argument("--txt-host", default="", help="TXT lookup host (required when checking DNS TXT)")
    p.add_argument("--txt-value", default=None, help="Expected TXT token")
    p.add_argument(
        "--smoke",
        default="",
        help="Comma-separated endpoint URLs for generic smoke checks. Leave empty to skip.",
    )
    p.add_argument("--build", default="", help="Comma-separated project:command pairs")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    cfg = CLIConfig(
        cwd=args.cwd,
        json=args.json,
        host=args.host,
        txt_host=args.txt_host,
        txt_value=args.txt_value,
        smoke_endpoints=[x.strip() for x in args.smoke.split(",") if x.strip()],
        build_projects=[x for x in args.build.split(",") if x.strip()],
        build_command="npm run build",
    )

    results = []
    results.append(check_git(cfg.cwd))
    results.append(check_ssh(cfg.host))
    results.append(check_dns(cfg.txt_host, cfg.txt_value))
    results.append(check_smoke(cfg.smoke_endpoints))

    # Build check format: "path:cmd" | default command
    for item in cfg.build_projects:
        if ":" in item:
            path, cmd = item.split(":", 1)
            results.extend(check_build([path.strip()], cmd.strip() or cfg.build_command, cfg.cwd))
        else:
            path = item.strip()
            if path:
                results.extend(check_build([path], cfg.build_command, cfg.cwd))

    format_output(results, json_mode=cfg.json)

    has_fail = any(r["status"] == "fail" for r in results)
    return 1 if has_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
