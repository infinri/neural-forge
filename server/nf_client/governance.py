import logging
import os
from typing import Any, Dict, List

import yaml


logger = logging.getLogger(__name__)


def _project_root() -> str:
    # server/nf_client/ -> server/ -> project root
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _memory_dir() -> str:
    return os.path.join(_project_root(), "memory")


def _iter_rule_files() -> List[str]:
    paths: List[str] = []
    base = _memory_dir()
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f.endswith(".rules.yml"):
                paths.append(os.path.join(root, f))
    return paths


def _parse_rules_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
    except FileNotFoundError:
        return {}
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("failed to parse governance rules from %s: %s", path, exc)
        return {}

    if not isinstance(loaded, dict):
        logger.warning("unexpected structure in rules file %s", path)
        return {}

    normalized: Dict[str, Any] = {}
    for key, value in loaded.items():
        key_norm = "tagSet" if key.lower() == "tagset" else key
        if key_norm == "includes":
            normalized[key_norm] = _ensure_string_list(value)
        elif key_norm in {"principles", "threats", "practices", "patterns"}:
            normalized[key_norm] = _ensure_string_list(value)
        elif key_norm == "description":
            normalized[key_norm] = str(value) if value is not None else ""
        elif key_norm == "version":
            normalized[key_norm] = str(value) if value is not None else ""
        else:
            normalized[key_norm] = value

    normalized.setdefault("tagSet", "")
    normalized.setdefault("version", "")
    normalized.setdefault("description", "")
    normalized.setdefault("includes", [])

    return normalized


def fetch_policies(project_id: str, scopes: List[str]):
    # For now, we ignore project_id and scopes; policies are global within repository memory/
    policies: List[Dict[str, Any]] = []
    graph: Dict[str, List[str]] = {}
    for p in _iter_rule_files():
        parsed = _parse_rules_file(p)
        tagset = parsed.get("tagSet", "").strip()
        if not tagset:
            continue
        includes = _ensure_string_list(parsed.get("includes"))
        policy = dict(parsed)
        policy["tagSet"] = tagset
        policy["includes"] = includes
        policy.setdefault("description", "")
        policy.setdefault("version", "")
        policy["source"] = os.path.relpath(p, _project_root())
        policies.append(policy)
        graph[tagset] = includes
    return {"policies": policies, "resolutionGraph": graph}


def _ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _ensure_string_list(value: Any) -> List[str]:
    result: List[str] = []
    for item in _ensure_list(value):
        if isinstance(item, str):
            candidate = item.strip()
            if candidate:
                result.append(candidate)
        elif item is not None:
            result.append(str(item))
    return result
