# Hermes-Ops-Mini-Toolkit

A tiny, stdlib-only CLI toolkit to run the operational checks people repeatedly do before deployment.

## Why

Common deploy/preflight checks are easy to forget:

- Git branch/remote health
- SSH auth for GitHub remotes
- DNS/TXT record visibility
- API endpoint smoke checks
- Optional build commands

`hermes-ops` bundles these checks into one command with deterministic output.

## Install

```bash
python -m pip install .
```

## Usage

```bash
hermes-ops
```

This runs:

- `git` check (`git status`, remotes, branch)
- `ssh -T git@github.com`
- DNS TXT lookup for `_github-pages-challenge-gooniebot.gooniebot.com`
- smoke checks for:
  - `https://api.cryptonical.io/health`
  - `https://cryptonical.io/api/markets?symbol=SPY`

### JSON output

```bash
hermes-ops --json
```

### Add a custom TXT check and include builds

```bash
hermes-ops \
  --txt-host _github-pages-challenge-gooniebot.gooniebot.com \
  --txt-value 4cd9ea470243637059e42ec4695a76 \
  --build client: npm run build,api: npm run build
```

> `--build` accepts comma-separated `path:command` pairs.

### Example output

```json
[
  {"name":"git","status":"pass","details":"git context looks ready for publish"},
  {"name":"ssh","status":"pass","details":"SSH auth successful"},
  {"name":"dns","status":"pass","details":"TXT value present"},
  {"name":"smoke","status":"pass","details":"all endpoints returned success"}
]
```

## License

MIT
