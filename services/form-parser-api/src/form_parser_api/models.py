"""Pydantic models for form parser API requests and responses."""

from typing import Literal

from baml_client.types import Form
from pydantic import BaseModel, Field


class InitiateUploadRequest(BaseModel):
    """Request to initiate a multipart upload.

    Attributes:
        filename: Name of the file to upload
        content_type: MIME type of the file (default: application/pdf)
    """
    filename: str = Field(..., description="Name of the file to upload")
    content_type: str = Field(
        default="application/pdf",
        description="MIME type of the file"
    )


class InitiateUploadResponse(BaseModel):
    """Response for initiated multipart upload.

    Attributes:
        upload_id: Multipart upload ID
        s3_key: S3 object key where the file will be stored
        s3_bucket: S3 bucket name
    """
    upload_id: str
    s3_key: str
    s3_bucket: str


class GetPartUrlRequest(BaseModel):
    """Request to get presigned URL for a part.

    Attributes:
        upload_id: Multipart upload ID
        s3_key: S3 object key
        part_number: Part number (1-10000)
    """
    upload_id: str = Field(..., description="Multipart upload ID")
    s3_key: str = Field(..., description="S3 object key")
    part_number: int = Field(..., ge=1, le=10000, description="Part number")


class GetPartUrlResponse(BaseModel):
    """Response containing presigned URL for a part.

    Attributes:
        upload_url: Presigned URL for uploading the part
        part_number: Part number
    """
    upload_url: str
    part_number: int


class CompleteUploadRequest(BaseModel):
    """Request to complete a multipart upload.

    Attributes:
        upload_id: Multipart upload ID
        s3_key: S3 object key
        parts: List of uploaded parts with ETags
    """
    upload_id: str = Field(..., description="Multipart upload ID")
    s3_key: str = Field(..., description="S3 object key")
    parts: list[dict[str, str | int]] = Field(
        ..., description="List of parts with PartNumber and ETag"
    )


class CompleteUploadResponse(BaseModel):
    """Response for completed multipart upload.

    Attributes:
        s3_key: S3 object key of the uploaded file
        s3_bucket: S3 bucket name
        location: S3 URL of the uploaded file
    """
    s3_key: str
    s3_bucket: str
    location: str


class ParseRequest(BaseModel):
    """Request to parse a form document.

    Attributes:
        file_path: Absolute path to the PDF or image file to parse (for local files)
        s3_bucket: S3 bucket name containing the file (for S3 files)
        s3_key: S3 object key of the file (for S3 files)
        gap_factor: Vertical gap threshold for paragraph grouping (default: 1.5)
    """
    file_path: str | None = Field(
        default=None,
        description="Absolute path to the document file (for local files)"
    )
    s3_bucket: str | None = Field(
        default=None,
        description="S3 bucket name containing the file"
    )
    s3_key: str | None = Field(
        default=None,
        description="S3 object key of the file"
    )
    gap_factor: float = Field(
        default=1.5,
        ge=0.5,
        le=5.0,
        description="Max vertical gap as a multiple of line height for paragraph grouping"
    )


class ParseResponse(BaseModel):
    """Response containing parsed form.

    Attributes:
        form: The parsed and refined form with structured members (grouped fields, paragraphs, and tables)
        status: Processing status
        message: Optional status message
    """
    form: Form
    status: Literal["success", "error"] = "success"
    message: str | None = None


class ErrorResponse(BaseModel):
    """Error response."""
    status: Literal["error"] = "error"
    message: str
