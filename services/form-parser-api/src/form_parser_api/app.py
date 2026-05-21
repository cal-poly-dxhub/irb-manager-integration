"""Flask API for form parsing using AWS Textract."""

import os
import tempfile
import uuid
from pathlib import Path

import boto3
from botocore.config import Config
from baml_client import b
from baml_client.types import Form, ParsedContent
from flask import Flask, jsonify, request
from flask_cors import CORS
from pydantic import ValidationError
from werkzeug.utils import secure_filename

from form_parser import (
    collect_results,
    join_paragraphs,
    poll_for_completion,
    process_pdf,
    process_pdf_async,
    start_analysis,
)
from form_parser_api.models import (
    CompleteUploadRequest,
    CompleteUploadResponse,
    ErrorResponse,
    GetPartUrlRequest,
    GetPartUrlResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    ParseRequest,
    ParseResponse,
)

app = Flask(__name__)

# Enable CORS for all routes (allows requests from Next.js dev server)
CORS(app)

# Configure upload directory
UPLOAD_DIR = Path(tempfile.gettempdir()) / "form-parser-uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# S3 bucket configuration (from environment or CDK output)
S3_BUCKET = os.environ.get("S3_UPLOAD_BUCKET")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
S3_PRESIGNED_URL_EXPIRATION = 3600  # 1 hour

# S3 client configuration to force regional endpoints
S3_CONFIG = Config(
    region_name=AWS_REGION,
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
)


def get_s3_client():
    """Get S3 client configured for the correct region."""
    return boto3.client("s3", region_name=AWS_REGION, config=S3_CONFIG)


