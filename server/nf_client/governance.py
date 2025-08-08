import os
import re
from typing import Any, Dict, List, Tuple

_TAGSET_RE = re.compile(r"^\s*tagSet:\s*(?P<val>.+?)\s*$")
_VERSION_RE = re.compile(r"^\s*version:\s*\"?(?P<val>[^\"\n]+)\"?\s*$")
_INCLUDE_ITEM_RE = re.compile(r"^\s*-\s*(?P<val>[^#\n]+?)\s*(#.*)?$")


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


def _parse_rules_file(path: str) -> Tuple[str, str, List[str]]:
    tagset = ""
    version = ""
    includes: List[str] = []
    in_includes = False
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not tagset:
                m = _TAGSET_RE.match(line)
                if m:
                    tagset = m.group("val").strip()
                    continue
            if not version:
                m = _VERSION_RE.match(line)
                if m:
                    version = m.group("val").strip()
                    continue
            if line.strip().startswith("includes:"):
                in_includes = True
                continue
            if in_includes:
                if line.strip().startswith("#") or not line.strip():
                    continue
                if line.startswith(" ") or line.startswith("\t") or line.strip().startswith("-"):
                    m = _INCLUDE_ITEM_RE.match(line)
                    if m:
                        includes.append(m.group("val").strip())
                else:
                    # left the includes block
                    in_includes = False
    return tagset, version, includes


def fetch_policies(project_id: str, scopes: List[str]):
    # For now, we ignore project_id and scopes; policies are global within repository memory/
    policies: List[Dict[str, Any]] = []
    graph: Dict[str, List[str]] = {}
    for p in _iter_rule_files():
        tagset, version, includes = _parse_rules_file(p)
        if not tagset:
            continue
        policies.append({
            "tagSet": tagset,
            "version": version or "",
            "includes": includes,
            "source": os.path.relpath(p, _project_root()),
        })
        graph[tagset] = includes
    return {"policies": policies, "resolutionGraph": graph}
