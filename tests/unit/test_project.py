"""Component tests for project metadata and the README."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_project_targets_python_313() -> None:
    """Verify DLV-1 and DLV-4: the project targets Python 3.13 and declares dependencies."""
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = (ROOT / ".python-version").read_text(encoding="utf-8").strip()

    assert version == "3.13.7"
    assert 'requires-python = ">=3.13"' in project
    assert "fastapi" in project
    assert "uvicorn" in project
    assert "pydantic-settings" in project
    assert "pytest" in project
    assert "ruff" in project


def test_project_sets_dependency_floors() -> None:
    """Verify DLV-4 and H11: runtime dependencies have lower bounds near the locked versions."""
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"fastapi>=0.141"' in project
    assert '"h11>=0.16"' in project
    assert '"pydantic-settings>=2.15"' in project
    assert '"uvicorn>=0.54"' in project


def test_ci_drops_checkout_token_and_pins_the_audit() -> None:
    """Verify DLV-5 and H12: CI keeps no checkout token and pins the audit tool."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "persist-credentials: false" in workflow
    assert 'uv run --with "pip-audit==2.*" pip-audit' in workflow
    assert "runs-on: self-hosted" in workflow
    assert "linux" not in workflow
    assert "contents: read" in workflow
    assert "docker" not in workflow.lower()


def test_readme_explains_setup_and_usage() -> None:
    """Verify DLV-6 and PRD-10: the README explains install, startup, the API and wire format."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    lowered = readme.lower()

    assert "uv sync" in lowered
    assert "processing-server" in lowered
    assert "uv run producer" in lowered
    assert "/api/v1/tasks" in readme
    assert "pytest" in lowered
    assert "assumption" in lowered
    assert "limitation" in lowered
    assert "float64" in lowered
