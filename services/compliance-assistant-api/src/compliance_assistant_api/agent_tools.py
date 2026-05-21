"""Agent tool definitions and execution for the compliance assistant.

Defines the tools available to the Claude agent and implements
their execution logic. Each tool maps to a function that operates
on the FormState, FieldPromptStore, and VectorStore.
"""

import json
from typing import Any, Optional

from compliance_assistant_api.form_state import FormState, _strip_html
from compliance_assistant_api.data.field_prompts import FieldPromptStore
from compliance_assistant_api.data.vector_store import VectorStore
from compliance_assistant_api.data.embeddings import get_embedding
from compliance_assistant_api.models import AppMode


# -- Tool Definitions (Bedrock Converse format) --

TOOL_DEFINITIONS = [
    {
        "toolSpec": {
            "name": "get_visible_sections",
            "description": (
                "List all form sections that are currently visible. "
                "Returns section names and indices so you know which parts of "
                "the form are available to fill. Sections become visible based "
                "on answers to earlier questions."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_fields_in_section",
            "description": (
                "List all visible fillable fields in a specific form section. "
                "Returns each field's dataId, label, type, whether it's required, "
                "and its current value (if already filled). Use this to see "
                "what fields need to be completed in a section."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "section_name": {
                            "type": "string",
                            "description": (
                                "The section name/title to look up (case-insensitive "
                                "partial match). For example: 'Introduction', "
                                "'Study Information', 'Recruitment'."
                            ),
                        },
                    },
                    "required": ["section_name"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_field_guidance",
            "description": (
                "Get detailed guidance for filling out a specific free-text field. "
                "Returns the field's custom prompt (writing instructions), common "
                "issues to avoid, formatting requirements, and examples from past "
                "submissions for that same field. Use this before filling any "
                "free-text field to ensure the response is high quality."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "data_id": {
                            "type": "integer",
                            "description": "The dataId of the field to get guidance for.",
                        },
                    },
                    "required": ["data_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "fill_field",
            "description": (
                "Set the value of a form field. For text fields (textbox/textarea), "
                "provide a string value. For radio buttons, provide the string 'true' "
                "to select or 'false' to deselect. For checkboxes, provide 'true' "
                "to check or 'false' to uncheck. Always get field guidance first "
                "for free-text fields before filling them."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "data_id": {
                            "type": "integer",
                            "description": "The dataId of the field to fill.",
                        },
                        "value": {
                            "type": "string",
                            "description": (
                                "The value to set. For text fields, the text content. "
                                "For radio/checkbox, 'true' or 'false'."
                            ),
                        },
                    },
                    "required": ["data_id", "value"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "search_past_submissions",
            "description": (
                "Search past IRB submissions for similar content. Useful for "
                "finding examples of how other researchers have answered similar "
                "questions. Can search globally or for a specific field. Returns "
                "the text from past submissions along with similarity scores."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query text to find similar past responses.",
                        },
                        "data_id": {
                            "type": "integer",
                            "description": (
                                "Optional: restrict search to a specific field's "
                                "past responses. If omitted, searches all fields."
                            ),
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results to return (default 3).",
                        },
                    },
                    "required": ["query"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_form_progress",
            "description": (
                "Get an overview of the current form completion status. Shows "
                "which fields have been filled and their values. Use this to "
                "understand what's already been done before starting or resuming work."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }
            },
        }
    },
]


FLAG_ISSUE_TOOL = {
    "toolSpec": {
        "name": "flag_issue",
        "description": (
            "Flag a compliance issue on a specific form field. Use this in "
            "review mode to annotate problems with the current submission. "
            "Provide the data_id of the field, severity (major or minor), "
            "a description of the issue, and optionally a suggestion for fixing it."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "data_id": {
                        "type": "integer",
                        "description": "The dataId of the field with the issue.",
                    },
                    "severity": {
                        "type": "string",
                        "description": "Severity level: 'major' or 'minor'.",
                    },
                    "message": {
                        "type": "string",
                        "description": "Description of the compliance issue.",
                    },
                    "suggestion": {
                        "type": "string",
                        "description": "Optional suggestion for how to fix the issue.",
                    },
                },
                "required": ["data_id", "severity", "message"],
            }
        },
    }
}


def get_tools_for_mode(mode: AppMode) -> list[dict]:
    """Return the appropriate tool set based on the app mode."""
    if mode == AppMode.REVIEW:
        # Review mode: all tools except fill_field, plus flag_issue
        tools = [t for t in TOOL_DEFINITIONS if t["toolSpec"]["name"] != "fill_field"]
        tools.append(FLAG_ISSUE_TOOL)
        return tools
    return TOOL_DEFINITIONS


# -- Tool Execution --

class ToolExecutor:
    """Executes agent tool calls against the form state and data stores."""

    def __init__(
        self,
        form_state: FormState,
        field_prompts: FieldPromptStore,
        vector_store: VectorStore,
        mode: AppMode = AppMode.COAUTHOR,
    ):
        self.form_state = form_state
        self.field_prompts = field_prompts
        self.vector_store = vector_store
        self.mode = mode
        self.flagged_issues: list[dict] = []

    def execute(self, tool_name: str, tool_input: dict) -> dict:
        """Execute a tool call and return the result as a dict."""
        handlers = {
            "get_visible_sections": self._get_visible_sections,
            "get_fields_in_section": self._get_fields_in_section,
            "get_field_guidance": self._get_field_guidance,
            "fill_field": self._fill_field,
            "search_past_submissions": self._search_past_submissions,
            "get_form_progress": self._get_form_progress,
            "flag_issue": self._flag_issue,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return handler(tool_input)
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}

    def _get_visible_sections(self, _input: dict) -> dict:
        visible = self.form_state.get_visible_sections()
        sections = []
        for i, s in enumerate(visible):
            field_count = len(self.form_state.get_visible_fields_in_section(s))
            sections.append({
                "index": i,
                "name": _strip_html(s.get("text", "")),
                "dataId": s["dataId"],
                "fieldCount": field_count,
            })
        return {"sections": sections, "totalVisible": len(sections)}

    def _get_fields_in_section(self, input_data: dict) -> dict:
        section_name = input_data.get("section_name", "")
        section = self.form_state.get_section_by_name(section_name)
        if not section:
            return {"error": f"Section not found: '{section_name}'"}

        fields = self.form_state.get_visible_fields_in_section(section)
        result = []
        for f in fields:
            data_id = f["dataId"]
            current_val = self.form_state.get_value(data_id)
            text = _strip_html(f.get("text", ""))
            # For radio/checkbox, include the parent question for context
            if f["type"] in ("radio", "checkbox"):
                parent_text = self.form_state.get_parent_question_text(data_id)
                if parent_text:
                    text = f"{parent_text} > {text}"
            result.append({
                "dataId": data_id,
                "text": text,
                "type": f["type"],
                "required": self.form_state.is_required(f),
                "currentValue": current_val,
                "hasPrompt": self.field_prompts.get_prompt(data_id) is not None,
            })
        return {
            "section": _strip_html(section.get("text", "")),
            "fields": result,
            "totalFields": len(result),
        }

    def _get_field_guidance(self, input_data: dict) -> dict:
        data_id = input_data.get("data_id")
        if data_id is None:
            return {"error": "data_id is required"}

        result = {}

        # Field metadata
        field_info = self.field_prompts.get_field_info(data_id)
        if field_info:
            result["fieldInfo"] = {
                "label": field_info.get("label", ""),
                "type": field_info.get("type", ""),
                "section": field_info.get("section", ""),
                "required": field_info.get("required", False),
            }

        # Custom prompt
        prompt_data = self.field_prompts.get_prompt(data_id)
        if prompt_data:
            result["prompt"] = prompt_data.get("prompt", "")
            result["commonIssues"] = prompt_data.get("commonIssues", [])
            result["formatting"] = prompt_data.get("formatting", "")

        if not result:
            # Fall back to element info from the template
            el = self.form_state.get_element(data_id)
            if el:
                result["fieldInfo"] = {
                    "label": _strip_html(el.get("text", "")),
                    "type": el["type"],
                }
            else:
                return {"error": f"No guidance found for field {data_id}"}

        return result

    def _fill_field(self, input_data: dict) -> dict:
        data_id = input_data.get("data_id")
        raw_value = input_data.get("value", "")

        if data_id is None:
            return {"error": "data_id is required"}

        el = self.form_state.get_element(data_id)
        if not el:
            return {"error": f"Field {data_id} not found in template"}

        if not self.form_state.is_visible(el):
            return {"error": f"Field {data_id} is not currently visible. Check dependencies."}

        # Convert value based on field type
        field_type = el["type"]
        if field_type in ("radio", "checkbox"):
            value = raw_value.lower() in ("true", "yes", "1")
        else:
            value = raw_value

        self.form_state.set_value(data_id, value)

        return {
            "success": True,
            "dataId": data_id,
            "field": _strip_html(el.get("text", "")),
            "type": field_type,
            "valueSet": value,
        }

    def _search_past_submissions(self, input_data: dict) -> dict:
        query = input_data.get("query", "")
        data_id = input_data.get("data_id")
        top_k = input_data.get("top_k", 3)

        if not query:
            return {"error": "query is required"}

        if not self.vector_store.is_loaded:
            return {"error": "Vector store not loaded. No past submissions available."}

        try:
            query_vector = get_embedding(query)
        except Exception as e:
            return {"error": f"Failed to generate query embedding: {str(e)}"}

        results = self.vector_store.search(
            query_vector=query_vector,
            top_k=top_k,
            data_id=data_id,
        )

        return {
            "results": [
                {
                    "protocol": r["protocol"],
                    "dataId": r["dataId"],
                    "text": r["text"][:500],
                    "score": round(r["score"], 4),
                }
                for r in results
            ],
            "totalResults": len(results),
        }

    def _get_form_progress(self, _input: dict) -> dict:
        filled = self.form_state.get_filled_fields_summary()
        visible_sections = self.form_state.get_visible_sections()

        section_progress = []
        for s in visible_sections:
            fields = self.form_state.get_visible_fields_in_section(s)
            filled_count = sum(
                1 for f in fields
                if self.form_state.get_value(f["dataId"]) is not None
            )
            section_progress.append({
                "section": _strip_html(s.get("text", "")),
                "totalFields": len(fields),
                "filledFields": filled_count,
            })

        return {
            "totalFieldsFilled": len(filled),
            "sectionProgress": section_progress,
            "filledFields": [
                {
                    "dataId": f["dataId"],
                    "text": f["text"][:80],
                    "type": f["type"],
                    "value": str(f["value"])[:100],
                }
                for f in filled
            ],
        }

    def _flag_issue(self, input_data: dict) -> dict:
        data_id = input_data.get("data_id")
        severity = input_data.get("severity", "minor")
        message = input_data.get("message", "")
        suggestion = input_data.get("suggestion")

        if data_id is None:
            return {"error": "data_id is required"}
        if not message:
            return {"error": "message is required"}

        issue = {
            "dataId": data_id,
            "severity": severity,
            "message": message,
        }
        if suggestion:
            issue["suggestion"] = suggestion

        self.flagged_issues.append(issue)

        return {
            "success": True,
            "dataId": data_id,
            "severity": severity,
            "message": message,
        }
