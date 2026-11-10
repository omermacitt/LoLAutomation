"""Enforce layer imports without migration exceptions."""

import ast
from importlib.util import resolve_name
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "rune_pilot"
ALLOWED_LAYERS = {
    "shared": {"shared"},
    "domain": {"domain", "shared"},
    "application": {"application", "domain", "shared"},
    "infrastructure": {"infrastructure", "application", "domain", "shared"},
    "presentation": {"presentation", "domain", "shared"},
    "composition": set(),  # Set below: the composition root wires all layers.
}
ALLOWED_LAYERS["composition"] = set(ALLOWED_LAYERS)


def imports(source: str, module: str, *, is_package: bool = False) -> set[str]:
    """Include local imports and resolve relative/package-level import forms."""
    package = module if is_package else module.rpartition(".")[0]
    result = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            target = node.module or ""
            if node.level:
                target = resolve_name("." * node.level + target, package)
            if target in {"rune_pilot", *(f"rune_pilot.{layer}" for layer in ALLOWED_LAYERS)}:
                result.update(f"{target}.{alias.name}" for alias in node.names)
            else:
                result.add(target)
    return result


def forbidden(module: str, target: str) -> bool:
    layer = module.split(".")[0]
    if target.startswith("rune_pilot."):
        target_layer = target.split(".")[1]
        if layer == "infrastructure" and target_layer == "application":
            return (
                not target.startswith("rune_pilot.application.ports.")
                and target != "rune_pilot.application.ports"
            )
        if layer == "domain" and target_layer == "shared":
            return target not in {"rune_pilot.shared.app_meta", "rune_pilot.shared.utils"}
        return target_layer not in ALLOWED_LAYERS[layer]
    external = target.split(".")[0]
    if layer in {"domain", "application", "shared"}:
        return external in {"requests", "httpx", "urllib", "PyQt6", "fastapi", "selenium", "psutil"}
    if layer == "presentation" and module != "presentation.api_client":
        return external in {"requests", "httpx", "urllib"}
    return False


def test_layer_dependencies():
    violations = set()
    for path in PACKAGE.rglob("*.py"):
        parts = path.relative_to(PACKAGE).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        module = ".".join(parts)
        for target in imports(
            path.read_text(encoding="utf-8-sig"),
            f"rune_pilot.{module}",
            is_package=path.name == "__init__.py",
        ):
            if forbidden(module, target):
                violations.add((module, target.removeprefix("rune_pilot.")))
    assert not violations, f"Architecture violations: {sorted(violations)}"


@pytest.mark.parametrize(
    "source",
    [
        "from ..infrastructure.lcu_client import lcu_request",
        "import rune_pilot.infrastructure.lcu_client as lcu",
        "def query():\n    from rune_pilot.infrastructure.lcu_client import lcu_request",
    ],
)
def test_import_scanner_covers_relative_aliased_and_local_imports(source):
    assert imports(source, "rune_pilot.application.query") == {
        "rune_pilot.infrastructure.lcu_client"
    }


def test_package_import_cannot_hide_a_forbidden_layer():
    targets = imports("from rune_pilot import infrastructure", "rune_pilot.presentation.view")
    assert any(forbidden("presentation.view", target) for target in targets)


@pytest.mark.parametrize(
    "module,target",
    [
        ("infrastructure.config_repository", "rune_pilot.application.config_service"),
        ("domain.rules", "rune_pilot.shared.updater"),
        ("presentation.controllers.settings_controller", "requests"),
    ],
)
def test_ports_and_pure_helpers_are_the_only_allowed_lower_layer_dependencies(module, target):
    assert forbidden(module, target)
