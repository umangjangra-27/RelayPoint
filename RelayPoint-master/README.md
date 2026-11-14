# RelayPoint — Automated Knowledge Handover Platform

> **Hackathon MVP** | Intelligent, evidence-grounded project handovers for incoming software engineers and team leads.

---

## 1. Project Overview

When software engineers join a project, change teams, or take over a codebase, the knowledge handover process is notoriously fragmented. Engineers spend days or weeks sifting through stale documentation, commit logs, abandoned branches, and unlinked pull requests to deduce the current state of unfinished work.

**RelayPoint** bridges this gap by connecting to an authorized GitHub repository or local Git checkout, systematically reconstructing project history, correlating work in progress, detecting blockers, and generating verifiable, evidence-grounded handover reports tailored for both developers and engineering leads.

---

## 2. Problem Being Solved

- **Knowledge Decay**: Institutional knowledge leaves with departing engineers, leaving commits and pull requests with ambiguous intent.
- **Context Fragmentation**: The true state of a project is scattered across git commit histories, pull request discussions, open issue trackers, and informal chat notes.
- **Unverified AI Summaries**: Generic AI summaries frequently hallucinate non-existent files, misattribute author intent, or invent context.
- **Onboarding Friction**: New team members spend excessive time answering: *"What was being worked on?", "Where did they stop?", "Why was this architectural decision made?", and "What are the immediate blockers?"*

---

## 3. Proposed Solution

RelayPoint provides an automated handover pipeline built on strict evidence verification:

1. **Ingest & Correlate**: Extracts git commit graphs, branch diffs, pull request conversations, and issue discussions.
2. **Deterministic Sanitization**: Scrubs all credentials, tokens, and secrets before any data storage or AI processing.
3. **Structured AI Synthesis**: Leverages the Google Gemini API with strict Pydantic v2 schemas to reconstruct narrative project context and identify unfinished work.
4. **Evidence Grounding**: Every synthesized claim is matched against concrete git diffs, commit SHAs, or PR numbers. Claims without verified backing are flagged.
5. **Tailored Role Views**:
   - **Developer View**: Actionable tasks, failing test traces, active branch diffs, setup guides, and source-level citations.
   - **Team Lead View**: High-level velocity, unresolved technical debt, risk hotspots, and roadmap continuity.
6. **Human Review**: Interactive interface to approve, amend, or question handover findings.

---

## 4. Technology Stack

- **Frontend**: React 18, Vite, Tailwind CSS, Lucide React
- **Backend API**: Python 3.12+, FastAPI, Uvicorn
- **Data Validation & Schemas**: Pydantic v2, Pydantic-Settings
- **Git Analysis**: GitPython, PyGithub (GitHub REST API)
- **AI Synthesis**: Google Gemini API (`google-genai` SDK)
- **Database**: SQLite (embedded, zero external daemon overhead)
- **Evidence Verification**: Deterministic Python validation engine

---

## 5. Planned Architecture

For a comprehensive architecture specification and layer boundaries, see [docs/architecture.md](docs/architecture.md).

```
RelayPoint/
├── frontend/             # React 18 + Vite SPA (Dashboard, Reports, Evidence Viewer)
├── backend/              # Python 3.12+ FastAPI application
│   ├── app/
│   │   ├── api/          # REST endpoints and routing
│   │   ├── core/         # Settings, database connection, security
│   │   ├── models/       # SQLite database persistence models
│   │   ├── schemas/      # Pydantic v2 request/response & domain schemas
│   │   ├── services/     # Git analysis, AI synthesis, evidence verifier
│   │   ├── integrations/ # GitHub API and Gemini API clients
│   │   └── utils/        # Sanitizer, text chunking, hashing utilities
│   ├── tests/            # Automated test suite (pytest)
│   └── requirements.txt  # Backend Python dependencies
├── docs/                 # Architectural specifications and design notes
├── .gitignore            # Git exclusion rules (credentials, caches, builds)
├── .env.example          # Template environment configuration
└── README.md             # Project documentation and roadmap
```

---

## 6. Backend Setup & Execution Guide

### Prerequisites
- **Python**: Python 3.12 (CPython 3.12.14). Do not use Python 3.15 prerelease.
- **Package Manager**: `uv` or `pip`.

