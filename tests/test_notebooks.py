from pathlib import Path

import docker
import nbformat
import pytest
from nbclient import NotebookClient
from .utils import nuke_dir


NOTEBOOK_ROOT = Path(__file__).resolve().parents[1] / "usage"
REPO_ROOT = NOTEBOOK_ROOT.parent
NOTEBOOKS = sorted(
    p for p in NOTEBOOK_ROOT.glob("*.ipynb")
    if ".ipynb_checkpoints" not in str(p)
)


def _cleanup_demo_and_test_containers():
    client = docker.from_env()
    for container in client.containers.list(all=True):
        if container.name.startswith("demo-") or container.name.startswith("test-"):
            try:
                container.stop(timeout=5)
            except docker.errors.APIError:
                pass
            try:
                container.remove(force=True)
            except docker.errors.APIError:
                pass
    nuke_dir(NOTEBOOK_ROOT / "tmp")


def _should_skip_cell(source: str) -> bool:
    """
    Should skip cell.

    Parameters
    ----------
    source : Any
        Fixture or test parameter.
    """
    normalized = source.strip().lower()
    if "this will fail because the container exists" in normalized:
        return True
    if normalized.startswith("%sql\n") or normalized == "%sql":
        return True
    if "%%sqlcmd" in normalized or normalized.startswith("%sqlcmd"):
        return True
    if "from demo_users" in normalized or "from demo_posts" in normalized:
        return True
    if "shutil.rmtree(temp_dir)" in normalized:
        return True
    return False


@pytest.mark.parametrize("notebook_path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_executes_without_errors(notebook_path: Path):
    """
    Test notebook executes without errors.

    Parameters
    ----------
    notebook_path : Any
        Fixture or test parameter.
    """
    _cleanup_demo_and_test_containers()

    with notebook_path.open("r", encoding="utf-8") as f:
        notebook = nbformat.read(f, as_version=4)

    notebook.cells = [
        c for c in notebook.cells
        if c.get("cell_type") != "code" or not _should_skip_cell(str(c.get("source", "")))
    ]

    # Ensure notebooks can import local package modules when executed from usage/.
    notebook.cells.insert(
        0,
        nbformat.v4.new_code_cell(
            "import os, sys\n"
            f"sys.path.insert(0, r'{REPO_ROOT}')\n"
            f"os.environ['WORKDIR'] = r'{REPO_ROOT}'\n"
        ),
    )

    client = NotebookClient(
        notebook,
        timeout=600,
        kernel_name="python3",
        resources={"metadata": {"path": str(notebook_path.parent)}},
        allow_errors=False,
    )
    try:
        client.execute()
    finally:
        _cleanup_demo_and_test_containers()
