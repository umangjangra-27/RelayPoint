# RelayPoint — System Architecture & Architectural Boundaries

## 1. System Overview

RelayPoint is an Automated Knowledge Handover Platform designed as a hackathon MVP. It ingests an authorized GitHub repository or local Git checkout, inspects project history, correlates unresolved issues and pull requests, reconstructs active context, isolates unfinished work, and synthesizes evidence-grounded handover reports for incoming developers and team leads.

```
+-----------------------------------------------------------------------------------+
|                                   USER INTERFACE                                  |
|   React 18 + Vite + Tailwind CSS + Lucide React                                   |
|   - Dashboard                       - Evidence Viewer (Grounding Inspection)      |
|   - Repository Connection Form      - Human Review & Decision Workflow            |
|   - Activity Feed & Timeline        - Role Views: Developer & Team Lead           |
+------------------------------------------+----------------------------------------+
                                           | HTTP / REST API (JSON)
                                           v
+-----------------------------------------------------------------------------------+
|                              BACKEND SERVICE (FastAPI)                            |
|                                                                                   |
|  [ Ingestion Layer ]                                                              |
|   - GitHub REST API / PyGithub Client   - Local Git Clone / History (GitPython)   |
|                                                                                   |
|  [ Sanitization & Safety Layer ]                                                  |
|   - Deterministic Secret Sanitizer (strips tokens, credentials, sensitive envs)   |
|                                                                                   |
|  [ Evidence & Analysis Layer ]                                                    |
|   - Activity & Context Correlator       - Unfinished Work Detector (PR/Issue/Git) |
|   - Deterministic Grounding Verifier    - Citations & Source Chunk Indexer        |
|                                                                                   |
|  [ Synthesis Engine ]                                                             |
|   - Google Gemini API (Structured Output via Pydantic v2 schemas)                 |
+------------------------------------------+----------------------------------------+
                                           | SQL
                                           v
+-----------------------------------------------------------------------------------+
|                              DATABASE LAYER (SQLite)                              |
|  - Repositories         - Source Chunks           - Evidence References           |
|  - Analysis Runs        - Handover Reports        - Review Decisions              |
+-----------------------------------------------------------------------------------+
```

---

## 2. Layer Responsibilities & Boundaries

### 2.1 Frontend Boundary (`/frontend`)
The frontend is a single-page application built with React 18, Vite, Tailwind CSS, and Lucide React. It is strictly responsible for presentation and user interaction:
- **Dashboard**: High-level status of connected repositories, ongoing/completed analysis runs, and recent handover summaries.
- **Repository Connection**: User interface for selecting/authorizing repositories and starting analysis jobs.
- **Project Activity**: Visual timeline of recent commits, merged PRs, and discussion threads.
- **Handover Report**: Formatted presentation of the generated handover document, categorized into executive summary, technical architecture, work-in-progress, blocker analysis, and onboarding tasks.
- **Evidence Viewer**: Side-by-side verification drawer showing exact commit diffs, issue comments, or source code chunks backing each claim in the handover report.
- **Human Review**: Workflow UI allowing incoming engineers and tech leads to accept, flag, or annotate claims.
- **Role Views**: Dedicated view toggles for **Developer** (deep dive into files, active branches, PR diffs, environment setup) and **Team Lead** (velocity, unresolved risks, blockers, roadmap alignment).