### Virtual Environment Setup (Windows PowerShell)
Navigate to the `backend` directory and create the virtual environment using Python 3.12:
```powershell
cd backend
uv venv .venv --python 3.12
# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

### Dependency Installation (Minimal Foundation)
To respect local bandwidth constraints, install only the minimal foundational dependencies:
```powershell
uv pip install fastapi uvicorn pydantic pydantic-settings
```

### Environment Configuration
Copy `.env.example` to `.env` in the repository root or `backend/` directory:
```powershell
cp ..\.env.example .\.env
```

### Database Initialization Behavior
The SQLite database schema automatically and idempotently initializes on application startup via FastAPI lifespan events (`app.core.database.init_db`). It creates the following 6 core tables and indexes with foreign keys and WAL mode enabled:
- `repositories`
- `analysis_runs`
- `source_chunks`
- `evidence_references`
- `handover_reports`
- `review_decisions`

The database file defaults to `relaypoint.db` (strictly excluded by `.gitignore`).

### Starting the Backend Server
Run the FastAPI development server with Uvicorn:
```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Health Check Diagnostic Endpoint
Access the health probe to verify server and database connectivity:
```http
GET http://127.0.0.1:8000/api/health
```

Example response:
```json
{
  "status": "healthy",
  "app_name": "RelayPoint",
  "version": "0.1.0",
  "database": "connected"
}
```

*Note: The health probe returns high-level diagnostic status and never leaks system file paths, database connection strings, or environment secrets.*

### Running the Test Suite
Run the test suite using Python's built-in `unittest` runner (no extra testing packages required):
```powershell
python -m unittest discover -s tests -v
```

---

## 7. GitHub Integration & Ingestion Pipeline

### 7.1 Repository Connection & Token Configuration
RelayPoint connects to GitHub repositories via the GitHub REST API using Python's built-in `urllib.request`:
- **Public Repositories**: Can be connected without a token (subject to GitHub unauthenticated IP rate limits of 60 requests/hr).
- **Private Repositories**: Require a GitHub Personal Access Token (classic with `repo` scope, or fine-grained with Read-Only access to metadata, commits, issues, and pull requests).
- **Token Setup**: Add `GITHUB_TOKEN=ghp_...` in `.env`. Tokens are wrapped in Pydantic's `SecretStr` and are strictly excluded from logs, string formatting, and API responses.

### 7.2 Ingestion Controls & Safety Limits
Ingestion is strictly bounded to prevent memory exhaustion, rate limit exhaustion, and excessive bandwidth consumption:
- `MAX_COMMITS`: Maximum commit records retrieved (default: 50).
- `MAX_ISSUES`: Maximum issue records retrieved (default: 30).
- `MAX_PULL_REQUESTS`: Maximum pull request records retrieved (default: 30).
- `MAX_CONTENT_LENGTH`: Maximum characters preserved per source chunk (default: 8,000 characters).
- `GITHUB_REQUEST_TIMEOUT`: Network timeout for GitHub API queries (default: 15 seconds).
- `GIT_SUBPROCESS_TIMEOUT`: Execution timeout for local git inspection (default: 15 seconds).

### 7.3 Supported Data Sources
- **GitHub Commits**: Commit hash, author name, timestamp, commit subject and body, and URL.
- **GitHub Issues**: Issue number, title, body, state (open/closed), author, labels, and timestamps. Pull requests returned by GitHub's raw issues endpoint are filtered out automatically.
- **GitHub Pull Requests**: PR number, title, body, state, branches (head/base), author, merged timestamp, and reviews.
- **Local Git Inspection**: Native CLI analyzer for local repositories, computing branch lists, commit logs, and file churn statistics (`additions`, `deletions`, `files_changed`) without reading raw diff bodies.

### 7.4 Ingestion API Endpoints

#### Connect a Repository
```http
POST /api/repositories/connect
Content-Type: application/json

{
  "repository_url": "https://github.com/fastapi/fastapi",
  "name": "FastAPI"
}
```

#### List Connected Repositories
```http
GET /api/repositories
```

#### Retrieve Repository Metadata
```http
GET /api/repositories/{repository_id}
```

#### Trigger Ingestion
```http
POST /api/repositories/{repository_id}/ingest
```

Response:
```json
{
  "run_id": "run_0a1b2c3d4e5f6789",
  "repository_id": "repo_1234567890abcdef",
  "status": "completed",
  "chunks_created": 38,
  "duplicates_skipped": 0,
  "started_at": "2026-11-11T08:15:00Z",
  "completed_at": "2026-11-11T08:15:04Z"
}
```

