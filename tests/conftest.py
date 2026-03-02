"""Shared pytest fixtures and helpers for container-based tests."""

import sys
import os
from pathlib import Path
from typing import Any

import pytest

try:
    import docker
except Exception:  # pragma: no cover
    docker = None

sys.path.append(str(Path(__file__).resolve().parents[1].joinpath("src")))
sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["WORKDIR"] = str(Path(__file__).resolve().parents[2])
TEST_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(TEST_DIR, "data")
TEMP_DIR = Path(DATA_DIR, "tmp")
CONFIG_DIR = Path(TEST_DIR, "configs")


def _pick_container_name(funcargs: dict[str, Any]) -> str | None:
    # 1) Prefer explicit container fixtures.
    for key, value in funcargs.items():
        if "container" not in key or value is None:
            continue
        direct_name = getattr(value, "name", None)
        if isinstance(direct_name, str) and direct_name:
            return direct_name
        cfg_name = getattr(value, "container_name", None)
        if isinstance(cfg_name, str) and cfg_name:
            return cfg_name

    # 2) Fallback: manager fixtures (manager.config.container_name).
    for value in funcargs.values():
        if value is None:
            continue
        config = getattr(value, "config", None)
        cfg_name = getattr(config, "container_name", None)
        if isinstance(cfg_name, str) and cfg_name:
            return cfg_name

    # 3) Fallback: config fixtures directly.
    for value in funcargs.values():
        if value is None:
            continue
        cfg_name = getattr(value, "container_name", None)
        if isinstance(cfg_name, str) and cfg_name:
            return cfg_name
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """
    Expose setup/call/teardown reports on each test item.

    Parameters
    ----------
    item : pytest.Item
        Test item being reported.
    call : pytest.CallInfo
        Call phase metadata provided by pytest.

    Yields
    ------
    object
        Pytest hookwrapper outcome object.
    """
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest.fixture(autouse=True)
def _dump_container_logs_on_failure(request: pytest.FixtureRequest):
    yield
    report = getattr(request.node, "rep_call", None) or getattr(request.node, "rep_setup", None)
    if not report or not report.failed:
        return
    if docker is None:
        return

    try:
        client = docker.from_env()
    except Exception:
        return

    name = _pick_container_name(getattr(request.node, "funcargs", {}))
    if not name:
        return

    terminal = request.config.pluginmanager.get_plugin("terminalreporter")
    try:
        container = client.containers.get(name)
        logs = container.logs(tail=300).decode("utf-8", errors="replace")
    except Exception as exc:
        logs = f"<could not fetch logs for {name}: {exc}>"

    if terminal:
        terminal.write_sep("-", f"Failed test {request.node.nodeid} | container logs: {name}")
        terminal.write_line(logs.rstrip() or "<empty>")
