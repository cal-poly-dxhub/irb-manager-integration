# Form Parser API

Flask API service for parsing documents using AWS Textract.

## Features

- Parse PDF and image files into structured paragraphs and tables
- Automatic selection of sync/async Textract processing based on file size
- Pydantic validation for inputs and outputs
- RESTful JSON API

## API Endpoints

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

### `POST /parse`
Parse a document and return structured elements.

**Request Body:**
```json
{
  "file_path": "/absolute/path/to/document.pdf",
  "gap_factor": 1.5,
  "s3_bucket": "my-bucket-name"
}
```

**Request Fields:**
- `file_path` (required): Absolute path to the document file
- `gap_factor` (optional): Paragraph grouping threshold (default: 1.5, range: 0.5-5.0)
- `s3_bucket` (optional): S3 bucket for async processing (required for files >5MB)

**Response:**
```json
{
  "status": "success",
  "form": {
    "elements": [
      {
        "type": "paragraph",
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "content": "This is a paragraph...",
        "page": 1
      },
      {
        "type": "table",
        "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "content": [
          ["Header 1", "Header 2"],
          ["Cell 1", "Cell 2"]
        ],
        "page": 1
      }
    ]
  }
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Error description"
}
```

## Running the Service

### Development
```bash
# Run with the included run script (uses port 5001 by default)
uv run --package form-parser-api python services/form-parser-api/run.py --debug

# Run on a different port
uv run --package form-parser-api python services/form-parser-api/run.py --port 8000 --debug

# Or run directly
uv run --package form-parser-api python services/form-parser-api/src/form_parser_api/app.py
```

### Production
For production, use a WSGI server like Gunicorn:
```bash
uv run --package form-parser-api gunicorn -w 4 -b 0.0.0.0:5001 'form_parser_api:app'
```

**Note:** Port 5000 is often used by AirPlay Receiver on macOS. This service defaults to port 5001.

## Example Usage

```bash
curl -X POST http://localhost:5001/parse \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/Users/spandan/Documents/form.pdf",
    "gap_factor": 1.5,
    "s3_bucket": "my-textract-bucket"
  }'
```

## AWS Configuration

Ensure AWS credentials are configured with access to:
- Textract (for document analysis)
- S3 (for async processing of large documents)

Set credentials via:
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- AWS credentials file (`~/.aws/credentials`)
- IAM role (when running on AWS)

## Dependencies

- `flask` - Web framework
- `boto3` - AWS SDK
- `pydantic` - Data validation
- `form-parser` - Document parsing logic (workspace package)
