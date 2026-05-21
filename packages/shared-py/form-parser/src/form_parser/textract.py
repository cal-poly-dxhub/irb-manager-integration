"""AWS Textract wrappers for synchronous and asynchronous document analysis."""

import os
import time
from typing import Any


def analyze_document(client: Any, document_bytes: bytes) -> dict:
    """Run synchronous Textract analysis on a document (< 10 pages).

    Args:
        client: boto3 textract client
        document_bytes: PDF or image bytes

    Returns:
        Textract response dictionary
    """
    response = client.analyze_document(
        Document={"Bytes": document_bytes},
        FeatureTypes=["FORMS"],
    )
    return response


def process_pdf(client: Any, input_path: str) -> dict:
    """Process a PDF/image file with Textract synchronously.

    Args:
        client: boto3 textract client
        input_path: Path to PDF or image file

    Returns:
        Textract response dictionary
    """
    with open(input_path, "rb") as f:
        doc_bytes = f.read()
    return analyze_document(client, doc_bytes)


def upload_to_s3(s3_client: Any, file_path: str, bucket: str, key: str | None = None) -> str:
    """Upload a file to S3.

    Args:
        s3_client: boto3 S3 client
        file_path: Local path to file
        bucket: S3 bucket name
        key: S3 object key (defaults to basename of file_path)

    Returns:
        The S3 key used
    """
    if key is None:
        key = os.path.basename(file_path)
    s3_client.upload_file(file_path, bucket, key)
    return key


def start_analysis(textract_client: Any, bucket: str, key: str) -> str:
    """Start async Textract analysis job.

    Args:
        textract_client: boto3 textract client
        bucket: S3 bucket containing document
        key: S3 object key

    Returns:
        Job ID string
    """
    response = textract_client.start_document_analysis(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}},
        FeatureTypes=["FORMS", "TABLES"],
    )
    return response["JobId"]


def poll_for_completion(
    textract_client: Any,
    job_id: str,
    poll_interval: int = 5,
    verbose: bool = True,
) -> None:
    """Poll Textract job until completion.

    Args:
        textract_client: boto3 textract client
        job_id: Job ID to poll
        poll_interval: Seconds between status checks
        verbose: Print progress to stdout

    Raises:
        RuntimeError: If job fails
    """
    start = time.monotonic()

    while True:
        response = textract_client.get_document_analysis(JobId=job_id)
        status = response["JobStatus"]
        elapsed = time.monotonic() - start

        if status == "SUCCEEDED":
            if verbose:
                print(f"\rJob completed in {elapsed:.1f}s")
            return
        elif status == "FAILED":
            message = response.get("StatusMessage", "unknown error")
            raise RuntimeError(f"Textract job failed after {elapsed:.1f}s: {message}")
        else:
            if verbose:
                print(f"\rStatus: {status} — elapsed {elapsed:.1f}s", end="", flush=True)
            time.sleep(poll_interval)


def collect_results(textract_client: Any, job_id: str) -> list[dict]:
    """Collect all blocks from a completed Textract job.

    Args:
        textract_client: boto3 textract client
        job_id: Job ID

    Returns:
        List of Textract block dictionaries
    """
    blocks = []
    next_token = None

    while True:
        kwargs = {"JobId": job_id}
        if next_token:
            kwargs["NextToken"] = next_token

        response = textract_client.get_document_analysis(**kwargs)
        blocks.extend(response.get("Blocks", []))

        next_token = response.get("NextToken")
        if not next_token:
            break

    return blocks


def process_pdf_async(
    s3_client: Any,
    textract_client: Any,
    input_path: str,
    bucket: str,
    poll_interval: int = 5,
    verbose: bool = True,
) -> list[dict]:
    """Process a multi-page PDF/image with async Textract.

    Args:
        s3_client: boto3 S3 client
        textract_client: boto3 textract client
        input_path: Path to PDF or image file
        bucket: S3 bucket for uploading the document
        poll_interval: Seconds between status checks
        verbose: Print progress messages

    Returns:
        List of Textract block dictionaries
    """
    if verbose:
        print(f"Uploading {input_path} to s3://{bucket}/...")

    key = upload_to_s3(s3_client, input_path, bucket)

    if verbose:
        print("Starting Textract analysis...")

    job_id = start_analysis(textract_client, bucket, key)

    if verbose:
        print(f"Job ID: {job_id}")

    poll_for_completion(textract_client, job_id, poll_interval, verbose)

    if verbose:
        print("Collecting results...")

    return collect_results(textract_client, job_id)
