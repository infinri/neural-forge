import os
from typing import Any, Dict, List


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
            # Token identity and metadata derived from path
            tokens.append({
                "kind": kind,
                "name": os.path.splitext(fn)[0],
                "source": os.path.relpath(path, _project_root()),
            })
    return {"tokens": tokens}
