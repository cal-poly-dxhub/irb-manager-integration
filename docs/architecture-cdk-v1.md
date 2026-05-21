# CDK Architecture — Compliance Assistant

## Overview

Production-grade AWS deployment for the compliance assistant. Stateless compute, managed data stores, and proper separation of concerns.

## Architecture Diagram

```
                           ┌──────────────────────┐
                           │   CloudFront CDN      │
                           │   (HTTPS, caching)    │
                           └───────┬──────┬────────┘
                                   │      │
                       /* (static) │      │ /api/*
                                   │      │
                        ┌──────────▼┐   ┌─▼───────────────┐
                        │ S3 Bucket │   │ ALB (public)     │
                        │ (frontend)│   │ port 80 → 5002   │
                        └───────────┘   └──────┬───────────┘
                                               │
                                      ┌────────▼──────────┐
                                      │  ECS Fargate       │
                                      │  (Flask + Gunicorn) │
                                      │  stateless          │
                                      └──┬───┬───┬───┬─────┘
                                         │   │   │   │
                    ┌────────────────────┘   │   │   └──────────────────┐
                    │                        │   │                      │
           ┌────────▼────────┐  ┌────────────▼┐ ┌▼───────────────┐  ┌──▼──────────┐
           │  AWS Bedrock    │  │  S3 (data)   │ │  DynamoDB      │  │  Aurora      │
           │  - Claude       │  │  - etemplate │ │  - sessions    │  │  Serverless  │
           │  - Titan Embed  │  │  - prompts   │ │  - form state  │  │  pgvector    │
           └─────────────────┘  │  - raw docs  │ │  - history     │  │  (phase 2)   │
                                └──────────────┘ └────────────────┘  └──────────────┘
```

## Phased Rollout

### Phase 1 (this PR)
- S3 + CloudFront for frontend
- ECS Fargate + ALB for backend
- S3 for data assets (etemplate, field prompts, embeddings)
- DynamoDB for session/form state persistence
- Session identity, lifecycle, and resume flow
- IAM roles for Bedrock access

### Phase 2 (next PR)
- Aurora Serverless v2 with pgvector
- Migrate embeddings from S3/numpy to pgvector
- Structured queries (filter by department, study type, field)

### Phase 3 (separate PR)
- Co-Author, Review, and Adapt modes
- Mode-specific system prompts and tool sets

---

## Phase 1 Components

### 1. Frontend — S3 + CloudFront

Vite static build served from a private S3 bucket via CloudFront.

- S3 bucket: private, accessed only via CloudFront OAC (origin access control)
- CloudFront default root object: `index.html`
- SPA fallback: custom error response redirects 403/404 to `/index.html`
- Frontend `VITE_API_URL` set to `""` so `/api/*` routes to the same CloudFront domain

### 2. Backend — ECS Fargate + ALB

Dockerized Flask API running Gunicorn with 4 workers behind an ALB.

**Why Fargate (not Lambda):**
- Agent loop runs up to 250 turns with SSE streaming
- Lambda has 15-min timeout; API Gateway has 29-sec REST timeout
- SSE requires long-lived HTTP connections — ALB supports this natively
- Flask loads data at startup; Lambda cold starts would be painful

**Configuration:**
- VPC: 2 public subnets (no NAT gateway, Fargate gets public IP)
- Fargate: 0.5 vCPU / 1 GB, Gunicorn with 4 workers
- ALB: public, health check on `/health`
- Single task for v1 (a handful of testers)

### 3. Data Assets — S3

Data decoupled from the container. Loaded at startup, can be updated without redeploying.

| Asset | Path in S3 | Size |
|---|---|---|
| etemplate | `etemplate/Initial Submission_Revision9.etemplate` | 492 KB |
| field_prompts.json | `data/field_prompts.json` | 118 KB |
| free_text_fields_reference.json | `data/free_text_fields_reference.json` | 82 KB |
| embeddings/vectors.npy | `data/embeddings/vectors.npy` | 356 KB |
| embeddings/metadata.json | `data/embeddings/metadata.json` | 62 KB |

**Total: ~1 MB.** Container downloads from S3 at startup via the task role.

### 4. Session Persistence — DynamoDB

#### 4.1 The Problem

Today, all state lives in the browser:
- **Form values** — React state in `FormContext` (`useState<FormValues>`)
- **Conversation history** — React state in `useChat` (`useState<ChatMessage[]>`)
- **Activity log** — React state in `useChat` (`useState<ActivityLogEntry[]>`)
- **Uploaded attachment text** — React state in `useChat` (`useState pendingFiles`)

If the user refreshes the page, closes the tab, or switches devices, everything is lost.

#### 4.2 Identity (No Auth)

There is no user authentication in v1. We identify sessions, not users.

**Session ID resolution order (on page load):**
1. Check URL for `?session=<uuid>` — if present, use it
2. Check `localStorage` for `compliance-assistant-session-id` — if present, use it
3. Neither found — create a new session via `POST /api/sessions`

