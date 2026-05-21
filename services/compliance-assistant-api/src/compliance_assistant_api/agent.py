"""Agentic loop for the compliance assistant using AWS Bedrock Converse API.

Sends messages to Claude with tool definitions, executes tool calls,
and loops until Claude produces a final text response. Collects all
fill_field calls to return as fieldUpdates to the frontend.
"""

import json
import logging
import os
from typing import Optional, Union

import boto3

from compliance_assistant_api.agent_tools import TOOL_DEFINITIONS, ToolExecutor, get_tools_for_mode
from compliance_assistant_api.form_state import FormState, _strip_html
from compliance_assistant_api.data.field_prompts import FieldPromptStore
from compliance_assistant_api.data.vector_store import VectorStore
from compliance_assistant_api.models import AppMode, ChatRequest, ChatResponse, FieldUpdate

logger = logging.getLogger(__name__)

MODEL_ID = os.environ.get("AGENT_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
MAX_TURNS = 250

SYSTEM_PROMPT_COAUTHOR = """You are the TCU IRB Compliance Assistant, an AI agent that helps university researchers fill out the Cayuse Human Ethics IRB submission form.

Your role:
- Help researchers complete their IRB initial submission form by filling in fields based on information they provide
- Work through the form systematically, section by section
- For each free-text field, always check the field guidance first (using get_field_guidance) to understand what's expected, common mistakes to avoid, and see examples from past approved submissions
- Ask the researcher for clarification when you don't have enough information to fill a field properly
- Be thorough but efficient -- fill as many fields as you can from the information provided

How you work:
1. When a researcher sends their research description or source document, analyze it to understand the study
2. Use get_visible_sections to see available form sections
3. Work through sections in order, using get_fields_in_section to see what needs filling
4. For free-text fields, use get_field_guidance to get writing instructions and past examples
5. Use fill_field to set values. For radio/checkbox fields use "true"/"false"
6. After filling fields, summarize what you did and ask about the next section

CRITICAL WORKFLOW RULE -- Section-by-section approval:
- Fill ONE section at a time
- After filling a section, summarize what you filled and STOP
- Wait for the researcher to approve before proceeding to the next section
- Do NOT proceed to the next section until the researcher explicitly approves
- If the researcher requests changes, make them before moving on

Important rules:
- NEVER use emojis in your responses
- ALWAYS use get_field_guidance before filling any textarea or textbox field
- Reference past submission examples when crafting responses for text fields
- Follow the formatting guidelines from the field guidance
- Avoid the common issues listed in the field guidance
- If the researcher's document does not explicitly address a field, DO NOT assume or guess the answer. Instead, stop and ask the researcher. For example, if funding is not mentioned, ask whether the study is funded rather than assuming it is not funded. This applies to all fields, not just text fields.
- When filling text fields, write in a professional academic tone appropriate for IRB submissions
- Do NOT fill fields with placeholder text or generic content -- every field must be filled with real, specific information based on what the researcher has told you"""

SYSTEM_PROMPT_REVIEW = """You are the TCU IRB Compliance Reviewer, an AI agent that reviews completed IRB submission forms for compliance issues.

Your role:
- Read the form as a compliance reviewer -- do NOT fill any fields
- Use flag_issue to annotate specific fields that have compliance problems
- Be constructive: explain what is wrong and suggest how to fix it
- Check for completeness, accuracy, regulatory compliance, and clarity

How you work:
1. Use get_visible_sections and get_fields_in_section to read the current form content
2. For each field that has issues, use flag_issue to annotate it with severity and a message
3. After reviewing, provide a summary of findings

Important rules:
- NEVER use emojis in your responses
- Do NOT use fill_field -- you are a reviewer, not an author
- Use flag_issue for every problem you find
- Severity "major" = blocks submission (missing required info, regulatory non-compliance)
- Severity "minor" = should fix but not blocking (clarity, formatting, best practices)
- Always provide a suggestion for how to fix the issue when possible
- Be specific about what is wrong and cite the relevant regulation or guideline if applicable"""

SYSTEM_PROMPT_ADAPT = """You are the TCU IRB Compliance Assistant in resubmission/adaptation mode. You help researchers adapt a previous IRB submission for a new study.

Your role:
- Pre-fill fields from the previous submission data already loaded in the form
- Identify which fields need to be updated for the new study
- Help the researcher make targeted changes rather than starting from scratch

How you work:
1. Review the current form values (from the previous submission)
2. Ask the researcher what has changed in the new study
3. Identify fields that need updating based on what changed
4. Use fill_field to update only the fields that need changes
5. Summarize changes made and ask for approval

Important rules:
- NEVER use emojis in your responses
- ALWAYS use get_field_guidance before filling any textarea or textbox field
- Focus on what has CHANGED -- do not rewrite fields that are still correct
- Ask the researcher about changes rather than guessing
- When filling text fields, write in a professional academic tone appropriate for IRB submissions"""


def get_system_prompt(mode: AppMode) -> str:
    """Return the system prompt for the given mode."""
    if mode == AppMode.REVIEW:
        return SYSTEM_PROMPT_REVIEW
    elif mode == AppMode.ADAPT:
        return SYSTEM_PROMPT_ADAPT
    return SYSTEM_PROMPT_COAUTHOR


AWS_PROFILE = os.environ.get("AWS_PROFILE")

_bedrock_client = None


def _get_client():
    global _bedrock_client
    if _bedrock_client is None:
        session_kwargs = {}
        if AWS_PROFILE:
            session_kwargs["profile_name"] = AWS_PROFILE
        session = boto3.Session(**session_kwargs)
        _bedrock_client = session.client(
            "bedrock-runtime", region_name=AWS_REGION
        )
    return _bedrock_client


def run_agent(
    request: ChatRequest,
    form_state: FormState,
    field_prompts: FieldPromptStore,
    vector_store: VectorStore,
    mode: AppMode = AppMode.COAUTHOR,
) -> ChatResponse:
    """Run the agentic loop and return a chat response with field updates.

    Args:
        request: The incoming chat request with message, history, and attachments.
        form_state: Current form state with values from the frontend.
        field_prompts: Access to per-field custom prompts.
        vector_store: Access to past submission embeddings for RAG.
        mode: The application mode (coauthor, review, adapt).

    Returns:
        ChatResponse with the assistant's message and any field updates.
    """
    client = _get_client()
    tool_executor = ToolExecutor(form_state, field_prompts, vector_store, mode=mode)

    # Build the conversation messages for Bedrock
    messages = _build_messages(request)

    # Track all fill_field calls
    field_updates: list[FieldUpdate] = []

    system_prompt = get_system_prompt(mode)
    tool_config = {"tools": get_tools_for_mode(mode)}

    for turn in range(MAX_TURNS):
        logger.info(f"Agent turn {turn + 1}/{MAX_TURNS}")

        try:
            response = client.converse(
                modelId=MODEL_ID,
                system=[{"text": system_prompt}],
                messages=messages,
                toolConfig=tool_config,
            )
        except Exception as e:
            logger.error(f"Bedrock converse error: {e}", exc_info=True)
            return ChatResponse(
                message=f"I encountered an error communicating with the AI service. Please try again.",
            )

        stop_reason = response.get("stopReason", "")
        output = response.get("output", {})
        assistant_message = output.get("message", {})

        # Add assistant's response to messages
        messages.append(assistant_message)

        # Check if we're done (no tool use)
        if stop_reason == "end_turn":
            # Extract text from the response
            text = _extract_text(assistant_message)
            return ChatResponse(
                message=text,
                field_updates=field_updates,
            )

        # Handle tool use
        if stop_reason == "tool_use":
            tool_results = []
            for block in assistant_message.get("content", []):
                if "toolUse" not in block:
                    continue

                tool_use = block["toolUse"]
                tool_name = tool_use["name"]
                tool_input = tool_use.get("input", {})
                tool_use_id = tool_use["toolUseId"]

                logger.info(f"Executing tool: {tool_name}({json.dumps(tool_input)[:200]})")

                # Execute the tool
                result = tool_executor.execute(tool_name, tool_input)

                # Track field updates from fill_field calls
                if tool_name == "fill_field" and result.get("success"):
                    data_id = result["dataId"]
                    value = result["valueSet"]
                    field_updates.append(FieldUpdate(dataId=data_id, value=value))

                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": result}],
                    }
                })

            # Add tool results as a user message
            messages.append({
                "role": "user",
                "content": tool_results,
            })
        else:
            # Unexpected stop reason
            text = _extract_text(assistant_message)
            if text:
                return ChatResponse(message=text, field_updates=field_updates)
            return ChatResponse(
                message="I've completed processing your request.",
                field_updates=field_updates,
            )

    # Max turns reached
    text = "I've been working on your request but hit the processing limit. Here's what I've done so far."
    if field_updates:
        text += f" I filled {len(field_updates)} field(s). Please send another message to continue."
    return ChatResponse(message=text, field_updates=field_updates)


