curl -X POST http://localhost:5001/parse \
    -H "Content-Type: application/json" \
    -d '{
      "file_path": "/Users/spandan/Projects/dxhub/research-compliance/data/IACUC Initial Submission 4624.pdf",
      "s3_bucket": "research-compliance-demo-output"
    }'
