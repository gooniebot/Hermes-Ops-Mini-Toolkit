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
- DNS TXT lookup (only if `--txt-host` is provided)
- Smoke checks for URLs passed via `--smoke`

### JSON output

```bash
hermes-ops --json
```

### Generic smoke-check mode (user supplied URLs)

```bash
hermes-ops \
  --smoke "https://google.com,https://duckduckgo.com"
```

### Presets

Use `--preset` to quickly load common endpoint sets:

- `neutral-web`: `https://google.com`, `https://duckduckgo.com`
- `minimal`: no smoke endpoints

```bash
hermes-ops --preset neutral-web
```

If a preset name is unknown, it returns a warning and continues with other checks.

### Add a custom TXT check and include builds

```bash
hermes-ops \
  --txt-host _github-pages-challenge-example.org.example \
  --txt-value 4cd9ea470243637059e42ec4695a76 \
  --build client: npm run build,api: npm run build
```

> `--build` accepts comma-separated `path:command` pairs.

### Example output

```json
[
  {"name":"git","status":"pass","details":"git context looks ready for publish"},
  {"name":"ssh","status":"pass","details":"SSH auth successful"},
  {"name":"dns","status":"warn","details":"TXT host not provided"},
  {"name":"smoke","status":"pass","details":"all endpoints returned success"}
]
```

If no `--smoke` endpoints are provided, smoke result shows warning status and empty endpoint data.

## License

MIT
