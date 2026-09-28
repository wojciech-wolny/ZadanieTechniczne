---
name: github-actions
description: Writes and reviews simple GitHub Actions workflows for this project running on self-hosted runners with uv, ruff and pytest. Use when creating or changing files in .github/workflows, adding a CI check, or when a pipeline fails.
---

# GitHub Actions

Pipelines must be simple: one workflow, one job, a few readable steps. Every step must also work when run by hand on a developer machine.

## Runner

1. Always `runs-on: [self-hosted, linux]`. Never GitHub hosted labels such as `ubuntu-latest`.
2. Runners may be ephemeral, so nothing beyond `git` can be assumed installed.
3. Install `uv` inside the job with `astral-sh/setup-uv`; `uv` then provides Python from `.python-version`. No `actions/setup-python`.
4. Commands are plain `uv` calls that behave the same in bash and PowerShell, so they also run on the Windows developer machine.
5. Jobs may run in parallel: tests use free ports and temporary directories only.

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
  check:
    if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository
    runs-on: [self-hosted, linux]
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --locked
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest -q
      - run: uv run --with pip-audit pip-audit
```

## Checklist

- [ ] `runs-on: [self-hosted, linux]` everywhere
- [ ] `uv` installed by `astral-sh/setup-uv`, not assumed on the runner
- [ ] Read only permissions, concurrency, timeout
- [ ] Fork pull requests skipped
- [ ] Every step runnable locally with the same command
- [ ] Workflow passes on the runner before merging