def assign_ids(form_dict: dict) -> dict:
    """Recursively assign UUIDs to all id fields in the form structure.

    Args:
        form_dict: Dictionary representation of Form

    Returns:
        Modified dictionary with UUIDs assigned to all id fields
    """
    if isinstance(form_dict, dict):
        # Assign UUID to id field if it exists and is empty
        if "id" in form_dict and (form_dict["id"] == "" or form_dict["id"] is None):
            form_dict["id"] = str(uuid.uuid4())

        # Recursively process all nested dictionaries
        for key, value in form_dict.items():
            if isinstance(value, dict):
                assign_ids(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        assign_ids(item)

    return form_dict


def parse_document(
    file_path: str | None,
    s3_bucket: str | None,
    s3_key: str | None,
    gap_factor: float,
) -> Form:
    """Parse a document using Textract and return a Form.

    Args:
        file_path: Path to local document file (if not using S3)
        s3_bucket: S3 bucket containing the file (if using S3)
        s3_key: S3 object key (if using S3)
        gap_factor: Paragraph grouping threshold

    Returns:
        Form object with parsed elements

    Raises:
        ValueError: If neither local file nor S3 location is provided
        FileNotFoundError: If local file doesn't exist
        RuntimeError: If Textract processing fails
    """
    textract_client = boto3.client("textract", region_name=AWS_REGION)

    # Determine if using S3 or local file
    if s3_bucket and s3_key:
        # Process from S3 (file already uploaded)
        app.logger.info(f"Processing S3 file: s3://{s3_bucket}/{s3_key}")

        # Start async Textract analysis on existing S3 object
        job_id = start_analysis(textract_client, s3_bucket, s3_key)
        app.logger.info(f"Started Textract job: {job_id}")

        # Wait for completion
        poll_for_completion(textract_client, job_id, poll_interval=5, verbose=False)

        # Collect results
        blocks = collect_results(textract_client, job_id)
    elif file_path:
        # Process local file
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        app.logger.info(f"Processing local file: {file_path}")

        # Determine file size to choose sync vs async processing
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if file_size_mb > 5:
            if not s3_bucket:
                raise ValueError(
                    "S3 bucket required for large documents (>5MB). "
                    "Provide s3_bucket in the request."
                )
            s3_client = get_s3_client()
            blocks = process_pdf_async(
                s3_client,
                textract_client,
                file_path,
                s3_bucket,
                verbose=False,
            )
        else:
            # Sync processing for small documents
            response = process_pdf(textract_client, file_path)
            blocks = response.get("Blocks", [])
    else:
        raise ValueError(
            "Either file_path or both s3_bucket and s3_key must be provided"
        )

    # Convert blocks to paragraphs and tables
    elements = join_paragraphs(blocks, gap_factor)

    # Create ParsedContent from raw elements
    parsed_content = ParsedContent(elements=elements)
    app.logger.info(f"Created ParsedContent with {len(elements)} elements")

    # Call RefineForm to convert ParsedContent into structured Form with grouped members
    app.logger.info("Calling RefineForm to structure the form...")
    refined_form = b.RefineForm(parsed_content)
    app.logger.info(f"RefineForm returned {len(refined_form.members)} form members")

    # Assign UUIDs to all id fields in the form structure
    form_dict = refined_form.model_dump()
    form_dict = assign_ids(form_dict)

    # Reconstruct Form from dict with assigned IDs
    form = Form(**form_dict)
    return form


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


@app.route("/initiate-upload", methods=["POST"])
def initiate_upload():
    """Initiate a multipart upload.

    Request body should be JSON matching InitiateUploadRequest schema.
    Returns JSON matching InitiateUploadResponse schema.
    """
    try:
        if not S3_BUCKET:
            return jsonify(
                ErrorResponse(
                    message="S3 bucket not configured. Set S3_UPLOAD_BUCKET environment variable."
                ).model_dump()
            ), 500

        # Validate request
        data = request.get_json()
        if not data:
            return jsonify(ErrorResponse(message="Request body required").model_dump()), 400

        upload_request = InitiateUploadRequest(**data)

        # Generate unique S3 key with timestamp and UUID
        timestamp = uuid.uuid4().hex[:8]
        safe_filename = secure_filename(upload_request.filename)
        s3_key = f"uploads/{timestamp}-{safe_filename}"

        # Initiate multipart upload
        s3_client = get_s3_client()
        response = s3_client.create_multipart_upload(
            Bucket=S3_BUCKET,
            Key=s3_key,
            ContentType=upload_request.content_type,
        )

        upload_id = response["UploadId"]
        app.logger.info(f"Initiated multipart upload: {upload_id} for key: {s3_key}")

        return jsonify(
            InitiateUploadResponse(
                upload_id=upload_id,
                s3_key=s3_key,
                s3_bucket=S3_BUCKET,
            ).model_dump()
        ), 200

    except ValidationError as e:
        app.logger.error(f"Validation error: {e}", exc_info=True)
        return jsonify(ErrorResponse(message=f"Invalid request: {e}").model_dump()), 400
    except Exception as e:
        app.logger.error(f"Error initiating upload: {e}", exc_info=True)
        return jsonify(ErrorResponse(message=f"Internal error: {str(e)}").model_dump()), 500


@app.route("/get-part-url", methods=["POST"])
def get_part_url():
    """Get presigned URL for uploading a part.

    Request body should be JSON matching GetPartUrlRequest schema.
    Returns JSON matching GetPartUrlResponse schema.
    """
    try:
        if not S3_BUCKET:
            return jsonify(
                ErrorResponse(
                    message="S3 bucket not configured. Set S3_UPLOAD_BUCKET environment variable."
                ).model_dump()
            ), 500

        # Validate request
        data = request.get_json()
        if not data:
            return jsonify(ErrorResponse(message="Request body required").model_dump()), 400

        part_request = GetPartUrlRequest(**data)

        # Generate presigned URL for uploading the part
        s3_client = get_s3_client()
        presigned_url = s3_client.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": S3_BUCKET,
                "Key": part_request.s3_key,
                "UploadId": part_request.upload_id,
                "PartNumber": part_request.part_number,
            },
            ExpiresIn=S3_PRESIGNED_URL_EXPIRATION,
        )

        return jsonify(
            GetPartUrlResponse(
                upload_url=presigned_url,
                part_number=part_request.part_number,
            ).model_dump()
        ), 200

    except ValidationError as e:
        app.logger.error(f"Validation error: {e}", exc_info=True)
        return jsonify(ErrorResponse(message=f"Invalid request: {e}").model_dump()), 400
    except Exception as e:
        app.logger.error(f"Error generating part URL: {e}", exc_info=True)
        return jsonify(ErrorResponse(message=f"Internal error: {str(e)}").model_dump()), 500