#### Query Ingested Source Chunks (Paginated)
```http
GET /api/repositories/{repository_id}/sources?source_type=commit&limit=20&offset=0
```

#### Retrieve Activity Timeline
```http
GET /api/repositories/{repository_id}/activity?limit=30
```

### 7.5 Security Invariants & Limitations
- **Mandatory Pre-Persistence Sanitization**: All content received from GitHub or local Git is sanitized via `app.utils.sanitizer` *before* hashing and database insertion. Secrets (API tokens, passwords, bearer headers, private keys) are replaced with `[REDACTED]`.
- **Duplicate Prevention**: Source chunks enforce deterministic SHA-256 uniqueness `(repository_id, content_hash)`. Repeated ingestions skip existing items idempotently without ballooning database storage.
- **Untrusted Input Invariant**: All repository content, commit messages, issue descriptions, and PR discussions are treated strictly as untrusted data.
- **No Command Injection**: Local Git analysis invokes argument arrays directly through `subprocess.run` (never `shell=True`). Paths are validated against directory traversal and verified with `git rev-parse --is-inside-work-tree`.

---

## 8. AI Synthesis & Evidence Verification Engine

### 8.1 Gemini Configuration & Model Selection
RelayPoint connects to Google Gemini via a lightweight, standard-library `urllib.request` client (`app.integrations.gemini`):
- **Model Selection**: Configured centrally via `GEMINI_MODEL` (default: `gemini-2.5-flash`). Supported models can be toggled without code modifications.
- **API Key Configuration**: Add `GEMINI_API_KEY=AIzaSy...` in your `.env` file. Keys are wrapped in `SecretStr` and protected against log disclosure.
- **Graceful Degradation**: When `GEMINI_API_KEY` is omitted, the API returns a structured, actionable error (`HTTP 400`) instead of fabricating synthetic or hardcoded AI outputs.

### 8.2 Bounded Context Preparation
To maintain strict data budgets and low token overhead:
- **Priority Ranking**: Sanitized source chunks are ranked deterministically:
  1. Open pull requests & open issues (highest priority for unfinished work).
  2. Recent commits (active development momentum).
  3. Closed pull requests & issues (historical context).
- **Safety Limits**: Bounded by `MAX_CONTEXT_CHUNKS` (default: 40) and `MAX_PROMPT_CHARS` (default: 35,000 chars).
- **Coverage Summary**: When repository history exceeds prompt limits, RelayPoint calculates an honest `CoverageSummary` reporting `is_complete_coverage: false` and the exact percentage of history analyzed, rather than claiming exhaustive coverage.

### 8.3 Deterministic Evidence Verification
Every finding generated by the AI model is audited by the deterministic verification engine (`app.services.verifier`):
1. **Source Existence & Ownership**: Confirms every cited chunk ID exists in SQLite and belongs strictly to the target repository. Cross-repository citations are flagged.
2. **Cryptographic Integrity**: Recomputes SHA-256 hashes of underlying stored chunks to guarantee content has not been tampered with or modified.
3. **Temporal Conflict Detection**: Cross-references claims against underlying artifact states. If an item is cited as an active blocker but the underlying PR is merged or issue is closed, the finding is tagged `temporal_conflict_detected = true` and flagged for review.
4. **Verification Statuses**:
   - `SOURCE_LINKED`: Citations verified and traceable to ground-truth repository chunks.
   - `INVALID_REFERENCE`: Model cited a non-existent or cross-repository chunk ID.
   - `INSUFFICIENT_EVIDENCE`: Finding lacked supporting citation links.
   - `NEEDS_HUMAN_REVIEW`: Temporal conflict or ambiguity detected between claim and source state.

*Important Note*: Verification guarantees **traceability, citation integrity, and temporal consistency**, not absolute semantic truth.

### 8.4 Role-Tailored Handover Views
Synthesized findings are formatted into two distinct view payloads within each report:
- **Developer View**: Deep architectural decisions, active code workstreams, unfinished implementation tasks, fragile file hotspots, immediate onboarding steps, and an **Evidence Appendix** providing full commit hashes, source URLs, and chunk previews.
- **Team Lead View**: Executive summary, computed project health status, major milestones, critical blockers and technical risks, strategic roadmap priorities, coverage metrics, and open uncertainties.

### 8.5 Analysis & Reports API Endpoints

#### Trigger Analysis and Report Generation
```http
POST /api/repositories/{repository_id}/analyze
```

