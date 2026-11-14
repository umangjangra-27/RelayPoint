# RelayPoint — Friend Handover & Quickstart Guide

Welcome to **RelayPoint**! This document provides everything you need to get the project running locally, run the test suites, explore the demonstration handover report, and continue development.

---

## 1. What RelayPoint Does
RelayPoint connects to GitHub repositories, ingests commit history, pull requests, and issues, sanitizes secrets, and synthesizes structured, evidence-grounded handover reports tailored for incoming software developers and team leads.

Every finding is tied to an immutable source chunk with a cryptographic SHA-256 hash, preventing AI hallucinations.

---

## 2. Prerequisites
- **Operating System**: Windows 10/11, macOS, or Linux.
- **Python**: Python 3.12 (CPython 3.12.x). *Do not use Python 3.15 prereleases.*
- **Node.js**: Node.js 18+ or 20+ and `npm`.
- **Git**: Installed and available in your terminal PATH.

---

## 3. Clone and Setup Instructions

### Step 1: Clone the Repository
```bash
git clone <repository-url> RelayPoint
cd RelayPoint
```

---

### Step 2: Backend Setup (Python 3.12)

#### Windows (PowerShell):
```powershell
cd backend

# Create virtual environment with Python 3.12 (using uv or python)
uv venv .venv --python 3.12
# Or standard Python 3.12: py -3.12 -m venv .venv / python3.12 -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install backend dependencies (offline from cache if previously installed)
uv pip install fastapi uvicorn pydantic pydantic-settings
# Or standard pip: pip install fastapi uvicorn pydantic pydantic-settings

# Configure environment variables from template
cp .env.example .env
```

#### macOS / Linux (bash/zsh):
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic pydantic-settings
cp .env.example .env
```

---

### Step 3: Populate Demonstration Data
The repository includes a verified, pre-sanitized demonstration dataset (`octocat/Hello-World`) so you can explore the complete handover workflow without needing external network calls:

```powershell
# From the backend directory with virtual environment activated:
python scripts/seed_demo_data.py
```

This idempotently initializes `relaypoint.db` and populates:
- 1 Repository (`octocat/Hello-World`)
- 52 Ingested Source Chunks
- 5 Evidence References
- 1 Complete Handover Report with Developer and Team Lead views

---

### Step 4: Run Backend Tests
Verify that all 78 unit and integration tests pass:
```powershell
python -m unittest discover -v -s tests
```
*Expected: `Ran 78 tests in ~6s ... OK`.*

---

### Step 5: Start the Backend Server
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Test that the backend is responding:
- Health check: `http://127.0.0.1:8000/api/health`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`

---

### Step 6: Frontend Setup & Launch
Open a second terminal window and navigate to `frontend/`:

```powershell
# From the repository root in a second terminal:
cd frontend

# Install frontend dependencies
npm install

# Run TypeScript type check
npx tsc --noEmit

# Start the Vite development server
npm run dev
```

Open your browser to:
**`http://localhost:5173`**

All requests to `/api/*` are automatically proxied to the backend on port 8000.

---

## 4. How to Use the Demonstration Report

1. Open `http://localhost:5173`.
2. On the **Dashboard**, you will see `octocat/Hello-World` listed under **Connected Repositories** and the demonstration report under **Recent Handover Reports**.
3. Click **View** on the handover report:
   - Notice the **Demonstration Report** badge.
   - Switch between **Developer View** and **Team Lead View** using the toggle in the upper right.
   - Scroll through immediate tasks, active workstreams, and technical architecture notes.
4. Click on any cited evidence pill (e.g. `chunk_c175deb6427b46d3`):
   - The **Evidence Inspection Drawer** slides out.
   - Inspect the verbatim sanitized excerpt, author, issue number, and SHA-256 integrity hash.
5. Click **Re-verify Citations** in the top navigation bar to trigger live backend verification.

---

## 5. Security & Deployment Restrictions

> [!WARNING]
> **Localhost Only**  
> RelayPoint binds to `127.0.0.1` and does not provide multi-user authentication or role-based access control. It is built strictly for single-user local evaluation. **Do not bind to `0.0.0.0` or expose the backend directly to the public internet.**

- **Secret Safety**: Never commit `.env` or your SQLite database file (`relaypoint.db`). Both are excluded by `.gitignore`.
- **Pre-Ingestion Sanitization**: RelayPoint deterministically scrubs passwords, API keys, Bearer tokens, and private keys before storing source chunks.

---

## 6. Known Limitations to Be Aware Of
- **Live Gemini Availability**: During evaluation, Google's upstream Gemini 3.8 Flash API returned HTTP 503 (Service Unavailable / Overloaded). The application handles upstream failures cleanly without corrupting the database. If you configure a `GEMINI_API_KEY` in `backend/.env`, you can test live generation against another repository whenever Google's endpoint has capacity.
- **Context Budget**: To prevent token exhaustion, source ranking selects the most relevant active PRs and open issues up to `MAX_CONTEXT_CHUNKS=20`.

---

## 7. How to Continue Development

- **Add New Ingestion Sources**: See `backend/app/services/ingestion.py` and `app/integrations/github.py` to add GitLab, Bitbucket, or Jira providers.
- **Custom Analysis Prompts**: Prompt templates and response schemas live in `backend/app/schemas/analysis.py` and `app/services/analyzer.py`.
- **Custom UI Components**: Frontend pages are in `frontend/src/pages/`, and report views are in `frontend/src/components/reports/`.
- **Resetting the Database**: If you ever want a clean slate:
  ```powershell
  rm backend/relaypoint.db
  # Then restart the backend or run python scripts/seed_demo_data.py
  ```
