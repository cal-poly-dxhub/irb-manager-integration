#!/usr/bin/env python3
"""Generate embeddings for past submission responses and store them locally.

Reads mapping files from data/compliance-assistant/mappings/,
embeds each response using AWS Bedrock (Cohere Embed v4),
and stores the result as numpy vectors + JSON metadata
in data/compliance-assistant/embeddings/.

Usage:
    python scripts/embed_past_submissions.py

    # With custom paths:
    python scripts/embed_past_submissions.py \
        --mappings-dir data/compliance-assistant/mappings \
        --output-dir data/compliance-assistant/embeddings

    # Dry run (no Bedrock calls, generates random vectors for testing):
    python scripts/embed_past_submissions.py --dry-run

    # With a specific AWS profile:
    python scripts/embed_past_submissions.py --profile bedrock
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np


BATCH_SIZE = 64  # Cohere Embed v4 supports up to 96 per call


def get_embeddings_batch_bedrock(texts, client, model_id, dimension):
    """Get embeddings for a batch of texts from Cohere Embed v4 via Bedrock."""
    body = json.dumps({
        "texts": texts,
        "input_type": "search_document",
        "embedding_types": ["float"],
        "output_dimension": dimension,
        "truncate": "RIGHT",
    })
    response = client.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())

    embeddings = result["embeddings"]
    if isinstance(embeddings, dict):
        return embeddings["float"]
    return embeddings


def get_embedding_dry_run(text, dimension):
    """Generate a deterministic pseudo-random embedding for testing."""
    seed = hash(text) % (2**31)
    rng = np.random.RandomState(seed)
    vec = rng.randn(dimension).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def main():
    parser = argparse.ArgumentParser(
        description="Embed past submission responses for vector search"
    )
    parser.add_argument(
        "--mappings-dir",
        default="data/compliance-assistant/mappings",
        help="Directory containing mapping JSON files",
    )
    parser.add_argument(
        "--output-dir",
        default="data/compliance-assistant/embeddings",
        help="Directory to write vectors.npy and metadata.json",
    )
    parser.add_argument(
        "--model-id",
        default="us.cohere.embed-v4:0",
        help="Bedrock embedding model ID",
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=1024,
        help="Embedding dimension",
    )
    parser.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region for Bedrock",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile name",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use random vectors instead of calling Bedrock (for testing)",
    )
    args = parser.parse_args()

    mappings_dir = Path(args.mappings_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load all mapping files
    mapping_files = sorted(mappings_dir.glob("mapping_*.json"))
    if not mapping_files:
        print(f"No mapping files found in {mappings_dir}")
        sys.exit(1)

    print(f"Found {len(mapping_files)} mapping file(s)")

    # Collect all entries to embed
    entries = []
    for mf in mapping_files:
        with open(mf) as f:
            data = json.load(f)
        protocol = data["protocol"]
        mappings = data["mappings"]
        print(f"  {mf.name}: protocol={protocol}, {len(mappings)} fields")
        for data_id, text in mappings.items():
            entries.append({
                "dataId": int(data_id),
                "protocol": protocol,
                "text": text,
            })

    print(f"\nTotal entries to embed: {len(entries)}")

    # Set up Bedrock client
    client = None
    if not args.dry_run:
        import boto3
        session_kwargs = {}
        if args.profile:
            session_kwargs["profile_name"] = args.profile
        session = boto3.Session(**session_kwargs)
        client = session.client("bedrock-runtime", region_name=args.region)
        print(f"Using Bedrock model: {args.model_id} (dim={args.dimension})")
    else:
        print(f"DRY RUN: using random vectors (dim={args.dimension})")

    # Prepare texts (truncate very long ones)
    texts = []
    for entry in entries:
        text = entry["text"]
        # Cohere Embed v4 supports 128k tokens, but keep it reasonable
        if len(text) > 50000:
            text = text[:50000]
        texts.append(text)

    # Embed all entries
    vectors = []
    if args.dry_run:
        for i, text in enumerate(texts):
            vec = get_embedding_dry_run(text, args.dimension)
            vectors.append(vec)
            print(f"  [{i+1}/{len(entries)}] dataId={entries[i]['dataId']} "
                  f"protocol={entries[i]['protocol']} ({len(entries[i]['text'])} chars)")
    else:
        # Batch embedding
        for batch_start in range(0, len(texts), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(texts))
            batch_texts = texts[batch_start:batch_end]

            print(f"  Embedding batch {batch_start+1}-{batch_end}/{len(texts)}...")
            batch_vectors = get_embeddings_batch_bedrock(
                batch_texts, client, args.model_id, args.dimension
            )
            vectors.extend(batch_vectors)

            for i in range(batch_start, batch_end):
                print(f"    [{i+1}/{len(entries)}] dataId={entries[i]['dataId']} "
                      f"protocol={entries[i]['protocol']} ({len(entries[i]['text'])} chars)")

            # Rate limiting between batches
            if batch_end < len(texts):
                time.sleep(1)

    # Build metadata
    metadata = []
    for i, entry in enumerate(entries):
        metadata.append({
            "dataId": entry["dataId"],
            "protocol": entry["protocol"],
            "text": entry["text"],
            "index": i,
        })

    # Save vectors
    vectors_np = np.array(vectors, dtype=np.float32)
    vectors_path = output_dir / "vectors.npy"
    np.save(str(vectors_path), vectors_np)

    # Save metadata
    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nDone!")
    print(f"  Vectors: {vectors_path} (shape: {vectors_np.shape})")
    print(f"  Metadata: {metadata_path} ({len(metadata)} entries)")

    # Summary stats
    unique_fields = len(set(e["dataId"] for e in metadata))
    unique_protocols = len(set(e["protocol"] for e in metadata))
    print(f"  Unique fields: {unique_fields}")
    print(f"  Unique protocols: {unique_protocols}")


if __name__ == "__main__":
    main()