Response:
```json
{
  "report_id": "rep_1a2b3c4d5e6f7890",
  "title": "Knowledge Handover: org/test-app (2026-11-11)",
  "repository_id": "repo_1234567890abcdef",
  "analysis_run_id": "run_9876543210fedcba",
  "verification_stats": {
    "SOURCE_LINKED": 8,
    "INVALID_REFERENCE": 0,
    "INSUFFICIENT_EVIDENCE": 1,
    "NEEDS_HUMAN_REVIEW": 1
  },
  "created_at": "2026-11-11T08:30:00Z"
}
```

#### List Reports for a Repository
```http
GET /api/repositories/{repository_id}/reports
```

#### Retrieve Full Report
```http
GET /api/reports/{report_id}
```

#### Re-verify Report Evidence
```http
POST /api/reports/{report_id}/verify
```

#### Retrieve Single Source Chunk
```http
GET /api/repositories/{repository_id}/sources/{source_id}
```

Response:
```json
{
  "id": "src_1a2b3c4d5e6f7890",
  "repository_id": "repo_1234567890abcdef",
  "source_type": "commit",
  "external_id": "c1a2b3c4",
  "title": "feat(auth): add token revocation",
  "content": "commit c1a2b3c4...\nAuthor: Dev\n\nfeat(auth): add token revocation",
  "author": "dev@example.com",
  "timestamp": "2026-11-10T12:00:00Z",
  "commit_hash": "c1a2b3c4d5e6f7890",
  "content_hash": "a1b2c3d4e5f6...",
  "metadata": {}
}
```

---

## 9. Frontend Setup & Execution Guide

### Prerequisites
- **Node.js**: Node.js 18+ (tested on Node v22.18.0)
- **Package Manager**: `npm`

### Installation & Development Workflow
Navigate to the `frontend` directory:
```powershell
cd frontend
npm install --prefer-offline
```

Start the Vite development server:
```powershell
npm run dev
```
The application will launch at `http://127.0.0.1:5173`.
All `/api/*` network requests are automatically reverse-proxied to the FastAPI backend running at `http://127.0.0.1:8000`.

### Production Build & Verification
```powershell
npm run build
```
This runs `tsc` for complete strict type safety followed by `vite build` into `frontend/dist/`.

---

## 10. Security Architecture & Operating Model

> [!IMPORTANT]
> **Local Development & Demo MVP Model**: RelayPoint is currently an engineering prototype designed for local development, hackathon demonstration, and internal team evaluations.
> - **No User Authentication**: There is currently no multi-tenant authentication or session access control system implemented.
> - **Strict Localhost Binding**: The application server defaults to binding exclusively on `127.0.0.1` (`APP_HOST=127.0.0.1`). **Never** configure `APP_HOST=0.0.0.0` or expose the service directly to public untrusted networks without an authenticating reverse proxy.
> - **API Key Safety**: Google Gemini API keys are transmitted to Google's endpoints via the official `x-goog-api-key` HTTP request header rather than URL query parameters to prevent leakage in proxy logs or error URLs.
> - **Credential Sanitization Disclaimer**: Regex pattern sanitization is a heuristic defense-in-depth layer. While it deterministically scrubs common high-entropy API tokens (GitHub, OpenAI, Google, AWS, Slack, Private Keys, DB URIs, and emails), regex matching cannot theoretically guarantee detection of all bespoke or obfuscated secrets or arbitrary PII.

---

## 11. Friend Handover & Quickstart Guide

This section is written specifically so a teammate or peer can clone and run RelayPoint on their local Windows computer from scratch with zero confusion.

### Prerequisites
1. **Python**: Python 3.12 (CPython 3.12.x). *Do not use Python 3.15 prerelease due to binary wheel incompatibilities.*
2. **Node.js**: Node.js 18+ and `npm` (tested on Node v22).
3. **Git**: Installed and available in PowerShell (`git --version`).
4. **Internet Connection**: Required for GitHub REST API calls and Google Gemini API synthesis.

### Step-by-Step Setup Instructions (PowerShell)

#### 1. Clone the Repository
```powershell
git clone <repository_url> RelayPoint
cd RelayPoint
```

#### 2. Set Up the Backend
```powershell
cd backend
# Create Python 3.12 virtual environment (using uv or standard python)
uv venv .venv --python 3.12
# Or: py -3.12 -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
uv pip install -r requirements.txt
# Or: pip install -r requirements.txt
```

