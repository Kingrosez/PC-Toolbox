"""Exclusion service for PC-Toolbox."""

import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

DEFAULT_PATH = os.path.join(os.path.expanduser("~"), ".pc_toolbox_exclusions.json")


def _normalize(path):
    if not path:
        return None
    try:
        p = os.path.abspath(os.path.expanduser(path))
        p = os.path.normcase(p)
        return p.rstrip("\\/")
    except Exception:
        return None


def _is_root(path):
    norm = _normalize(path)
    if not norm:
        return True
    # drive root or bare
    if len(norm) <= 3 and norm.endswith(":"):
        return True
    if norm in ("/", "\\"):
        return True
    return False


class ExclusionService:
    def __init__(self, storage_path=None, activity_service=None):
        self.storage_path = storage_path or DEFAULT_PATH
        self.activity_service = activity_service
        self._items: List[Dict[str, Any]] = []
        self.load()

    def load(self):
        if not os.path.exists(self.storage_path):
            self._items = []
            return
        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._items = [self._validate_item(x) for x in data if self._validate_item(x)]
            else:
                self._items = []
        except Exception:
            self._items = []

    def _validate_item(self, x):
        if not isinstance(x, dict):
            return None
        if "id" not in x or "category" not in x or "path" not in x:
            return None
        n = _normalize(x["path"])
        if not n:
            return None
        return {
            "id": x["id"],
            "category": x["category"],
            "path": n,
            "display_path": x.get("path", n),
            "description": x.get("description", ""),
            "date_added": x.get("date_added", datetime.now().isoformat()),
            "enabled": bool(x.get("enabled", True)),
        }

    def save(self):
        try:
            tmp = self.storage_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self._items, f, indent=2)
            os.replace(tmp, self.storage_path)
            return True
        except Exception:
            return False

    def list_items(self, category=None, search=""):
        result = list(self._items)
        if category:
            result = [i for i in result if i["category"] == category]
        if search:
            q = search.lower()
            result = [i for i in result if q in i["path"].lower() or q in (i["description"] or "").lower()]
        return result

    def add(self, category, path, description=""):
        norm = _normalize(path)
        if not norm:
            return False, "Invalid path"
        if _is_root(norm):
            return False, "Cannot exclude filesystem root"
        if not os.path.exists(path):
            # allow applications identifiers? For files/folders require existence
            if category in ("folder", "file"):
                return False, "Path does not exist"
        # duplicate check
        for it in self._items:
            if it["category"] == category and it["path"] == norm:
                return False, "Already excluded"
        item = {
            "id": str(uuid.uuid4()),
            "category": category,
            "path": norm,
            "display_path": path,
            "description": description,
            "date_added": datetime.now().isoformat(),
            "enabled": True,
        }
        self._items.append(item)
        self.save()
        if self.activity_service:
            try:
                self.activity_service.add_event("exclusion", "Exclusion added: %s" % norm, "info")
            except Exception:
                pass
        return True, item

    def remove(self, item_id):
        before = len(self._items)
        self._items = [i for i in self._items if i["id"] != item_id]
        if len(self._items) < before:
            self.save()
            if self.activity_service:
                try:
                    self.activity_service.add_event("exclusion", "Exclusion removed", "info")
                except Exception:
                    pass
            return True
        return False

    def update_description(self, item_id, description):
        for it in self._items:
            if it["id"] == item_id:
                it["description"] = description
                self.save()
                return True
        return False

    def is_excluded(self, path, category=None):
        norm = _normalize(path)
        if not norm:
            return False
        for it in self._items:
            if not it.get("enabled", True):
                continue
            if category and it["category"] != category:
                continue
            excl = it["path"]
            if norm == excl:
                return True
            # folder boundary: norm must be under excl
            if norm.startswith(excl + os.sep) or norm.startswith(excl + "/"):
                return True
        return False

    def set_enabled(self, item_id, enabled):
        for it in self._items:
            if it["id"] == item_id:
                it["enabled"] = bool(enabled)
                self.save()
                return True
        return False