@app.route("/complete-upload", methods=["POST"])
def complete_upload():
    """Complete a multipart upload.

    Request body should be JSON matching CompleteUploadRequest schema.
    Returns JSON matching CompleteUploadResponse schema.
    """
    try:
        if not S3_BUCKET:
            return jsonify(
                ErrorResponse(
                    message="S3 bucket not configured. Set S3_UPLOAD_BUCKET environment variable."
                ).model_dump()
            ), 500

        # Validate request
        data = request.get_json()
        if not data:
            return jsonify(ErrorResponse(message="Request body required").model_dump()), 400

        complete_request = CompleteUploadRequest(**data)

        # Complete the multipart upload
        s3_client = get_s3_client()
        response = s3_client.complete_multipart_upload(
            Bucket=S3_BUCKET,
            Key=complete_request.s3_key,
            UploadId=complete_request.upload_id,
            MultipartUpload={"Parts": complete_request.parts},
        )

        app.logger.info(f"Completed multipart upload: {complete_request.upload_id}")

        return jsonify(
            CompleteUploadResponse(
                s3_key=complete_request.s3_key,
                s3_bucket=S3_BUCKET,
                location=response["Location"],
            ).model_dump()
        ), 200

    except ValidationError as e:
        app.logger.error(f"Validation error: {e}", exc_info=True)
        return jsonify(ErrorResponse(message=f"Invalid request: {e}").model_dump()), 400
    except Exception as e:
        app.logger.error(f"Error completing upload: {e}", exc_info=True)
        return jsonify(ErrorResponse(message=f"Internal error: {str(e)}").model_dump()), 500


@app.route("/upload", methods=["POST"])
def upload():
    """Upload a file and return its absolute path on the server.

    Accepts multipart/form-data with a 'file' field.
    Returns the absolute path where the file was saved.
    """
    try:
        if "file" not in request.files:
            return jsonify(ErrorResponse(message="No file provided").model_dump()), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify(ErrorResponse(message="No file selected").model_dump()), 400

        # Secure the filename and save to upload directory
        filename = secure_filename(file.filename)
        file_path = UPLOAD_DIR / filename
        file.save(str(file_path))

        return jsonify({
            "status": "success",
            "file_path": str(file_path.absolute())
        }), 200

    except Exception as e:
        app.logger.error(f"Error uploading file: {e}", exc_info=True)
        return jsonify(ErrorResponse(message=f"Upload failed: {str(e)}").model_dump()), 500


@app.route("/parse", methods=["POST"])
def parse():
    """Parse a document and return structured form elements.

    Request body should be JSON matching ParseRequest schema.
    Returns JSON matching ParseResponse schema.
    """
    try:
        # Validate request
        data = request.get_json()
        if not data:
            return jsonify(ErrorResponse(message="Request body required").model_dump()), 400

        app.logger.info(f"Parse request received: {data}")
        parse_request = ParseRequest(**data)

        # Parse the document (returns a Form)
        form = parse_document(
            parse_request.file_path,
            parse_request.s3_bucket,
            parse_request.s3_key,
            parse_request.gap_factor,
        )

        # Construct and return response with the Form
        response = ParseResponse(form=form)
        return jsonify(response.model_dump()), 200

    except ValidationError as e:
        app.logger.error(f"Validation error: {e}", exc_info=True)
        return jsonify(ErrorResponse(message=f"Invalid request: {e}").model_dump()), 400
    except FileNotFoundError as e:
        return jsonify(ErrorResponse(message=str(e)).model_dump()), 404
    except ValueError as e:
        return jsonify(ErrorResponse(message=str(e)).model_dump()), 400
    except Exception as e:
        app.logger.error(f"Error parsing document: {e}", exc_info=True)
        return jsonify(ErrorResponse(message=f"Internal error: {str(e)}").model_dump()), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify(ErrorResponse(message="Endpoint not found").model_dump()), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify(ErrorResponse(message="Internal server error").model_dump()), 500


if __name__ == "__main__":
    import sys

    # Accept port as command-line argument
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(host="0.0.0.0", port=port, debug=True)
