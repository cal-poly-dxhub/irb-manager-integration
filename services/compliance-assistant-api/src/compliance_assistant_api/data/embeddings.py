"""AWS Bedrock embeddings client using Cohere Embed v4."""

import json
import os

import boto3


_bedrock_client = None

EMBEDDING_MODEL_ID = os.environ.get(
    "EMBEDDING_MODEL_ID", "us.cohere.embed-v4:0"
)
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
AWS_PROFILE = os.environ.get("AWS_PROFILE")
EMBEDDING_DIMENSION = 1024


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


def get_embedding(text: str, input_type: str = "search_query") -> list[float]:
    """Get an embedding vector for the given text using Cohere Embed v4.

    Args:
        text: The text to embed.
        input_type: One of 'search_document' or 'search_query'.
                    Use 'search_document' when embedding documents for storage.
                    Use 'search_query' when embedding a query for retrieval.
    """
    client = _get_client()

    body = json.dumps({
        "texts": [text],
        "input_type": input_type,
        "embedding_types": ["float"],
        "output_dimension": EMBEDDING_DIMENSION,
        "truncate": "RIGHT",
    })

    response = client.invoke_model(
        modelId=EMBEDDING_MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())

    # Response may be {"embeddings": [[...]]} or {"embeddings": {"float": [[...]]}}
    embeddings = result["embeddings"]
    if isinstance(embeddings, dict):
        return embeddings["float"][0]
    return embeddings[0]


def get_embeddings_batch(
    texts: list[str],
    input_type: str = "search_document",
) -> list[list[float]]:
    """Get embeddings for a batch of texts (up to 96 per call).

    Args:
        texts: List of texts to embed.
        input_type: One of 'search_document' or 'search_query'.
    """
    client = _get_client()

    body = json.dumps({
        "texts": texts,
        "input_type": input_type,
        "embedding_types": ["float"],
        "output_dimension": EMBEDDING_DIMENSION,
        "truncate": "RIGHT",
    })

    response = client.invoke_model(
        modelId=EMBEDDING_MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())

    embeddings = result["embeddings"]
    if isinstance(embeddings, dict):
        return embeddings["float"]
    return embeddings
