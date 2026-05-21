import json
import logging
import os
from pathlib import Path

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from pydantic import ValidationError

from compliance_assistant_api.models import ChatRequest, ChatResponse, ErrorResponse
from compliance_assistant_api.form_state import FormState
from compliance_assistant_api.data.field_prompts import FieldPromptStore
from compliance_assistant_api.data.vector_store import VectorStore
from compliance_assistant_api.data.session_store import SessionStore

USE_MOCK = os.environ.get("USE_MOCK", "").lower() in ("1", "true", "yes")

if USE_MOCK:
    from compliance_assistant_api.mock_agent import generate_mock_response
else:
    from compliance_assistant_api.agent import run_agent_stream

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Load data from S3 when DATA_BUCKET is set (deployed), otherwise use local paths
if os.environ.get("DATA_BUCKET"):
    from compliance_assistant_api.data.s3_loader import download_data_from_s3
    TEMPLATE_PATH, DATA_DIR, EMBEDDINGS_DIR = download_data_from_s3()
else:
    _REPO_ROOT = Path(__file__).resolve().parents[4]
    TEMPLATE_PATH = os.environ.get(
        "TEMPLATE_PATH",
        str(_REPO_ROOT / "apps" / "compliance-assistant" / "public" / "Initial Submission_Revision9.etemplate"),
    )
    DATA_DIR = os.environ.get(
        "DATA_DIR",
        str(_REPO_ROOT / "data" / "compliance-assistant"),
    )
    EMBEDDINGS_DIR = os.environ.get(
        "EMBEDDINGS_DIR",
        str(_REPO_ROOT / "data" / "compliance-assistant" / "embeddings"),
    )

# Initialize data stores (loaded once at startup)
field_prompts = FieldPromptStore(DATA_DIR)
vector_store = VectorStore(EMBEDDINGS_DIR)
session_store = SessionStore()

logger.info(f"Mode: {'MOCK' if USE_MOCK else 'AGENT (Bedrock)'}")
logger.info(f"Template: {TEMPLATE_PATH}")
logger.info(f"Sessions: {'DynamoDB' if session_store.enabled else 'disabled (no DYNAMODB_TABLE)'}")
logger.info(f"Field prompts: {len(field_prompts.get_fields_with_prompts())} fields with prompts")
logger.info(f"Vector store: {vector_store.size} entries, loaded={vector_store.is_loaded}")


@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "sessions": session_store.enabled,
        "fieldPrompts": len(field_prompts.get_fields_with_prompts()),
        "vectorStoreEntries": vector_store.size,
    })


# -------------------------------------------------------
# Session endpoints
# -------------------------------------------------------

@app.route("/sessions", methods=["POST"])
@app.route("/api/sessions", methods=["POST"])
def create_session():
    if not session_store.enabled:
        return jsonify(ErrorResponse(message="Sessions not available").model_dump()), 503

    try:
        session = session_store.create_session()
        return jsonify(session), 201
    except Exception as e:
        logger.error(f"Create session error: {e}", exc_info=True)
        return jsonify(ErrorResponse(message="Failed to create session").model_dump()), 500


@app.route("/sessions/<session_id>", methods=["GET"])
@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    if not session_store.enabled:
        return jsonify(ErrorResponse(message="Sessions not available").model_dump()), 503

    try:
        session = session_store.get_session(session_id)
        if session is None:
            return jsonify(ErrorResponse(message="Session not found").model_dump()), 404
        return jsonify(session)
    except Exception as e:
        logger.error(f"Get session error: {e}", exc_info=True)
        return jsonify(ErrorResponse(message="Failed to load session").model_dump()), 500


@app.route("/sessions/<session_id>", methods=["DELETE"])
@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    if not session_store.enabled:
        return jsonify(ErrorResponse(message="Sessions not available").model_dump()), 503

    try:
        ok = session_store.delete_session(session_id)
        if not ok:
            return jsonify(ErrorResponse(message="Session not found").model_dump()), 404
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Delete session error: {e}", exc_info=True)
        return jsonify(ErrorResponse(message="Failed to delete session").model_dump()), 500


@app.route("/sessions/<session_id>/form", methods=["PATCH"])
@app.route("/api/sessions/<session_id>/form", methods=["PATCH"])
def save_form(session_id):
    if not session_store.enabled:
        return jsonify(ErrorResponse(message="Sessions not available").model_dump()), 503

    try:
        data = request.get_json()
        if not data or "formValues" not in data:
            return jsonify(ErrorResponse(message="formValues required").model_dump()), 400

        ok = session_store.save_form_values(session_id, data["formValues"])
        if not ok:
            return jsonify(ErrorResponse(message="Session not found").model_dump()), 404
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Save form error: {e}", exc_info=True)
        return jsonify(ErrorResponse(message="Failed to save form").model_dump()), 500


