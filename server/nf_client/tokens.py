import logging
import os
from typing import Any, Dict, List

import yaml


logger = logging.getLogger(__name__)


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _tags_dir() -> str:
    return os.path.join(_project_root(), "memory", "tags")


def _list_kinds() -> List[str]:
    base = _tags_dir()
    if not os.path.isdir(base):
        return []
    return sorted([d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))])


def fetch_tokens(project_id: str, kinds: List[str]):
    base = _tags_dir()
    available = set(_list_kinds())
    selected = available if not kinds else (available.intersection(set(kinds)))

    tokens: List[Dict[str, Any]] = []
    for kind in sorted(selected):
        kdir = os.path.join(base, kind)
        if not os.path.isdir(kdir):
            continue
        for fn in sorted(os.listdir(kdir)):
            path = os.path.join(kdir, fn)
            if not os.path.isfile(path):
                continue
            if not fn.lower().endswith((".yml", ".yaml")):
                continue
            # Token identity and metadata derived from path
            token: Dict[str, Any] = {
                "kind": kind,
                "name": os.path.splitext(fn)[0],
                "source": os.path.relpath(path, _project_root()),
            }

            data: Dict[str, Any] = {}
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    loaded = yaml.safe_load(fh)
                    if isinstance(loaded, dict):
                        data = loaded
            except Exception as exc:  # pragma: no cover - logged for visibility
                logger.warning("failed to parse token metadata from %s: %s", path, exc)
                data = {}

            if data:
                token.update(_normalize_token_payload(data))

            token.setdefault("tag", token["name"])

            tokens.append(token)
    return {"tokens": tokens}


def _normalize_token_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize token metadata loaded from YAML files."""

    normalized: Dict[str, Any] = {}
    for key, value in raw.items():
        if key in {"appliesTo", "patterns", "implementation"}:
            normalized[key] = _ensure_list(value)
        elif key in {"bestPractices", "rules"}:
            normalized[key] = _ensure_list(value)
        elif key in {"linkedTags", "usage_metadata", "associative_strength", "pattern_combinations"}:
            normalized[key] = _ensure_dict(value)
        elif key == "description" and value is not None:
            normalized[key] = str(value)
        else:
            normalized[key] = value

    normalized.setdefault("description", "")

    best_practices = _ensure_list(normalized.get("bestPractices"))
    rules = _ensure_list(normalized.get("rules"))
    if not rules and best_practices:
        rules = list(best_practices)

    normalized["bestPractices"] = best_practices
    normalized["rules"] = rules

    for field in ("appliesTo", "patterns", "implementation"):
        normalized[field] = _ensure_list(normalized.get(field))

    for field in ("linkedTags", "usage_metadata", "associative_strength", "pattern_combinations"):
        normalized[field] = _ensure_dict(normalized.get(field))

    normalized.setdefault("usage_metadata", {})
    normalized.setdefault("linkedTags", {})

    if "tag" not in normalized and "name" in normalized:
        normalized["tag"] = normalized["name"]

    return normalized


def _ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _ensure_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}
