# Continuous integration

GitHub Actions on **self-hosted runners**. Rules and the workflow template are in the `github-actions` skill.

## Pipeline

One workflow `.github/workflows/ci.yml`, one job `check`, triggered on push and pull request to `main` and manually.

| Step | Command | Fails when |
|------|---------|------------|
| Checkout | `actions/checkout@v4` with `persist-credentials: false` | |
| Install uv | `astral-sh/setup-uv@v6` | |
| Install | `uv sync --locked` | `uv.lock` is out of date or a dependency is missing |
| Lint | `uv run ruff check .` | style or error rule violated |
| Format | `uv run ruff format --check .` | code not formatted |
| Test | `uv run pytest -q` | any unit, integration or system test fails |
| Audit | `uv run --with "pip-audit==2.*" pip-audit` | a dependency has a known vulnerability |

Every step after installing `uv` is the same command a developer runs locally, so a red pipeline is reproducible by hand.

## Decisions

1. **Self-hosted only.** Per project requirement. `uv` is installed in the job, so the runner needs nothing extra.
2. **One job.** The whole check takes well under a minute; splitting into jobs adds setup time without benefit.
3. **No matrix.** One Python version, 3.13.7, declared in `.python-version`.
4. **Fork pull requests skipped.** The job condition
   `github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository`
   prevents untrusted fork code from running on self-hosted runners while still checking
   same-repository pull requests.
5. **No Docker in the pipeline.** Tests run as plain processes.
6. **No deployment or release job.** Out of scope for the task.
7. **No stored checkout token.** `persist-credentials: false` keeps the job token out of `.git/config` on the persistent runner.
8. **Pinned audit tool.** `pip-audit` is pinned to major version 2, so a new major cannot change the audit silently. It audits the installed environment, including dev tools.
