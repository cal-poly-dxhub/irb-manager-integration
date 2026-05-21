"""Load data assets from S3 to local temp directory.

When DATA_BUCKET is set, downloads etemplate, field_prompts.json,
free_text_fields_reference.json, and embeddings from S3 to a temp dir.
The rest of the app then reads from the local temp path as usual.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

import boto3

logger = logging.getLogger(__name__)


def download_data_from_s3() -> tuple[str, str, str]:
    """Download data assets from S3 and return local paths.

    Returns:
        (template_path, data_dir, embeddings_dir)
    """
    bucket = os.environ["DATA_BUCKET"]
    region = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
    template_key = os.environ.get(
        "TEMPLATE_S3_KEY", "etemplate/Initial Submission_Revision9.etemplate"
    )
    data_prefix = os.environ.get("DATA_S3_PREFIX", "data")

    s3 = boto3.client("s3", region_name=region)
    tmp = Path(tempfile.mkdtemp(prefix="compliance-data-"))

    logger.info(f"Downloading data from s3://{bucket} to {tmp}")

    # Download etemplate
    template_path = tmp / "etemplate.json"
    s3.download_file(bucket, template_key, str(template_path))
    logger.info(f"Downloaded etemplate: {template_key}")

    # Download data files
    data_dir = tmp / "data"
    data_dir.mkdir()
    for filename in ["field_prompts.json", "free_text_fields_reference.json"]:
        key = f"{data_prefix}/{filename}"
        local_path = data_dir / filename
        try:
            s3.download_file(bucket, key, str(local_path))
            logger.info(f"Downloaded {key}")
        except Exception as e:
            logger.warning(f"Could not download {key}: {e}")

    # Download embeddings
    embeddings_dir = tmp / "embeddings"
    embeddings_dir.mkdir()
    for filename in ["vectors.npy", "metadata.json"]:
        key = f"{data_prefix}/embeddings/{filename}"
        local_path = embeddings_dir / filename
        try:
            s3.download_file(bucket, key, str(local_path))
            logger.info(f"Downloaded {key}")
        except Exception as e:
            logger.warning(f"Could not download {key}: {e}")

    return str(template_path), str(data_dir), str(embeddings_dir)