def run_agent_stream(
    request: ChatRequest,
    form_state: FormState,
    field_prompts: FieldPromptStore,
    vector_store: VectorStore,
    mode: AppMode = AppMode.COAUTHOR,
):
    """Run the agentic loop, yielding SSE events as fields are filled.

    Yields dicts with:
      {"type": "fieldUpdate", "data": {"dataId": ..., "value": ...}}
      {"type": "flaggedIssue", "data": {"dataId": ..., "severity": ..., "message": ..., "suggestion": ...}}
      {"type": "message", "data": {"message": "..."}}
      {"type": "done"}
      {"type": "error", "data": {"message": "..."}}
    """
    client = _get_client()
    tool_executor = ToolExecutor(form_state, field_prompts, vector_store, mode=mode)
    messages = _build_messages(request)
    system_prompt = get_system_prompt(mode)
    tool_config = {"tools": get_tools_for_mode(mode)}

    for turn in range(MAX_TURNS):
        logger.info(f"Agent turn {turn + 1}/{MAX_TURNS}")

        try:
            response = client.converse(
                modelId=MODEL_ID,
                system=[{"text": system_prompt}],
                messages=messages,
                toolConfig=tool_config,
            )
        except Exception as e:
            logger.error(f"Bedrock converse error: {e}", exc_info=True)
            yield {"type": "error", "data": {"message": "I encountered an error communicating with the AI service. Please try again."}}
            return

        stop_reason = response.get("stopReason", "")
        output = response.get("output", {})
        assistant_message = output.get("message", {})
        messages.append(assistant_message)

        if stop_reason == "end_turn":
            text = _extract_text(assistant_message)
            yield {"type": "message", "data": {"message": text}}
            yield {"type": "done"}
            return

        # Emit any reasoning text the model produced alongside tool calls
        thinking_text = _extract_text(assistant_message)
        if thinking_text:
            yield {"type": "thinking", "data": {"text": thinking_text}}

        if stop_reason == "tool_use":
            tool_results = []
            for block in assistant_message.get("content", []):
                if "toolUse" not in block:
                    continue

                tool_use = block["toolUse"]
                tool_name = tool_use["name"]
                tool_input = tool_use.get("input", {})
                tool_use_id = tool_use["toolUseId"]

                logger.info(f"Executing tool: {tool_name}({json.dumps(tool_input)[:200]})")

                # Enrich tool call event with field label when available
                tool_call_data: dict = {"name": tool_name, "input": tool_input}
                if "data_id" in tool_input:
                    data_id = tool_input["data_id"]
                    el = form_state.get_element(data_id)
                    if el:
                        label = _strip_html(el.get("text", ""))
                        # For radio/checkbox, include the parent question for context
                        if el.get("type") in ("radio", "checkbox"):
                            parent_text = form_state.get_parent_question_text(data_id)
                            if parent_text:
                                label = f"{parent_text} > {label}"
                        tool_call_data["fieldLabel"] = label

                yield {"type": "toolCall", "data": tool_call_data}

                result = tool_executor.execute(tool_name, tool_input)

                yield {
                    "type": "toolResult",
                    "data": {"name": tool_name, "result": result},
                }

                if tool_name == "fill_field" and result.get("success"):
                    yield {
                        "type": "fieldUpdate",
                        "data": {"dataId": result["dataId"], "value": result["valueSet"]},
                    }

                if tool_name == "flag_issue" and result.get("success"):
                    issue_data = {
                        "dataId": result["dataId"],
                        "severity": result["severity"],
                        "message": result["message"],
                    }
                    # Include suggestion if present in tool input
                    if tool_input.get("suggestion"):
                        issue_data["suggestion"] = tool_input["suggestion"]
                    yield {
                        "type": "flaggedIssue",
                        "data": issue_data,
                    }

                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": result}],
                    }
                })

            messages.append({"role": "user", "content": tool_results})
        else:
            text = _extract_text(assistant_message)
            if text:
                yield {"type": "message", "data": {"message": text}}
            yield {"type": "done"}
            return

    yield {"type": "message", "data": {"message": "I've been working on your request but hit the processing limit. Please send another message to continue."}}
    yield {"type": "done"}


def _build_messages(request: ChatRequest) -> list[dict]:
    """Convert the chat request into Bedrock Converse message format."""
    messages = []

    # Add conversation history (skip entries with blank content — Bedrock rejects them)
    for item in request.conversation_history:
        if item.content and item.content.strip():
            messages.append({
                "role": item.role,
                "content": [{"text": item.content}],
            })

    # Build the current user message
    user_content = []

    # Add attachment contents
    if request.attachments:
        for att in request.attachments:
            user_content.append({
                "text": f"[Attached file: {att.filename}]\n{att.content}",
            })

    # Add the message text
    if request.message:
        user_content.append({"text": request.message})

    if user_content:
        messages.append({
            "role": "user",
            "content": user_content,
        })

    return messages


def _extract_text(message: dict) -> str:
    """Extract text content from a Bedrock Converse message."""
    parts = []
    for block in message.get("content", []):
        if "text" in block:
            parts.append(block["text"])
    return "\n".join(parts) if parts else ""
