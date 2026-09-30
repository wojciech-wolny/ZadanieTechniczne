---
name: github-actions
description: Writes and reviews simple GitHub Actions workflows for this project running on self-hosted runners with uv, ruff and pytest. Use when creating or changing files in .github/workflows, adding a CI check, or when a pipeline fails.
---

# GitHub Actions

Pipelines must be simple: one workflow, parallel jobs, a few readable steps. Every step must also work when run by hand on a developer machine.

## Runner

1. Always `runs-on: self-hosted` and no other label. Never GitHub hosted labels such as `ubuntu-latest`, and never an extra label such as `linux`.
2. Runners may be ephemeral, so nothing beyond `git` can be assumed installed.
3. Install `uv` inside the job with `astral-sh/setup-uv`; `uv` then provides Python from `.python-version`. No `actions/setup-python`.
4. Commands are plain `uv` calls that behave the same in bash and PowerShell, so they also run on the Windows developer machine.
5. Lint, format, test, and audit are separate jobs with no `needs`, so they start together. Tests use free ports and temporary directories only, because several jobs may share one runner machine.

## Rules

1. Workflow lives in `.github/workflows/ci.yml`. Add a new file only for a different trigger (for example a scheduled audit).
2. Triggers: `push` to `main` and `pull_request` to `main`, plus `workflow_dispatch`.
3. `permissions: contents: read` at the top. Grant more only per job and only when needed.
4. `concurrency` group per ref with `cancel-in-progress: true`.
5. `timeout-minutes` on every job (10 is enough).
6. Only official actions (`actions/*`) plus `astral-sh/setup-uv` from the uv authors, pinned to a major version. No other third party actions.
7. Use `uv sync --locked` so CI fails when `uv.lock` is out of date.
8. Steps mirror local commands: lint, format check, tests. Nothing CI only.
9. No secrets are needed. Never echo environment variables.
10. Tests must not need a manually started server and must use free local ports, because several jobs may share one runner machine.
11. The test job sets `HTTP_HOST`, `HTTP_PORT`, `TCP_HOST`, `TCP_PORT`, `MAX_TASKS`, and `PRODUCER_IDLE_SECONDS` to the same values as `.env.example`. The programs read `.env` only, and that file is not committed. The process environment wins over `.env`, and a reused runner may already define the names. Do not echo the values.

## Self-hosted security

1. Self-hosted runners execute any code from the workflow. Keep the repository private, or in a public repository require approval for workflows from outside collaborators.
2. Skip pull requests from forks: `if: github.event.pull_request.head.repo.full_name == github.repository || github.event_name != 'pull_request'`.
3. Workflows never use Docker. Fork pull requests must never reach these runners.

## Template

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository
    runs-on: self-hosted
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --locked
      - run: uv run ruff check .

  format:
    if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository
    runs-on: self-hosted
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --locked
      - run: uv run ruff format --check .

  test:
    if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository
    runs-on: self-hosted
    timeout-minutes: 10
    permissions:
      contents: read
      actions: write
    env:
      HTTP_HOST: 127.0.0.1
      HTTP_PORT: "8000"
      TCP_HOST: 127.0.0.1
      TCP_PORT: "9000"
      MAX_TASKS: "32"
      PRODUCER_IDLE_SECONDS: "30"
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --locked
      - run: uv run pytest -q --html=report.html --self-contained-html
      - if: always()
        uses: actions/upload-artifact@v7
        with:
          name: test-report
          path: report.html
          if-no-files-found: warn

  audit:
    if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository
    runs-on: self-hosted
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --locked
      - run: uv run --with "pip-audit==2.*" pip-audit
```

## Checklist

- [ ] `runs-on: self-hosted` everywhere
- [ ] `uv` installed by `astral-sh/setup-uv`, not assumed on the runner
- [ ] Read only permissions, plus `actions: write` only on the test job, concurrency, timeout
- [ ] Fork pull requests skipped
- [ ] Every step runnable locally with the same command
- [ ] Test job env matches `.env.example` for host, port, task limit, and idle timeout
- [ ] Workflow passes on the runner before merging