#### 3. Configure Environment Variables
Copy `.env.example` from the project root into `backend/.env`:
```powershell
cp ..\.env.example .\.env
```
Open `backend/.env` and configure:
- `GEMINI_API_KEY`: *(Optional but recommended)* Your Gemini API key from [Google AI Studio](https://aistudio.google.com/).
- `GITHUB_TOKEN`: *(Optional)* A GitHub Personal Access Token to raise GitHub API rate limits from 60 req/hr to 5,000 req/hr.

#### 4. Run the Backend Test Suite
Verify that all 78 unit and integration tests pass locally:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -v -s tests
```

#### 5. Start the Backend API Server
```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Verify backend health in a separate PowerShell window:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health"
```
Interactive Swagger API documentation is available at `http://127.0.0.1:8000/docs`.

#### 6. Set Up and Launch the Frontend
In a new PowerShell window, navigate to `frontend/`:
```powershell
cd RelayPoint\frontend
npm install
npm run dev
```
Open your browser to `http://localhost:5173`.
All requests to `/api` are automatically proxied to the backend on `http://127.0.0.1:8000`.

### Known Security & Operational Limitations

> [!WARNING]
> **Localhost-Only Demonstration Platform**  
> RelayPoint is designed as a single-user evaluation and demonstration system for hackathons and local review. It binds strictly to `127.0.0.1` and does **not** include user authentication or role-based access control (RBAC). **Do not expose this application directly to the public internet or bind it to `0.0.0.0`.**

> [!NOTE]
> **Gemini API Integration & Demonstration Data Disclosure**  
> - **Integration Architecture**: The backend includes full Google Gemini integration (`gemini-3.8-flash`) utilizing OpenAPI 3.0 structured output response schemas (`get_gemini_analysis_schema()`), header authentication (`x-goog-api-key`), and a deterministic normalization layer (`normalize_gemini_analysis_response()`). All 78 tests pass completely offline.
> - **Live Availability Status**: During final live evaluation, Google's upstream Gemini endpoint returned consecutive HTTP 503 (Service Unavailable / Overloaded) errors. Live AI synthesis is therefore **NOT LIVE VERIFIED**.
> - **Demonstration Fixture**: The platform includes a pre-seeded, verified demonstration handover report (`rep_f34ab9bca2904063`) for `octocat/Hello-World` with 5 verified findings, full Developer/Team Lead views, and live SHA-256 evidence linking. This report is clearly labeled in the user interface as demonstration data.

### Resetting the Local SQLite Database
The SQLite database file is stored locally at `backend/relaypoint.db` (and excluded by `.gitignore`).
To reset your local database to a clean slate at any time:
1. Stop the backend server (`Ctrl + C`).
2. Delete the database file:
   ```powershell
   Remove-Item .\backend\relaypoint.db -Force -ErrorAction SilentlyContinue
   ```
3. Restart the backend server. The schema and tables will automatically re-initialize on startup.

---

## 12. Troubleshooting Guide

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **Python 3.15 wheel build failures** | System has Python 3.15 prerelease in PATH. | Use Python 3.12 explicitly: `uv venv .venv --python 3.12` or `py -3.12 -m venv .venv`. |
| **Port 8000 or 5173 already in use** | A dangling process is holding the port. | In PowerShell run: `Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess \| Stop-Process -Force` |
| **GitHub HTTP 403 Rate Limit** | Exceeded GitHub's 60 req/hr unauthenticated limit. | Generate a classic personal access token on GitHub (read-only) and add `GITHUB_TOKEN=ghp_...` to `.env`. |
| **Gemini missing API key dialog** | `GEMINI_API_KEY` is not present in `.env`. | Add `GEMINI_API_KEY=AIza...` to your `backend/.env` file and restart the backend. |
| **CORS errors in browser console** | Frontend accessing an unexpected origin. | Ensure frontend is accessed via `http://localhost:5173` or `http://127.0.0.1:5173`, which are whitelisted in `config.py`. |
| **Vite proxy error (ECONNREFUSED)** | Backend is not running on port 8000. | Start the FastAPI server before launching the Vite frontend. |

---

## 13. Development Roadmap

- [x] **Prompt 01: Project Foundation & Environment Inspection**
  - Environment reconnaissance and version verification
  - Clean project scaffolding and directory structure
  - Architectural boundary definitions (`docs/architecture.md`)
  - Low-bandwidth constraint controls and strict `.gitignore`
  - Safe `.env.example` template with zero hardcoded credentials
- [x] **Prompt 02: Backend Core Configuration, SQLite & Security**
  - Python 3.12 virtual environment setup with `uv` (`backend/.venv`)
  - Pydantic Settings configuration with `SecretStr` redaction (`app.core.config`)
  - Direct SQLite database layer with WAL mode, foreign key cascades, and transaction manager (`app.core.database`)
  - Idempotent schema initialization for 6 core tables and indexes
  - Deterministic regex secret sanitization engine (`app.utils.sanitizer`)
  - Minimal FastAPI application with `/api/health` and safe error envelopes (`app.main`)
  - Comprehensive unit test suite (21 unit tests passing via `unittest`)
- [x] **Prompt 03: GitHub Integration and Project History Ingestion**
  - Standard library `urllib.request` GitHub REST API client (`app.integrations.github`)
  - Local Git analysis engine using `subprocess` without `shell=True` (`app.services.git_analyzer`)
  - Ingestion coordinator with secret sanitization and duplicate detection (`app.services.ingestion`)
  - Repository management and activity timeline API endpoints (`app.api.repositories`)
  - Centralized, configurable safety limits (commits, issues, PRs, content length, timeouts)
  - 37 unit tests passing across all components with 0 external network dependencies
- [x] **Prompt 04: AI Synthesis and Evidence Verification Engine**
  - Lightweight Google Gemini REST API client (`app.integrations.gemini`) with JSON schema enforcement
  - Bounded context preparation and deterministic source relevance ranking (`app.services.analyzer`)
  - Comprehensive Pydantic v2 domain schemas for structured findings (`app.schemas.analysis`)
  - Deterministic evidence verification and temporal conflict detection engine (`app.services.verifier`)
  - Dual-role handover report generator (`app.services.report_generator`) with Developer & Team Lead views
  - Complete analysis and report management API endpoints (`app.api.analysis`)
  - 57 unit tests passing across entire backend with 0 mock leaks or real API calls
- [x] **Prompt 05: Frontend Dashboard & Handover Report Viewer**
  - React 18 + Vite + TypeScript + Tailwind CSS production architecture
  - Strict type contracts mirroring backend Pydantic v2 schemas (`frontend/src/types/api.ts`)
  - Centralized API client (`frontend/src/services/api.ts`) with timeout handling and error envelopes
  - SaaS application shell: TopNav with live backend connectivity status, collapsible Sidebar, and responsive layout
  - Repository Management: Connect GitHub Modal, repository directory, and deep-dive repository view
  - Real-Time Action Triggers: Ingestion trigger with busy states and AI handover synthesis trigger
  - Dual-Role Report Viewer: Instant toggle between Developer View and Team Lead View
  - Developer View: Technical architecture, active workstreams, unfinished tasks, fragile modules, immediate roadmap, and full Evidence Appendix
  - Team Lead View: Executive summary, computed project health status, key milestones, critical risks, strategic roadmap, coverage overview, and known uncertainties
  - Interactive Evidence Inspector Drawer: Slides out on citation click, displays cryptographic SHA-256 integrity hash, author, timestamp, sanitized excerpt, audit notes, copy buttons, and GitHub links
  - Re-verify Citations button: Triggers live backend verification and updates verification badges
- [x] **Prompt 07: Secure Gemini API Configuration**
  - Inspected backend configuration, `.env.example`, `.gitignore`, and settings
  - Confirmed `GEMINI_API_KEY` environment mapping with `SecretStr` redaction
  - Configured secure template without exposing secrets in logs or git history
- [x] **Prompt 08: Gemini API Diagnostics, Normalization & Release Stabilization**
  - **P08.1**: Diagnosed model availability; handled Gemini 2.5 vs 3.x tier differences
  - **P08.2**: Transitioned default configuration to `gemini-3.8-flash`
  - **P08.3**: Evaluated live synthesis latency and bounded context ranking (20 chunks, 6,733 chars)
  - **P08.4 / P08.4.1**: Implemented OpenAPI 3.0 `responseSchema` and robust `normalize_gemini_analysis_response()` normalizer; expanded test suite to 78 passing unit/integration tests
  - **P08.5 / P08.5.1**: Handled upstream Google HTTP 503 Service Unavailable gracefully with zero retries, zero orphaned records, and clean database fail-safe state
  - **P08.6**: Final release audit; corrected `.gitignore` rule for frontend report components, labeled demonstration data transparently, and finalized friend handover documentation
