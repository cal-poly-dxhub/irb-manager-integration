"""DynamoDB session store for persisting form state and conversation history."""

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

logger = logging.getLogger(__name__)

SESSION_TTL_DAYS = 90


class SessionStore:
    """CRUD operations for sessions in DynamoDB."""

    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name or os.environ.get("DYNAMODB_TABLE")
        self._client = None
        self._serializer = TypeSerializer()
        self._deserializer = TypeDeserializer()

    @property
    def enabled(self) -> bool:
        return self._table_name is not None

    def _get_client(self):
        if self._client is None:
            region = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
            profile = os.environ.get("AWS_PROFILE")
            session_kwargs = {}
            if profile:
                session_kwargs["profile_name"] = profile
            session = boto3.Session(**session_kwargs)
            self._client = session.client("dynamodb", region_name=region)
        return self._client

    def create_session(self) -> dict:
        """Create a new session. Returns the session data dict."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        ttl = int((datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)).timestamp())

        item = {
            "PK": {"S": f"SESSION#{session_id}"},
            "SK": {"S": "SESSION"},
            "sessionId": {"S": session_id},
            "createdAt": {"S": now},
            "updatedAt": {"S": now},
            "status": {"S": "active"},
            "formValues": {"M": {}},
            "conversationHistory": {"L": []},
            "attachmentFilenames": {"L": []},
            "ttl": {"N": str(ttl)},
        }

        self._get_client().put_item(
            TableName=self._table_name,
            Item=item,
        )

        logger.info(f"Created session {session_id}")
        return {
            "sessionId": session_id,
            "createdAt": now,
            "updatedAt": now,
            "status": "active",
            "formValues": {},
            "conversationHistory": [],
            "attachmentFilenames": [],
        }

    def get_session(self, session_id: str) -> Optional[dict]:
        """Load a session by ID. Returns None if not found."""
        response = self._get_client().get_item(
            TableName=self._table_name,
            Key={
                "PK": {"S": f"SESSION#{session_id}"},
                "SK": {"S": "SESSION"},
            },
        )

        item = response.get("Item")
        if not item:
            return None

        return self._deserialize_session(item)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID. Returns True if deleted, False if not found."""
        try:
            self._get_client().delete_item(
                TableName=self._table_name,
                Key={
                    "PK": {"S": f"SESSION#{session_id}"},
                    "SK": {"S": "SESSION"},
                },
                ConditionExpression="attribute_exists(PK)",
            )
            logger.info(f"Deleted session {session_id}")
            return True
        except self._get_client().exceptions.ConditionalCheckFailedException:
            logger.warning(f"Session {session_id} not found for deletion")
            return False

    def save_form_values(self, session_id: str, form_values: dict) -> bool:
        """Save form values for a session."""
        now = datetime.now(timezone.utc).isoformat()
        serialized = self._serialize_form_values(form_values)

        try:
            self._get_client().update_item(
                TableName=self._table_name,
                Key={
                    "PK": {"S": f"SESSION#{session_id}"},
                    "SK": {"S": "SESSION"},
                },
                UpdateExpression="SET formValues = :fv, updatedAt = :now",
                ExpressionAttributeValues={
                    ":fv": {"M": serialized},
                    ":now": {"S": now},
                },
                ConditionExpression="attribute_exists(PK)",
            )
            return True
        except self._get_client().exceptions.ConditionalCheckFailedException:
            logger.warning(f"Session {session_id} not found for form save")
            return False

    def save_after_chat(
        self,
        session_id: str,
        form_values: dict,
        conversation_history: list[dict],
        attachment_filenames: list[str],
    ) -> bool:
        """Persist state after a chat turn completes."""
        now = datetime.now(timezone.utc).isoformat()
        serialized_fv = self._serialize_form_values(form_values)
        serialized_history = self._serialize_history(conversation_history)
        serialized_filenames = {"L": [{"S": f} for f in attachment_filenames]}

        try:
            self._get_client().update_item(
                TableName=self._table_name,
                Key={
                    "PK": {"S": f"SESSION#{session_id}"},
                    "SK": {"S": "SESSION"},
                },
                UpdateExpression=(
                    "SET formValues = :fv, conversationHistory = :ch, "
                    "attachmentFilenames = :af, updatedAt = :now"
                ),
                ExpressionAttributeValues={
                    ":fv": {"M": serialized_fv},
                    ":ch": serialized_history,
                    ":af": serialized_filenames,
                    ":now": {"S": now},
                },
                ConditionExpression="attribute_exists(PK)",
            )
            return True
        except self._get_client().exceptions.ConditionalCheckFailedException:
            logger.warning(f"Session {session_id} not found for chat save")
            return False

    def _serialize_form_values(self, form_values: dict) -> dict:
        """Serialize form values to DynamoDB attribute map."""
        result = {}
        for key, value in form_values.items():
            str_key = str(key)
            if isinstance(value, bool):
                result[str_key] = {"BOOL": value}
            elif isinstance(value, str):
                result[str_key] = {"S": value}
            elif isinstance(value, list):
                result[str_key] = {"L": [{"S": v} for v in value]}
            else:
                result[str_key] = {"S": str(value)}
        return result

    def _serialize_history(self, history: list[dict]) -> dict:
        """Serialize conversation history to DynamoDB list."""
        items = []
        for msg in history:
            entry = {
                "M": {
                    "role": {"S": msg.get("role", "")},
                    "content": {"S": msg.get("content", "")},
                }
            }
            if msg.get("timestamp"):
                entry["M"]["timestamp"] = {"S": str(msg["timestamp"])}
            if msg.get("fieldUpdates"):
                entry["M"]["fieldUpdates"] = {
                    "L": [
                        {"M": {
                            "dataId": {"N": str(fu.get("dataId", 0))},
                            "value": {"S": str(fu.get("value", ""))},
                        }}
                        for fu in msg["fieldUpdates"]
                    ]
                }
            if msg.get("attachmentFilenames"):
                entry["M"]["attachmentFilenames"] = {
                    "L": [{"S": f} for f in msg["attachmentFilenames"]]
                }
            items.append(entry)
        return {"L": items}

    def _deserialize_session(self, item: dict) -> dict:
        """Deserialize a DynamoDB item into a plain session dict."""
        session_id = item["sessionId"]["S"]
        created_at = item["createdAt"]["S"]
        updated_at = item["updatedAt"]["S"]
        status = item["status"]["S"]

        # Deserialize form values
        form_values = {}
        for key, val in item.get("formValues", {}).get("M", {}).items():
            if "S" in val:
                form_values[key] = val["S"]
            elif "BOOL" in val:
                form_values[key] = val["BOOL"]
            elif "L" in val:
                form_values[key] = [v["S"] for v in val["L"]]

        # Deserialize conversation history
        conversation_history = []
        for entry in item.get("conversationHistory", {}).get("L", []):
            m = entry.get("M", {})
            msg = {
                "role": m.get("role", {}).get("S", ""),
                "content": m.get("content", {}).get("S", ""),
            }
            if "timestamp" in m:
                msg["timestamp"] = m["timestamp"]["S"]
            if "fieldUpdates" in m:
                msg["fieldUpdates"] = [
                    {
                        "dataId": int(fu["M"]["dataId"]["N"]),
                        "value": fu["M"]["value"]["S"],
                    }
                    for fu in m["fieldUpdates"]["L"]
                ]
            if "attachmentFilenames" in m:
                msg["attachmentFilenames"] = [
                    f["S"] for f in m["attachmentFilenames"]["L"]
                ]
            conversation_history.append(msg)

        # Deserialize attachment filenames
        attachment_filenames = [
            f["S"]
            for f in item.get("attachmentFilenames", {}).get("L", [])
        ]

        return {
            "sessionId": session_id,
            "createdAt": created_at,
            "updatedAt": updated_at,
            "status": status,
            "formValues": form_values,
            "conversationHistory": conversation_history,
            "attachmentFilenames": attachment_filenames,
        }
