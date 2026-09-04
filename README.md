# Personal Job Outreach Agent

A production-oriented job search command center for discovering opportunities, tracking applications, preparing human-approved Gmail outreach, syncing replies, and managing follow-ups.

This project is built as a personal automation system, not a bulk email tool. LinkedIn and Indeed are handled through manual-safe URL and description imports. Gmail sending is gated by human approval, live sending is disabled by default, LLM usage is routed through LiteLLM with budget caps, and every important workflow action is recorded in an audit trail.

Live App: https://personal-outreach-agent-21647215439.us-central1.run.app/ 

## 🎥 Project Demo

[▶ Watch the 3-minute demo](https://www.youtube.com/watch?v=0ugqV4Pgr5k)

The demo covers:
- Multi-source job discovery
- Opportunity tracking and fit analysis
- Gemini-powered outreach generation
- Human approval workflow
- Gmail OAuth integration
- Reply/follow-up tracking
- Cloud deployment on GCP
## What It Does

- Discovers early-career tech opportunities from public job feeds, saved career-page sources, and manual imports.
- Supports manual-safe LinkedIn and Indeed trackers for pasted job URLs, descriptions, recruiter links, and notes.
- Scores opportunities against target roles, Canadian/remote locations, skills, contact availability, and role fit.
- Researches companies and stores source links, summaries, tech stack clues, and contact-search context.
- Finds public contact options when available, including careers inboxes, contact pages, public emails, and recruiter/profile links.
- Generates recent-graduate-friendly outreach drafts using Gemini through LiteLLM, with deterministic fallback drafts if the LLM is unavailable.
- Requires review, edit, and approval before any message can be sent.
- Sends through Gmail only when a real recipient exists and live sending is explicitly enabled.
- Syncs Gmail replies, matches them to sent outreach, classifies intent, and prepares follow-up work.
- Tracks applications separately from outreach so job applications without public emails still stay visible.

## Pipeline

```text
DISCOVERED
  -> ANALYZED
  -> COMPANY_RESEARCHED
  -> CONTACT_FOUND
  -> DRAFTED
  -> PENDING_APPROVAL
  -> APPROVED
  -> SENT
  -> REPLIED
  -> FOLLOW_UP_DUE
```

The dashboard is organized around this lifecycle:

- Dashboard: real workflow summary, safety status, action queue, and audit preview
- Job Discovery: public job-feed search, saved career sources, and one-off career-page scans
- LinkedIn Tracker: manual LinkedIn URL/description tracking with no scraping or auto-messaging
- Indeed Tracker: manual Indeed URL/description/CSV import with no scraping
- Opportunities: pipeline table and per-opportunity actions
- Applications: saved/applied/interview/rejected/follow-up-needed tracking
- Company Research: company and role context
- Contact Finder: public contact discovery and manual contact confirmation
- Drafts / Approval Queue: human review before send
- Gmail Outreach: needs recipient, ready to send, sent, reply waiting, follow-up due
- Replies: Gmail reply sync and LLM classification
- Follow-ups: follow-up draft generation after no reply
- Settings: connected Gmail accounts, profile preferences, and readiness
- Audit Logs: traceability for imports, analysis, drafts, approvals, sends, and reply classification

## Source Safety

The app intentionally does not scrape LinkedIn, does not automate LinkedIn messaging, and does not scrape Indeed. Those tabs are designed for user-provided job URLs, descriptions, recruiter links, and notes.

Supported discovery approaches:

- Remotive and RemoteOK public job feeds
- Optional Adzuna Canada API integration
- Public company career pages
- Greenhouse, Lever, and Ashby public job-board URLs
- Manual LinkedIn, Indeed, and Glassdoor URL tracking
- CSV imports

Future job sources should be added through the source adapter boundary using official APIs, partner feeds, exports, or user-pasted data.

## Architecture

```text
Dashboard
  -> FastAPI API
    -> PostgreSQL state and audit log
    -> Source adapters and job discovery services
    -> Company research and contact finder services
    -> LiteLLM gateway for Gemini-backed AI tasks
    -> Gmail OAuth send and reply sync
```

Key backend modules:

- `backend/app/services/job_source_discovery.py`: public job-feed discovery and source adapter boundary
- `backend/app/services/pipeline_service.py`: pipeline orchestration, applications, drafts, sends, replies, follow-ups, and audit events
- `backend/app/services/contact_finder.py`: public contact-source detection and confidence scoring
- `backend/app/services/ai_draft_service.py`: first-touch and follow-up drafting with fallback behavior
- `backend/app/services/gmail_account_service.py`: connected Gmail account storage and token encryption
- `backend/app/agents/email_sender.py`: Gmail send and dry-run delivery
- `backend/app/agents/email_inbox.py`: Gmail reply fetching
- `backend/app/agents/reply_classifier.py`: reply intent classification

## Safety Defaults

- `APP_AUTH_ENABLED=false` locally, but should be `true` on Cloud Run.
- `APP_SIGNUP_ENABLED=false` except during first-user setup.
- `EMAIL_SENDING_ENABLED=false` by default.
- Human approval is required before send.
- Approved drafts still need a real recipient email before Gmail can send.
- LinkedIn remains manual-only.
- Gmail refresh tokens are encrypted when `GMAIL_TOKEN_ENCRYPTION_KEY` is configured.
- LLM calls are limited by per-run caps and LiteLLM budget caps.
- Secrets belong in `.env` locally and Secret Manager or Cloud Run secrets in production.

## Local Setup

```powershell
cd personal-job-outreach-agent
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
docker compose up -d postgres redis litellm
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001
```

In another terminal:

```powershell
cd personal-job-outreach-agent
.\.venv\Scripts\python.exe -m http.server 3000 --directory dashboard --bind 127.0.0.1
```

Open:

- Dashboard: `http://localhost:3000`
- API docs: `http://localhost:8001/docs`
- Readiness: `http://localhost:8001/api/v1/system/readiness`
- LiteLLM proxy: `http://localhost:4000`

The Cloud Run build serves the dashboard and API from one service, so the separate static server is only needed for local frontend development.

## Environment

Copy `.env.example` to `.env` and fill only local values:

```powershell
Copy-Item .env.example .env
```

Important values:

```text
DATABASE_URL=postgresql+asyncpg://...
AUTOMATION_API_KEY=<random-local-token>
APP_AUTH_ENABLED=false
APP_AUTH_SECRET_KEY=<random-session-secret>
APP_SIGNUP_ENABLED=false
APP_ALLOWED_EMAIL=<your-login-email>

LLM_PROVIDER=gemini
LLM_API_KEY=<your-gemini-api-key>
PRIMARY_MODEL=gemini-flash
FAST_MODEL=gemini-flash-lite
AI_DRAFTING_ENABLED=true
MONTHLY_LLM_BUDGET_CAD=20
MONTHLY_LLM_BUDGET_USD=14

GOOGLE_CLIENT_ID=<oauth-client-id>
GOOGLE_CLIENT_SECRET=<oauth-client-secret>
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8001/auth/google/callback
GMAIL_TOKEN_ENCRYPTION_KEY=<fernet-or-long-random-secret>

EMAIL_SENDING_ENABLED=false
EMAIL_REPLY_SYNC_ENABLED=true
```

Runtime caps:

```text
MAX_JOBS_PER_SOURCE=10
MAX_JOBS_PER_SEARCH_RUN=30
MAX_AI_DRAFTS_PER_RUN=5
MAX_FOLLOWUPS_PER_RUN=5
MAX_PIPELINE_BATCH_SIZE=10
```

## Gmail OAuth

1. Create or select a Google Cloud project.
2. Enable the Gmail API.
3. Configure OAuth consent for external testing and add your Gmail as a test user.
4. Create a web OAuth client.
5. Add local redirect URI: `http://localhost:8001/auth/google/callback`.
6. Add Cloud Run redirect URI after deploy: `https://YOUR-CLOUD-RUN-URL/auth/google/callback`.
7. Start the backend and open `/auth/google/start`.
8. Select the Gmail account you want to use for job outreach and reply sync.

The Gemini billing account and Gmail sender account do not need to be the same Google account.

## LLM Gateway

AI tasks are routed through LiteLLM so the app can use one provider API key and switch model aliases without changing application code.

Default Gemini routing:

- `gemini-flash-lite`: fit scoring, contact extraction, reply classification, and small structured tasks
- `gemini-flash`: company research, outreach drafts, and follow-up drafts

LiteLLM enforces the gateway budget. The app also enforces server-side per-run limits so scheduled jobs and direct API calls stay bounded.

## Cloud Run Deployment

The project includes:

- `Dockerfile.cloudrun`: one image for FastAPI plus static dashboard assets
- `cloudbuild.yaml`: build and push to Artifact Registry
- `.gcloudignore`: excludes local-only files from build context
- Cloud SQL-compatible `DATABASE_URL`
- Google OAuth callback support for deployed URLs

Production checklist:

- Enable `APP_AUTH_ENABLED=true`.
- Temporarily enable `APP_SIGNUP_ENABLED=true` only for first-user setup.
- Disable signup after the first account is created.
- Store secrets in Secret Manager or Cloud Run secrets.
- Use Cloud SQL PostgreSQL or another managed PostgreSQL database.
- Add the deployed OAuth callback URL to the Google OAuth client.
- Keep `EMAIL_SENDING_ENABLED=false` until dry-run and approval behavior is verified.
- Keep LLM and discovery caps low.

Example build:

```powershell
gcloud artifacts repositories create personal-outreach --repository-format=docker --location=us-central1
gcloud builds submit --config cloudbuild.yaml
```

Deploy with production environment variables and secrets attached through Cloud Run.

## Validation

```powershell
.\.venv\Scripts\python.exe -m ruff check backend\app
.\.venv\Scripts\python.exe -m pytest backend\tests -q
node --check dashboard\app.js
docker compose config --quiet
```

Do not run the full database test suite against a populated personal development database unless you are comfortable with test database resets.

## Roadmap

- Add login/session hardening for multi-user deployment.
- Add Cloud Scheduler jobs for safe batch discovery, reply sync, and follow-up generation.
- Add official job-source adapters where supported.
- Improve company/contact research with richer public-source attribution.
- Add exportable interview demo data without mixing it with live personal data.
