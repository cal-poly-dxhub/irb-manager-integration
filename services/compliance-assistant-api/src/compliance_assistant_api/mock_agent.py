"""Mock agent responses for Piece 1 testing.

This module returns canned responses to demonstrate the chat-to-form pipeline.
It gets replaced by the real agent harness in Piece 3.
"""

from compliance_assistant_api.models import ChatRequest, ChatResponse, FieldUpdate


def generate_mock_response(request: ChatRequest) -> ChatResponse:
    message_lower = request.message.lower().strip()

    # If user attached files, acknowledge them
    if request.attachments:
        filenames = ", ".join(a.filename for a in request.attachments)
        preview = request.attachments[0].content[:200]
        return ChatResponse(
            message=(
                f"I've received your source document(s): {filenames}. "
                f"Let me review the content and start filling out the form.\n\n"
                f"Here's a preview of what I see:\n\"{preview}...\"\n\n"
                f"I'll start with the Introduction section. To proceed, I need to confirm "
                f"that you've reviewed the submission guidelines. I'll check that off for you."
            ),
            field_updates=[
                # Check "Yes" on "I have reviewed the information and am ready to begin"
                FieldUpdate(dataId=3862360, value=True),
            ],
        )

    # Greeting
    if any(word in message_lower for word in ["hello", "hi", "hey", "help"]):
        return ChatResponse(
            message=(
                "Hello! I'm the Compliance Assistant. I can help you fill out the "
                "TCU IRB submission form.\n\n"
                "Here's how to get started:\n"
                "1. Upload your research description or source documents as text files\n"
                "2. Tell me about your study and I'll fill out the relevant form fields\n"
                "3. You can also ask me about specific sections or fields\n\n"
                "What would you like to do?"
            ),
        )

    # Study funding related
    if any(word in message_lower for word in ["fund", "funding", "grant", "sponsor"]):
        return ChatResponse(
            message=(
                "I'll help with the funding section. Based on what you've told me, "
                "I'll mark the study as funded and we can fill in the details."
            ),
            field_updates=[
                # Set "Is your study funded?" to "Yes"
                FieldUpdate(dataId=3862364, value=True),
            ],
        )

    # Not funded
    if "not funded" in message_lower or "no funding" in message_lower:
        return ChatResponse(
            message="Got it, I'll mark the study as not funded.",
            field_updates=[
                FieldUpdate(dataId=3862365, value=True),
            ],
        )

    # Ready / begin
    if any(word in message_lower for word in ["ready", "begin", "start", "confirm"]):
        return ChatResponse(
            message=(
                "Great! I'll confirm that you've reviewed the submission guidelines "
                "and we can move on to the next section."
            ),
            field_updates=[
                FieldUpdate(dataId=3862360, value=True),
            ],
        )

    # Default: echo back with a helpful message
    return ChatResponse(
        message=(
            f"I understand. You mentioned: \"{request.message[:100]}{'...' if len(request.message) > 100 else ''}\"\n\n"
            f"I'll use this information to help fill out the relevant form fields. "
            f"Could you tell me which section of the form you'd like me to work on? "
            f"Or you can upload your full research description and I'll work through "
            f"the form from the beginning."
        ),
    )
