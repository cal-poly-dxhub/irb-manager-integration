"""Loads and serves per-field custom prompts and field metadata."""

import json
from pathlib import Path
from typing import Optional


class FieldPromptStore:
    """Provides access to pre-generated field prompts and field reference data."""

    def __init__(self, data_dir: str):
        self._data_dir = Path(data_dir)
        self._prompts: dict = {}
        self._reference: dict = {}
        self._load()

    def _load(self):
        prompts_path = self._data_dir / "field_prompts.json"
        if prompts_path.exists():
            with open(prompts_path) as f:
                self._prompts = json.load(f)

        ref_path = self._data_dir / "free_text_fields_reference.json"
        if ref_path.exists():
            with open(ref_path) as f:
                ref_list = json.load(f)
                self._reference = {str(item["dataId"]): item for item in ref_list}

    def get_prompt(self, data_id: int) -> Optional[dict]:
        """Get the custom prompt for a free-text field.

        Returns dict with keys: name, prompt, commonIssues, formatting.
        Returns None if no prompt exists for this field.
        """
        return self._prompts.get(str(data_id))

    def get_field_info(self, data_id: int) -> Optional[dict]:
        """Get field metadata from the reference file.

        Returns dict with keys: dataId, name, type, label, section, etc.
        Returns None if field not found.
        """
        return self._reference.get(str(data_id))

    def get_all_free_text_field_ids(self) -> list[int]:
        """Return all free-text field dataIds."""
        return [int(item["dataId"]) for item in self._reference.values()]

    def get_fields_with_prompts(self) -> list[int]:
        """Return dataIds that have custom prompts."""
        return [int(k) for k in self._prompts.keys()]

    def build_agent_prompt(self, data_id: int) -> Optional[str]:
        """Build a complete prompt string for the agent to use when filling a field.

        Combines field metadata with the custom prompt, common issues, and formatting.
        """
        prompt_data = self.get_prompt(data_id)
        field_info = self.get_field_info(data_id)

        if not prompt_data and not field_info:
            return None

        parts = []

        if field_info:
            parts.append(f"Field: {field_info.get('label', 'Unknown')}")
            parts.append(f"Section: {field_info.get('section', 'Unknown')}")
            parts.append(f"Type: {field_info.get('type', 'Unknown')}")
            if field_info.get("required"):
                parts.append("This field is REQUIRED.")

        if prompt_data:
            parts.append(f"\nGuidelines: {prompt_data.get('prompt', '')}")

            common_issues = prompt_data.get("commonIssues", [])
            if common_issues:
                parts.append("\nCommon issues to avoid:")
                for issue in common_issues:
                    parts.append(f"  - {issue}")

            formatting = prompt_data.get("formatting")
            if formatting:
                parts.append(f"\nFormatting: {formatting}")

        return "\n".join(parts)
