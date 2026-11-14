# RelayPoint — Hackathon Submission Description

### Project Name
**RelayPoint** — Automated Knowledge Handover Platform

### Elevator Pitch
RelayPoint reconstructs project history from GitHub commits, pull requests, and issues into structured, role-specific knowledge handover reports where every claim is cryptographically tied to immutable ground-truth evidence.

---

## 1. Problem Statement
When software engineers transition between teams or take over codebases, knowledge transfer is severely broken:
- **Context Fragmentation**: Critical institutional knowledge is scattered across hundreds of commit messages, pull request discussions, and closed issue threads.
- **Onboarding Friction**: Incoming engineers take weeks to answer fundamental questions: *"What was being worked on?", "Where did the previous maintainer stop?", "Why was this architectural decision made?", and "What are the immediate blockers?"*
- **Unreliable AI Summarization**: Standard LLM summaries frequently hallucinate non-existent files, confuse dates, and present fabricated facts without verification or source attribution.

---

## 2. Proposed Solution
RelayPoint provides an automated knowledge handover pipeline backed by deterministic evidence verification:
1. **GitHub Ingestion**: Synchronously pulls commits, issues, and pull requests via the GitHub REST API or local Git CLI.
2. **Deterministic Sanitization**: Removes passwords, API keys, Bearer tokens, and private keys using regex rules before storage or AI processing.
3. **Structured AI Synthesis**: Leverages Google Gemini models with native OpenAPI 3.0 response schemas to extract structured findings, continuation tasks, and technical debt.
4. **Deterministic Evidence Grounding**: Validates every AI claim against stored SHA-256 chunk hashes and temporal sequences. Hallucinated or invalid citations are flagged immediately.
5. **Dual-Perspective Handover Reports**:
   - **Developer View**: Tactical architecture notes, active workstreams, unfinished tasks, fragile modules, immediate roadmap, and an evidence appendix.
   - **Team Lead View**: Executive synthesis, computed project health status, strategic milestones, critical risks, and budget coverage accounting.
6. **Interactive Evidence Inspector**: An inspection drawer enabling developers and leads to click any citation and view the verbatim, sanitized Git excerpt alongside its cryptographic SHA-256 hash.

---

## 3. Technology Stack
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Lucide React
- **Backend API**: Python 3.12, FastAPI, Uvicorn, Pydantic v2, Pydantic-Settings
- **Database**: SQLite with WAL journal mode, foreign key cascades, and connection pooling
- **AI Integration**: Google Gemini API (`gemini-3.8-flash`) with structured JSON schema enforcement (`responseSchema`) and header-based authentication (`x-goog-api-key`)
- **Git Integration**: Standard-library GitHub REST client and native Git CLI analyzer
- **Verification Engine**: Deterministic Python SHA-256 integrity verifier

---

## 4. Key Differentiators & Innovation
1. **Zero Hallucination Tolerance**: Findings are strictly classified into `SOURCE_LINKED`, `NEEDS_HUMAN_REVIEW`, `INSUFFICIENT_EVIDENCE`, or `INVALID_REFERENCE`.
2. **Cryptographic Grounding**: Citations are not freeform text strings; they reference immutable SQLite source chunk records with SHA-256 checksums that can be re-verified at any time.
3. **Temporal Conflict Detection**: Automatically detects when a closed or superseded PR is erroneously cited as active work, tagging it for human review.
4. **Defensive Normalization**: Built with a resilient adapter layer that maps variations in Gemini JSON structures while rejecting malformed or unattributed data.
5. **Security by Default**: Strict localhost binding (`127.0.0.1`), origin-restricted CORS, `SecretStr` secret redaction, and deterministic sanitization.

---

## 5. Current Implementation Status

| Component | Status | Verification Detail |
| :--- | :--- | :--- |
| **Backend API & Data Layer** | **LOCALLY TEST VERIFIED** | 78 / 78 passing unit and integration tests |
| **Frontend SPA Architecture** | **LOCALLY TEST VERIFIED** | TypeScript check and Vite production build passed |
| **GitHub Ingestion Engine** | **LIVE VERIFIED** | Ingested 52 chunks from public `octocat/Hello-World` |
| **Evidence Verification & Reverification** | **LOCALLY TEST VERIFIED** | SHA-256 hash verification and temporal checks fully operational |
| **Handover Demonstration Workflow** | **DEMONSTRATION DATA VERIFIED** | Complete walkthrough verified using pre-seeded `octocat/Hello-World` dataset |
| **Live Upstream Gemini Generation** | **NOT LIVE VERIFIED** | Dispatched 2 live requests to `gemini-3.8-flash`; upstream Google API returned HTTP 503 (Service Unavailable / Overloaded) |

---

## 6. Disclosures & Known Limitations
- **Live Gemini Availability Disclosure**: Although the Gemini integration architecture, OpenAPI 3.0 response schemas, and normalization layer are fully implemented and verified offline (78 passing tests), live AI synthesis could not be completed during evaluation due to upstream Google Gemini API capacity limitations (HTTP 503). The platform relies on its verified demonstration dataset for live presentation.
- **Single-User Localhost Evaluation**: RelayPoint is intentionally built as a local evaluation tool for hackathons and peer review. It binds strictly to `127.0.0.1` and does not provide multi-tenant user authentication or RBAC. It should not be exposed to the public internet without an authentication proxy.
- **Context Budget Limits**: To operate reliably within token constraints, source ranking prioritizes active PRs and open issues over historical commits. Budget metrics are transparently displayed in the report header.