**This gives us:**
- **Auto-resume:** User closes tab, reopens site → resumes from localStorage
- **Shareable sessions:** User copies URL with `?session=abc-123` → another person can view/continue the same session
- **Clean start:** User clears localStorage or opens in incognito → fresh session

#### 4.3 Session Lifecycle

| Event | What Happens |
|---|---|
| **User opens site (no existing session)** | Frontend calls `POST /api/sessions`. Backend creates DynamoDB item, returns `sessionId`. Frontend stores in localStorage + updates URL. |
| **User opens site (existing session)** | Frontend calls `GET /api/sessions/:id`. Backend returns saved state. Frontend hydrates form values, conversation history, and attachment metadata. |
| **User sends a chat message** | Frontend includes `sessionId` in the `/api/chat` request. After the agent finishes (SSE stream completes), backend persists the updated conversation history and form values to DynamoDB. |
| **User manually edits a form field** | Frontend debounces changes (2 second delay), then calls `PATCH /api/sessions/:id/form` with the current form values. |
| **User uploads a file** | Extracted text is included in the chat message (existing behavior). The text persists as part of conversation history in DynamoDB. Attachment filenames are stored in session metadata for display on resume. |
| **Session expires** | DynamoDB TTL auto-deletes items after 90 days. |

#### 4.4 What Gets Persisted

| Data | When Saved | Size Estimate |
|---|---|---|
| Session metadata (createdAt, updatedAt, status, attachmentFilenames) | On create, on every update | < 1 KB |
| Form values (full `Record<dataId, value>` map) | After each agent turn + debounced manual edits | ~10-20 KB |
| Conversation history (all messages with role, content, fieldUpdates) | After each agent turn | ~50-100 KB for a full session |

**Total per session: ~100-150 KB** — well under DynamoDB's 400 KB item limit.

Activity logs are NOT persisted. They are transient per-turn data (tool calls, thinking blocks) that can be regenerated and have no value on resume.

#### 4.5 DynamoDB Schema

Single-item-per-session design. One DynamoDB item holds all session state.

**Table: `compliance-assistant-sessions`**

| Attribute | Type | Description |
|---|---|---|
| `PK` | String | `SESSION#<uuid>` (partition key) |
| `SK` | String | `SESSION` (sort key, constant — single item per session) |
| `createdAt` | String | ISO 8601 timestamp |
| `updatedAt` | String | ISO 8601 timestamp |
| `status` | String | `active` or `completed` |
| `formValues` | Map | `{ "1234": "some text", "5678": true, ... }` |
| `conversationHistory` | List | `[{ role, content, fieldUpdates, attachmentFilenames, timestamp }, ...]` |
| `attachmentFilenames` | List | `["study_narrative.pdf", "consent_form.txt"]` |
| `ttl` | Number | Unix timestamp, 90 days from creation |

**Why single-item (not multi-item per session):**
- Simpler reads: one `GetItem` loads the entire session
- Simpler writes: one `PutItem` saves everything
- Our sessions are small (~100-150 KB) — no need to split across items
- No need for `Query` operations
- Trades write efficiency (full item replace) for read simplicity — acceptable at our scale

**On-demand billing.** Costs effectively $0 at low usage.

#### 4.6 API Changes

**New endpoints:**

```
POST   /api/sessions
  Request:  (empty body)
  Response: { "sessionId": "abc-123" }
  Creates a new session in DynamoDB. Returns the ID.

GET    /api/sessions/:id
  Response: {
    "sessionId": "abc-123",
    "status": "active",
    "formValues": { ... },
    "conversationHistory": [ { role, content, fieldUpdates, attachmentFilenames, timestamp }, ... ],
    "attachmentFilenames": ["study.pdf"],
    "createdAt": "...",
    "updatedAt": "..."
  }
  Loads a session. Returns 404 if not found or expired.

PATCH  /api/sessions/:id/form
  Request:  { "formValues": { "1234": "text", "5678": true } }
  Response: { "ok": true }
  Saves form values (called by frontend on debounced manual edits).
```

**Modified endpoint:**

```
POST   /api/chat
  Request (changed):  {
    "sessionId": "abc-123",        // NEW — required when deployed
    "message": "...",
    "conversationHistory": [...],
    "attachments": [...],
    "formValues": { ... }
  }
  Response: SSE stream (unchanged)

  After the stream completes, the backend persists the updated
  conversationHistory and formValues to DynamoDB.
```

When `sessionId` is absent (local dev without DynamoDB), the backend skips persistence — maintaining backward compatibility.

#### 4.7 Frontend Changes

**On mount (`App.tsx` or a new `useSession` hook):**
1. Parse `?session=` from URL
2. If not in URL, check `localStorage.getItem("compliance-assistant-session-id")`
3. If found: `GET /api/sessions/:id`
   - Success: hydrate `FormContext` values and `useChat` messages
   - 404 (expired/invalid): clear stored ID, create new session
4. If not found: `POST /api/sessions`, store returned ID in both localStorage and URL

**On chat send (`useChat.ts`):**
- Include `sessionId` in the chat request body
- No other change — backend handles persistence after the stream

