# IRB Manager Integration

## Project Goal

Build an integration between our existing AI compliance assistant agent and IRBManager (a third-party IRB submission platform). Instead of maintaining our own form UI and having users copy-paste, the agent will directly interact with IRBManager's forms.

## Origin

This codebase was forked from `cal-poly-dxhub/research-compliance` (the standalone compliance assistant). The existing code works as a self-contained app with its own form rendering. The goal is to adapt the agent to work against IRBManager's form system instead.

## Architecture Overview

### Backend (Python 3.13, Flask)

- `services/compliance-assistant-api/` - The main API service
  - `agent.py` - Agentic loop using AWS Bedrock Converse API (Claude Sonnet). Sends messages, executes tool calls, loops until text response. Max 250 turns. SSE streaming with event types: message, fieldUpdate, toolCall, toolResult, thinking, flaggedIssue, error, done
  - `agent_tools.py` - 7 tools (get_visible_sections, get_fields_in_section, get_field_guidance, fill_field, flag_issue, search_similar_fields, get_document_content). Tools filtered by mode via `get_tools_for_mode()`
  - `form_state.py` - In-memory representation of the form tree (sections, fields, visibility rules, values). Built fresh per request from eTemplate JSON + user's current values
  - `app.py` - Flask routes. POST /chat (SSE stream), session CRUD endpoints. Loads data from S3 (deployed) or local filesystem (dev)
  - `models.py` - Pydantic models. AppMode enum (coauthor, review, adapt), ChatRequest, FlaggedIssue
  - `data/` - Data layer:
    - `field_prompts.py` - Maps fields to writing guidance, instructions, past examples
    - `vector_store.py` - Cosine similarity search over pre-computed field embeddings
    - `embeddings.py` - Bedrock Titan embeddings client
    - `s3_loader.py` - Downloads data assets from S3 at container startup
    - `session_store.py` - DynamoDB session persistence (conversation history, form values, attachments)

### Frontend (React + Vite + TypeScript)

- `apps/compliance-assistant/` - Split-pane SPA
  - Left pane: Chat with SSE streaming, file upload, session management
  - Right pane: Form rendered from eTemplate JSON with field-level annotations
  - `hooks/useChat.ts` - SSE connection, event stream parsing, field update accumulation
  - `hooks/useSession.ts` - Session lifecycle (create/load/switch/delete), localStorage + URL param sync
  - `FormContext.tsx` - Central form value state shared between chat and form panels

### Infrastructure (CDK)

- `apps/infra/` - AWS CDK stacks
  - V2 stack: Fargate (1 vCPU/2GB), ALB, S3 (data assets), DynamoDB (sessions), CloudFront (SPA + API routing)
  - IAM roles for Bedrock, S3, DynamoDB access

### 3 Application Modes

1. **Co-Author** (default) - Agent fills form fields section-by-section, asks for approval. Has `fill_field` tool.
2. **Review** - Agent reads existing form values and flags compliance issues. Has `flag_issue` tool instead of `fill_field`.
3. **Adapt** - Helps researchers modify a previously submitted form for resubmission. Same tools as Co-Author but different system prompt.

Mode differentiation: system prompt selection + tool availability filtering in `get_tools_for_mode()`.

## Key Data Files

- `data/compliance-assistant/field_prompts.json` - Structured guidance per form field (instructions, mistakes, examples)
- `data/compliance-assistant/embeddings/` - Pre-computed Titan embeddings for vector search
- `apps/compliance-assistant/public/Initial Submission_Revision9.etemplate` - Cayuse form definition (JSON)
- `data/compliance-assistant/mappings/` - Example form value mappings from past approved submissions

## Running Locally

```bash
# Backend (from repo root)
cd services/compliance-assistant-api
USE_MOCK=true python run.py  # Mock mode (no AWS credentials needed)
# Or with real Bedrock:
python run.py  # Requires AWS credentials with Bedrock access

# Frontend
cd apps/compliance-assistant
npm install && npm run dev
```

Environment variables:
- `USE_MOCK=true` - Use mock agent (no Bedrock calls)
- `AGENT_MODEL_ID` - Bedrock model ID (default: us.anthropic.claude-sonnet-4-6)
- `AWS_REGION` - AWS region (default: us-west-2)
- `DATA_BUCKET` - S3 bucket name (triggers S3 loading vs local filesystem)
- `DYNAMODB_TABLE` - DynamoDB table name for sessions

## What Needs to Change for IRBManager Integration

The core agent logic (agentic loop, RAG, field guidance) stays the same. What changes:

1. **Form interaction layer** - Instead of operating on our in-memory FormState from an eTemplate, the agent needs to interact with IRBManager's form API/DOM
2. **Frontend** - May become a browser extension, embedded widget, or headless service rather than a standalone SPA
3. **Tool definitions** - Tools like `fill_field`, `get_fields_in_section` need to map to IRBManager's form structure instead of our eTemplate
4. **Session management** - May need to tie into IRBManager's session/auth rather than our own DynamoDB sessions

## Code Style

- No emojis in code
- Keep commit messages simple and brief
- Python: type hints, pydantic models for API contracts
- TypeScript: strict mode, functional components, hooks pattern
- Never use `cat` in shell commands (it's aliased to `bat` on this machine and corrupts output)