### 2.2 Backend Boundary (`/backend`)
The backend is a lightweight FastAPI service written in Python 3.12:
- **GitHub Ingestion (`app.integrations.github`)**: Authenticated fetching of repository metadata, commits, pull requests, issues, and discussions using standard library `urllib.request`.
- **Git History Processing (`app.services.git_analyzer`)**: Commit log traversal, branch detection, author metrics, and addition/deletion statistics via native `subprocess.run` (never `shell=True`).
- **Secret Sanitization (`app.utils.sanitizer`)**: High-priority safety boundary executing *before* any data reaches storage or AI synthesis. Regex-based scrubbing of API keys, bearer tokens, passwords, database URIs, private keys, and emails.
- **AI Synthesis (`app.integrations.gemini` & `app.services.analyzer`)**: Controlled prompting using the Google Gemini API with configurable model (`gemini-2.5-flash`), enforcing strict Pydantic v2 JSON schema adherence. Employs bounded context budgets (`MAX_CONTEXT_CHUNKS`, `MAX_PROMPT_CHARS`) and deterministic source priority ranking.
- **Deterministic Evidence Verification (`app.services.verifier`)**: Cryptographic and structural verification checking that every cited finding points to existing SQLite chunks with matching SHA-256 hashes and repository ownership. Detects temporal conflicts (e.g. closed/merged PRs cited as active tasks) and tags them `NEEDS_HUMAN_REVIEW`.
- **Handover Report Generation (`app.services.report_generator`)**: Assembling verified evidence and synthesis into persistent, dual-view handover reports (Developer View & Team Lead View) saved in `handover_reports` and `evidence_references`.

### 2.3 Database Boundary (SQLite)
A clean, embedded SQLite database accessed via Python's standard `sqlite3` driver / lightweight ORM models. Minimal schema footprint:
- **`repositories`**: Registered GitHub or local repositories (name, remote URL, default branch, synced timestamps).
- **`analysis_runs`**: Execution log of handover analysis jobs (status, started_at, completed_at, error_details, options).
- **`source_chunks`**: Sanitized code and documentation chunks extracted during analysis (file path, commit SHA, line start/end, content hash).
- **`evidence_references`**: Atomic evidence units (type: commit/issue/pr/file, external identifier, excerpt, verified status).
- **`handover_reports`**: Complete generated reports (summary markdown, structured JSON payload, target audience role, status).
- **`review_decisions`**: Human feedback entries (report_id, reviewer_id, item_key, decision: approved/flagged/edited, comments).

---

## 3. Security, Grounding & Safety Invariants

1. **Deterministic Secret Sanitization**: No raw commit diff or PR discussion is stored or transmitted to external AI endpoints without passing through the secret scrubbing pipeline.
2. **Zero In-Memory Model Footprint**: RelayPoint utilizes the Google Gemini API directly, eliminating the need to download large local model weights, run Ollama, or bundle heavy embedding models locally.
3. **Evidence Grounding & Verification Invariant**:
   - `SOURCE_LINKED`: Every claim must cross-reference a verified entry in `source_chunks` with matching cryptographic SHA-256 hash and repository ownership.
   - `INVALID_REFERENCE`: Findings citing hallucinated, cross-repository, or modified chunk IDs are tagged invalid.
   - `INSUFFICIENT_EVIDENCE`: Claims lacking citations are never promoted to verified status.
   - `NEEDS_HUMAN_REVIEW`: Discrepancies between claim category and underlying artifact state (e.g. claiming a merged PR is ongoing) trigger human review flags.
4. **Traceability vs Semantic Truth**: The deterministic verifier validates *traceability, integrity, and temporal consistency*, not absolute semantic truth. While hallucination risk is drastically minimized, automated verification cannot guarantee semantic correctness of every natural language sentence.
5. **Bounded Context & Honest Coverage**: Repository history packed into AI prompts is strictly bounded by `MAX_CONTEXT_CHUNKS` and `MAX_PROMPT_CHARS`. If history exceeds this budget, the system computes and surfaces a `CoverageSummary` indicating partial coverage rather than pretending the analysis is exhaustive.
6. **Untrusted Data Boundary**: Commits, PR bodies, and issues are treated strictly as untrusted third-party data. Prompt injection attempts inside repository text are neutralized via explicit system boundary instructions.
7. **Environment Isolation**: All credentials and tokens reside exclusively in local `.env` files (never checked into version control).
