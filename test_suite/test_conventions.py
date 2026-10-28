"""Protect the owner's maintainability rules independently of Docker acceptance."""

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings

import py_docker

SOURCE = Path(__file__).resolve().parents[1].joinpath("src", "py_docker")


def test_pydantic_contracts_have_described_fields_in_owning_modules():
    """Require meaningful descriptions and canonical placement for every data field."""
    for info in pkgutil.walk_packages(py_docker.__path__, prefix="py_docker."):
        module = importlib.import_module(info.name)
        for value in vars(module).values():
            if not inspect.isclass(value) or value.__module__ != module.__name__:
                continue
            if not issubclass(value, BaseModel):
                continue
            expected = "settings" if issubclass(value, BaseSettings) else "models"
            assert module.__name__.rsplit(".", 1)[-1] == expected, value
            for name, field in value.model_fields.items():
                assert field.description and len(field.description.split()) >= 4, (
                    value,
                    name,
                )


def test_python_modules_keep_cohesion_settings_and_method_order():
    """Reject mixed modules, dataclasses and ambient configuration outside settings."""
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        functions = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert not (classes and functions), path
        assert path.name not in {"config.py", "constants.py"}, path
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", None)
                names = [alias.name for alias in node.names]
                assert module not in {"dataclasses", "pydantic.dataclasses"}, path
                assert not set(names) & {"dataclasses", "pydantic.dataclasses"}, path
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "os" and node.attr in {"environ", "getenv"}:
                    assert path.name == "settings.py", (path, node.lineno)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                # Arithmetic remains valid; direct Path construction/joining does not.
                expression = ast.unparse(node.left)
                assert (
                    not expression.startswith("Path(") and ".parent" not in expression
                ), (path, node.lineno)
        for cls in classes:
            if path.name == "base.py":
                assert cls.name.startswith("Base"), (path, cls.name)
            if cls.name.startswith("Base"):
                assert path.name == "base.py", (path, cls.name)
            ranks = [
                _method_rank(node)
                for node in cls.body
                if isinstance(node, ast.FunctionDef)
            ]
            assert ranks == sorted(ranks), (path, cls.name)


def test_test_folder_uses_the_requested_prefix():
    """Keep test discovery on test_suite rather than quietly restoring tests/."""
    root = Path(__file__).resolve().parents[1]
    assert Path(__file__).parent.name.startswith("test_")
    assert not Path(root, "tests").exists()


def _method_rank(node: ast.FunctionDef) -> int:
    """Classify dunders, properties, public methods and private helpers in order.

    Parameters
    ----------
    node : ast.FunctionDef
        Class method, including class/static methods and property accessors.

    Returns
    -------
    int
        Stable ordering rank; a nondecreasing sequence matches the preference.
    """
    if node.name.startswith("__") and node.name.endswith("__"):
        return 0
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id in {
            "property",
            "cached_property",
        }:
            return 1
        if isinstance(decorator, ast.Attribute) and decorator.attr in {
            "getter",
            "setter",
            "deleter",
        }:
            return 1
    return 3 if node.name.startswith("_") else 2
