# Continuous integration

GitHub Actions on **self-hosted runners**. Rules and the workflow template are in the `github-actions` skill.

## Pipeline

One workflow `.github/workflows/ci.yml`, triggered on push and pull request to `main` and manually. Lint, format, test, and audit are separate jobs with no `needs`, so they start together. Each job checks out the repo, installs `uv`, and runs `uv sync --locked` before its command.

| Job | Command | Fails when |
|-----|---------|------------|
| `lint` | `uv run ruff check .` | style or error rule violated |
| `format` | `uv run ruff format --check .` | code not formatted |
| `test` | `uv run pytest -q` | any unit, integration or system test fails |
| `audit` | `uv run --with "pip-audit==2.*" pip-audit` | a dependency has a known vulnerability |

Every step after installing `uv` is the same command a developer runs locally, so a red pipeline is reproducible by hand.

## Decisions

1. **Self-hosted only.** Per project requirement, every job uses `runs-on: self-hosted` and no other label. `uv` is installed in the job, so the runner needs nothing extra.
2. **Parallel jobs.** Lint, format, test, and audit do not depend on each other, so each is its own job and they run at the same time. Tests use free ports and temporary directories, so they can share a runner machine with the other jobs.
3. **No matrix.** One Python version, 3.13.7, declared in `.python-version`.
4. **Fork pull requests skipped.** Every job uses the condition
   `github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository`
   prevents untrusted fork code from running on self-hosted runners while still checking
   same-repository pull requests.
5. **No Docker in the pipeline.** Tests run as plain processes.
6. **No deployment or release job.** Out of scope for the task.
7. **No stored checkout token.** `persist-credentials: false` keeps the job token out of `.git/config` on the persistent runner.
8. **Pinned audit tool.** `pip-audit` is pinned to major version 2, so a new major cannot change the audit silently. It audits the installed environment, including dev tools.
