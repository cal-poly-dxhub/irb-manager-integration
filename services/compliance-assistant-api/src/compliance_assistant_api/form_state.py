"""Backend form state manager.

Mirrors the frontend's FormContext logic so the agent can reason about
which fields are visible, which are required, and what's already filled.
Loads the etemplate JSON and evaluates visibility/dependency rules.
"""

import json
from pathlib import Path
from typing import Optional, Union


FormValues = dict[int, Union[str, bool, list]]


class FormState:
    """Manages form state and evaluates field visibility on the backend."""

    def __init__(self, template_path: str, values: Optional[FormValues] = None):
        self._template_path = Path(template_path)
        self._sections: list[dict] = []
        self._all_elements: dict[int, dict] = {}
        self._parent_map: dict[int, int] = {}  # child dataId -> parent dataId
        self._values: FormValues = values or {}
        self._load_template()

    def _load_template(self):
        with open(self._template_path) as f:
            data = json.load(f)
        self._sections = data["templateJson"]["children"]
        self._index_elements(self._sections, parent_id=None)

    def _index_elements(self, elements: list[dict], parent_id: Optional[int] = None):
        """Recursively index all elements by dataId for fast lookup."""
        for el in elements:
            data_id = el["dataId"]
            self._all_elements[data_id] = el
            if parent_id is not None:
                self._parent_map[data_id] = parent_id
            if el.get("children"):
                self._index_elements(el["children"], parent_id=data_id)

    @property
    def sections(self) -> list[dict]:
        return self._sections

    @property
    def values(self) -> FormValues:
        return self._values

    def update_values(self, updates: FormValues):
        self._values.update(updates)

    def set_value(self, data_id: int, value):
        self._values[data_id] = value

    def get_value(self, data_id: int):
        return self._values.get(data_id)

    def get_element(self, data_id: int) -> Optional[dict]:
        return self._all_elements.get(data_id)

    def get_parent_question_text(self, data_id: int) -> Optional[str]:
        """Walk up the tree to find the nearest question ancestor and return its text."""
        current = data_id
        for _ in range(10):  # guard against infinite loop
            parent_id = self._parent_map.get(current)
            if parent_id is None:
                return None
            parent = self._all_elements.get(parent_id)
            if parent and parent.get("type") == "question":
                return _strip_html(parent.get("text", ""))
            current = parent_id
        return None

    def _get_selected_ids(self) -> set[int]:
        """Return set of dataIds that have a truthy value."""
        selected = set()
        for data_id, value in self._values.items():
            if value is True:
                selected.add(data_id)
            elif isinstance(value, str) and len(value) > 0:
                selected.add(data_id)
            elif isinstance(value, list) and len(value) > 0:
                selected.add(data_id)
        return selected

    def is_visible(self, element: dict) -> bool:
        """Check if an element is visible based on its display dependencies."""
        deps = element.get("dependencies", [])
        if not deps:
            return True

        display_deps = [d for d in deps if d["type"] == "displayed"]
        if not display_deps:
            return True

        selected = self._get_selected_ids()
        return any(d["targetId"] in selected for d in display_deps)

    def is_required(self, element: dict) -> bool:
        """Check if an element is required (statically or conditionally)."""
        if element.get("required"):
            return True

        deps = element.get("dependencies", [])
        if not deps:
            return False

        required_deps = [d for d in deps if d["type"] == "required"]
        if not required_deps:
            return False

        selected = self._get_selected_ids()
        return any(d["targetId"] in selected for d in required_deps)

    def get_visible_sections(self) -> list[dict]:
        """Return top-level sections that are currently visible."""
        return [s for s in self._sections if self.is_visible(s)]

    def get_section_by_index(self, index: int) -> Optional[dict]:
        """Get a section by its index in the visible sections list."""
        visible = self.get_visible_sections()
        if 0 <= index < len(visible):
            return visible[index]
        return None

    def get_section_by_name(self, name: str) -> Optional[dict]:
        """Find a section by its text/title (case-insensitive partial match)."""
        name_lower = name.lower()
        for s in self._sections:
            if name_lower in _strip_html(s.get("text", "")).lower():
                return s
        return None

    def get_visible_fields_in_section(self, section: dict) -> list[dict]:
        """Get all visible, fillable fields within a section (recursively).

        Returns elements of type: textbox, textarea, radio, checkbox, datepicker.
        Excludes labels, questions (containers), and non-visible elements.
        """
        fields = []
        self._collect_visible_fields(section.get("children", []), fields)
        return fields

    def _collect_visible_fields(self, elements: list[dict], result: list[dict]):
        """Recursively collect visible fillable fields."""
        fillable_types = {"textbox", "textarea", "radio", "checkbox", "datepicker"}
        for el in elements:
            if not self.is_visible(el):
                continue
            if el["type"] in fillable_types:
                result.append(el)
            if el.get("children"):
                self._collect_visible_fields(el["children"], result)

    def get_field_summary(self, data_id: int) -> Optional[dict]:
        """Get a summary of a field: its text, type, current value, visibility."""
        el = self.get_element(data_id)
        if not el:
            return None
        return {
            "dataId": data_id,
            "name": el.get("name", ""),
            "text": _strip_html(el.get("text", "")),
            "type": el["type"],
            "visible": self.is_visible(el),
            "required": self.is_required(el),
            "currentValue": self._values.get(data_id),
        }

    def get_filled_fields_summary(self) -> list[dict]:
        """Return a summary of all fields that have values set."""
        result = []
        for data_id, value in self._values.items():
            el = self.get_element(data_id)
            if el:
                result.append({
                    "dataId": data_id,
                    "text": _strip_html(el.get("text", "")),
                    "type": el["type"],
                    "value": value,
                })
        return result


def _strip_html(html: str) -> str:
    """Simple HTML tag stripper."""
    import re
    clean = re.sub(r"<[^>]+>", "", html)
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&")
    return clean.strip()
