
# Collaboration

Thanks for your interest in our solution. Having specific examples of replication and cloning allows us to continue to grow and scale our work. If you clone or download this repository, kindly shoot us a quick email to let us know you are interested in this work!

[wwps-cic@amazon.com]

---

# Disclaimers 

Customers are responsible for making their own independent assessment of the information in this document. 

This document: 

(a) is for informational purposes only, 

(b) references AWS product offerings and practices, which are subject to change without notice, 

(c) does not create any commitments or assurances from AWS and its affiliates, suppliers or licensors. AWS products or services are provided "as is" without warranties, representations, or conditions of any kind, whether express or implied. The responsibilities and liabilities of AWS to its customers are controlled by AWS agreements, and this document is not part of, nor does it modify, any agreement between AWS and its customers, and 

(d) is not to be considered a recommendation or viewpoint of AWS. 

Additionally, you are solely responsible for testing, security and optimizing all code and assets on GitHub repo, and all such code and assets should be considered: 

(a) as-is and without warranties or representations of any kind, 

(b) not suitable for production environments, or on production or other critical data, and 

(c) to include shortcuts in order to support rapid prototyping such as, but not limited to, relaxed authentication and authorization and a lack of strict adherence to security best practices. 

All work produced is open source. More information can be found in the GitHub repo.

# IRB Manager Integration

An AI compliance assistant that helps university researchers complete IRB (Human Ethics) submission forms, built on AWS Bedrock (Claude Sonnet). The project is being adapted from a standalone form-filling app into an integration with IRBManager, a third-party IRB submission platform.

This codebase was forked from `cal-poly-dxhub/research-compliance`.

## How it works

The agent runs an agentic loop against AWS Bedrock's Converse API: it reads a form's fields and visibility rules, asks the user clarifying questions, fills in fields, and flags compliance issues, streaming its reasoning and form updates back to the client over SSE. It supports three modes:

1. **Co-Author** (default) - fills the form section-by-section with user approval
2. **Review** - reads existing form values and flags compliance issues
3. **Adapt** - helps modify a previously submitted form for resubmission

See `CLAUDE.md` for a detailed architecture breakdown.

## Project structure

```
apps/compliance-assistant/          React + Vite + TypeScript frontend (split-pane chat/form UI)
apps/cayuse-form-viewer/            Standalone viewer for Cayuse eTemplate form definitions
services/compliance-assistant-api/  Flask backend: agentic loop, tools, RAG, session storage
packages/shared-py/                 Shared Python packages
packages/shared-ts/                 Shared TypeScript packages
baml_src/                           BAML source files
data/                                Field prompts, embeddings, and sample test documents
docs/                                Architecture and feature design notes
scripts/                             Data processing and tooling scripts (PDF parsing, embeddings, Lambda packaging)
```

## Prerequisites

- Node.js (v20+)
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- AWS credentials with access to Amazon Bedrock (Claude + Titan Embeddings), unless running in mock mode

## Running locally

### Quick start

From the repo root:

```bash
./apps/compliance-assistant/demo.sh
```

This starts both the backend (Flask, port 5002) and frontend (Vite, port 5173) in one terminal. Press `Ctrl+C` to stop both. By default it calls live AWS Bedrock; set `USE_MOCK=true` to run without AWS credentials.

### Backend and frontend separately

```bash
# Backend (Flask API on port 5002)
cd services/compliance-assistant-api
uv run python run.py
# Or without AWS credentials:
USE_MOCK=true uv run python run.py

# Frontend (Vite dev server on port 5173)
cd apps/compliance-assistant
npm install && npm run dev
```

The Vite dev server proxies `/api` requests to the backend on port 5002.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_MOCK` | `false` | Use a mock agent instead of calling Bedrock |
| `AGENT_MODEL_ID` | `us.anthropic.claude-sonnet-4-6` | Bedrock model ID |
| `AWS_REGION` | `us-west-2` | AWS region |
| `DATA_BUCKET` | unset | S3 bucket for data assets; if unset, data is loaded from the local filesystem |
| `DYNAMODB_TABLE` | unset | DynamoDB table for session persistence; if unset, sessions are disabled but chat still works |
| `TEMPLATE_PATH` | auto-detected | Path to the `.etemplate` form file |
| `DATA_DIR` | auto-detected | Path to `data/compliance-assistant/` |
| `EMBEDDINGS_DIR` | auto-detected | Path to the embeddings directory |

See `apps/compliance-assistant/README.md` for frontend-specific details and sample test documents.

## Code style

- No emojis in code
- Keep commit messages simple and brief
- Python: type hints, pydantic models for API contracts
- TypeScript: strict mode, functional components, hooks pattern