# -------------------------------------------------------
# Existing endpoints
# -------------------------------------------------------

@app.route("/parse-pdf", methods=["POST"])
@app.route("/api/parse-pdf", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify(ErrorResponse(message="No file provided").model_dump()), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify(ErrorResponse(message="File must be a PDF").model_dump()), 400

    try:
        from pypdf import PdfReader
        reader = PdfReader(file.stream)
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        text = text.strip()
        if not text:
            return jsonify(ErrorResponse(message="Could not extract text from PDF").model_dump()), 400
        return jsonify({"text": text, "pages": len(reader.pages)})
    except Exception as e:
        logger.error(f"PDF parse error: {e}", exc_info=True)
        return jsonify(ErrorResponse(message=f"Failed to parse PDF: {str(e)}").model_dump()), 500


@app.route("/chat", methods=["POST"])
@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        if not data:
            return (
                jsonify(ErrorResponse(message="Request body is required").model_dump()),
                400,
            )

        chat_request = ChatRequest(**data)

        if USE_MOCK:
            response: ChatResponse = generate_mock_response(chat_request)
            return jsonify(response.model_dump(by_alias=True))

        # Build form state from frontend values
        form_values = {}
        for k, v in chat_request.form_values.items():
            form_values[int(k)] = v

        form_state = FormState(TEMPLATE_PATH, values=form_values)

        # Extract mode from request
        mode = chat_request.mode

        # Collect field updates and final message for session persistence
        collected_field_updates = []
        final_message = ""
        session_id = chat_request.session_id

        def generate():
            nonlocal final_message
            for event in run_agent_stream(
                request=chat_request,
                form_state=form_state,
                field_prompts=field_prompts,
                vector_store=vector_store,
                mode=mode,
            ):
                if event.get("type") == "fieldUpdate":
                    collected_field_updates.append(event["data"])
                elif event.get("type") == "message":
                    final_message = event["data"]["message"]

                yield f"data: {json.dumps(event)}\n\n"

            # Persist session after stream completes
            if session_id and session_store.enabled:
                _persist_after_chat(
                    session_id=session_id,
                    user_message=chat_request.message,
                    assistant_message=final_message,
                    form_values=chat_request.form_values,
                    field_updates=collected_field_updates,
                    conversation_history=[
                        {"role": h.role, "content": h.content}
                        for h in chat_request.conversation_history
                    ],
                    attachment_filenames=[a.filename for a in chat_request.attachments],
                )

        return Response(generate(), mimetype="text/event-stream")

    except ValidationError as e:
        return (
            jsonify(ErrorResponse(message=str(e)).model_dump()),
            400,
        )
    except Exception as e:
        app.logger.error(f"Chat error: {e}", exc_info=True)
        return (
            jsonify(ErrorResponse(message=str(e)).model_dump()),
            500,
        )


def _persist_after_chat(
    session_id: str,
    user_message: str,
    assistant_message: str,
    form_values: dict,
    field_updates: list[dict],
    conversation_history: list[dict],
    attachment_filenames: list[str],
):
    """Save updated state to DynamoDB after a chat turn."""
    try:
        # Build the full history: previous messages + this turn
        updated_history = list(conversation_history)
        updated_history.append({
            "role": "user",
            "content": user_message,
            "attachmentFilenames": attachment_filenames if attachment_filenames else None,
        })
        updated_history.append({
            "role": "assistant",
            "content": assistant_message,
            "fieldUpdates": field_updates if field_updates else None,
        })

        # Apply field updates to form values for persistence
        updated_form_values = dict(form_values)
        for fu in field_updates:
            updated_form_values[str(fu["dataId"])] = fu["value"]

        # Collect all attachment filenames across the session
        all_filenames = set()
        for msg in updated_history:
            if msg.get("attachmentFilenames"):
                all_filenames.update(msg["attachmentFilenames"])

        session_store.save_after_chat(
            session_id=session_id,
            form_values=updated_form_values,
            conversation_history=updated_history,
            attachment_filenames=sorted(all_filenames),
        )
        logger.info(f"Persisted session {session_id} after chat turn")
    except Exception as e:
        logger.error(f"Failed to persist session {session_id}: {e}", exc_info=True)