**On form edit (`FormContext.tsx`):**
- Add a debounced save: when `values` changes, wait 2 seconds of inactivity, then `PATCH /api/sessions/:id/form`
- Only when `sessionId` is present (skip in local dev)

**On page load with existing session:**
- `FormProvider` accepts optional `initialValues` prop for hydration
- `useChat` accepts optional `initialMessages` for hydration

#### 4.8 Resume Flow (Detailed)

```
User opens https://d1234.cloudfront.net/?session=abc-123
  │
  ▼
Frontend: GET /api/sessions/abc-123
  │
  ▼
Backend: DynamoDB GetItem(PK=SESSION#abc-123, SK=SESSION)
  │
  ├─ Found → return { formValues, conversationHistory, ... }
  │    │
  │    ▼
  │  Frontend hydrates:
  │    - FormContext.setValues(formValues)
  │    - useChat.setMessages(conversationHistory)
  │    - Show attachment chips for attachmentFilenames
  │    - User sees their form partially filled, chat history intact
  │    - User continues working
  │
  └─ Not found (404) → Frontend clears localStorage, creates new session
```

### 5. CloudFront Routing

| Path Pattern | Origin | Behavior |
|---|---|---|
| `/api/*` | ALB | No caching, forward all headers, SSE buffering disabled |
| `/*` (default) | S3 | Cache static assets, SPA fallback for 403/404 |

### 6. IAM

**Fargate task role:**
- `bedrock:InvokeModel` on Claude and Titan Embed models
- `s3:GetObject` on the data bucket
- `dynamodb:GetItem`, `PutItem`, `UpdateItem` on the sessions table

**Fargate execution role (standard):**
- ECR image pull
- CloudWatch Logs

### 7. Docker Image

Minimal image. No data baked in — everything comes from S3 and DynamoDB at runtime.

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
COPY run.py .
RUN pip install gunicorn .
EXPOSE 5002
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5002", "--timeout", "300", "compliance_assistant_api.app:app"]
```

Environment variables set in task definition:
- `DATA_BUCKET` — S3 bucket name for data assets
- `DYNAMODB_TABLE` — DynamoDB table name
- `AWS_DEFAULT_REGION` — deployment region
- `AGENT_MODEL_ID` — Bedrock model ID (optional override)

---

## Prerequisites for Deployer

1. **AWS account** with Bedrock model access enabled:
   - `us.anthropic.claude-sonnet-4-6`
   - `amazon.titan-embed-text-v2:0`
2. **AWS CLI** configured with credentials
3. **Node.js 18+** and **Docker** running locally
4. **CDK bootstrapped**: `npx cdk bootstrap`

## Estimated Monthly Cost

| Service | Idle | Light Usage (10 sessions/day) |
|---|---|---|
| Fargate (1 task, always-on) | ~$15 | ~$15 |
| ALB | $16 | $18 |
| CloudFront | $0 | ~$1 |
| S3 | < $1 | < $1 |
| DynamoDB (on-demand) | $0 | < $1 |
| Bedrock | $0 | ~$5-15 (usage-based) |
| **Total** | **~$32** | **~$40-50** |

## Stack Structure

```
apps/infra/
├── bin/infra.ts                         # Stack instantiation
├── lib/
│   ├── compliance-assistant-stack.ts    # Main stack (phase 1)
│   ├── hello-stack.ts                   # Existing (legacy, opt-in)
│   └── parse-demo-stack.ts              # Existing (legacy, opt-in)
```

**Stack outputs:**
- `SiteUrl` — CloudFront URL (share with testers)
- `ApiUrl` — ALB URL (debugging)
- `DataBucketName` — S3 bucket for data assets
- `SessionsTableName` — DynamoDB table name

## Backend Code Changes Summary

| File | Change |
|---|---|
| `app.py` | S3 data loading, `/api/*` route aliases, session endpoints |
| `data/s3_loader.py` | New: downloads data assets from S3 at startup |
| `data/session_store.py` | New: DynamoDB CRUD for sessions |
| `models.py` | Add `session_id` to `ChatRequest`, new `SessionResponse` model |
| `Dockerfile` | New: container image for Fargate |
| `.dockerignore` | New: exclude dev files from image |

## Frontend Code Changes Summary

| File | Change |
|---|---|
| `hooks/useSession.ts` | New: session resolution, load, create, debounced save |
| `hooks/useChat.ts` | Include `sessionId` in chat requests |
| `FormContext.tsx` | Accept `initialValues` prop, debounced auto-save |
| `App.tsx` | Integrate `useSession` hook, hydrate state on load |
| `api.ts` | New functions: `createSession`, `loadSession`, `saveFormValues` |
| `types.ts` | Add `sessionId` to `ChatRequest` |

## Deployment

```bash
cd apps/infra
npx cdk deploy ComplianceAssistantStack
```

CDK will:
1. Build the React frontend (`npm run build` in `apps/compliance-assistant/`)
2. Build and push the Docker image to ECR
3. Create VPC, ALB, Fargate service, S3 buckets, DynamoDB table, CloudFront
4. Upload frontend to S3, upload data assets to S3
5. Output the CloudFront URL
