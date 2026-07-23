# Personal Job Outreach Agent

A personal job search command center for opportunity discovery, application tracking, recruiter/contact research, human-approved Gmail outreach, replies, and follow-ups.

The product keeps automation useful without making it reckless: contacts are tracked in a pipeline, AI drafts are quality-checked, every message requires human approval, Gmail sending is disabled by default, replies are synced and classified, and every important action is written to an audit trail.

## Product Capabilities

- Contact and opportunity pipeline for recruiters, hiring managers, founders, alumni, referrals, and target companies
- Manual contact creation, CSV import, and job discovery import
- Career-page discovery from public company/job-board URLs, including Greenhouse, Lever, and Ashby public boards
- Automated latest-job search from public job feeds such as Remotive and RemoteOK, plus optional Adzuna Canada search with API keys
- Production-safe LinkedIn and Indeed tracker tabs for manual URL/description/CSV imports without scraping
- Fit scoring from target roles, target locations, skills, contact availability, and role research notes
- Company research and contact finder agents for each discovered opportunity
- AI-assisted first-touch and follow-up drafting through LiteLLM
- Deterministic QA checks before a draft reaches the approval queue
- Human approval and edit workflow before any email can be sent
- Gmail OAuth setup for live send and reply sync
- Reply classification into interested, interview, resume requested, not interested, out of office, bounce, unclear, neutral, and unsubscribe
- Scheduled automation (Cloud Scheduler) for pipeline advancement, draft queues, reply sync, and follow-up queues
- PostgreSQL-backed state and audit history for portfolio-grade traceability

## Target Workflow

1. Enter target roles and locations, such as junior AI engineer, backend developer, software developer, Vancouver, Alberta, Saskatchewan, or remote Canada.
2. Discover opportunities from job boards, company career pages, URLs, or CSV imports.
3. Research each company and role with summaries, tech stack clues, role fit, and source links.
4. Find public contacts such as recruiter emails, HR inboxes, careers inboxes, LinkedIn profile links, or contact-page links.
5. Score each opportunity based on skills, location, role level, tech stack, and outreach readiness.
6. Generate a personalized outreach draft from the job, company, contact, and profile context.
7. Review, edit, approve, or reject every draft in the dashboard.
8. Send through Gmail only after approval and only when live sending is explicitly enabled.
9. Sync Gmail replies and match them back to sent outreach.
10. Classify replies as interested, interview, resume requested, not interested, out of office, bounce, unclear, or neutral.
11. Generate a follow-up draft if no reply arrives after the configured waiting period.
12. Track the pipeline from discovered to contact found, drafted, approved, sent, replied, follow-up due, or closed.

## Current Working Scope

- Manual company/job/contact entry
- CSV import
- Career-page and job-board URL discovery
- Automated latest-job search by target roles, locations, and skills
- LinkedIn Tracker: manual LinkedIn job URL import, recruiter profile URL tracking, pasted descriptions, fit scoring, LinkedIn connection message generation, and Gmail draft generation
- Indeed Tracker: manual Indeed URL import, pasted job descriptions, CSV import, fit scoring, company research, and Gmail draft generation
- Job discovery importer for job postings, company research, tech stack notes, contact links, and opportunity scoring
- Public contact finder for careers/recruiting emails, contact pages, company profile links, and source URL fallback
- Delete controls for local pipeline cleanup
- Opportunity pipeline states
- AI/fallback draft generation
- Human approval
- Gmail OAuth
- Gmail dry-run/live-send switch
- Reply classification endpoint
- Follow-up queue generation

## Next Automation Integrations

- Job discovery source: Indeed, ZipRecruiter, company career pages, Greenhouse/Lever pages, or imported CSV exports.
- Company research source: public websites, career pages, job descriptions, and company insight providers.
- Contact discovery source: public careers inboxes, recruiter profile links, company contact pages, and manually confirmed emails.
- Profile memory: resume, project summaries, skills, locations, and preferred roles used by the scoring and drafting agents.

## Import Sources

- **Automated Job Search** queries configured job feeds directly, filters for Canada/remote Canada IT roles, scores the matches, and imports them into the pipeline.
- **Create Contact** adds one company, job, recruiter, hiring manager, or team manually.
- **Discover From Career Pages** fetches public source URLs, uses supported public job-board APIs for Greenhouse, Lever, and Ashby, falls back to HTML extraction for ordinary career pages, detects public contact emails where available, and imports matches into the pipeline.
- **Import CSV Contacts** imports rows from the text box in the dashboard. This is local CSV parsing only.
- **Job Discovery Importer** imports job rows, keeps research context, scores fit, and places each opportunity in `Opportunity Discovered` or `Contact Found`.

LinkedIn and Indeed are intentionally not scraped. The tracker tabs use only user-pasted URLs, descriptions, recruiter/profile URLs, CSV rows, and notes. LinkedIn messages are generated for manual use only; the app does not send or automate LinkedIn messaging.

Indeed, Glassdoor, and Canada Job Bank live-source adapters should be added only through approved provider access, partner APIs, official feeds, exports, or pasted job/company URLs.

## Agent Layer

- `JobSearchDiscoveryService`: live job feed discovery for Remotive, RemoteOK, optional Adzuna, and explicit gated adapters for Indeed, Glassdoor, and Job Bank.
- `SourceAdapter`: production-safe source adapter boundary for LinkedIn and Indeed manual trackers, with future official API adapters able to normalize into the same opportunity model.
- `CompanyResearchAgent`: turns the posting, company, source URL, location, tech stack, and fit context into research notes.
- `ContactFinderAgent`: searches public job/company/careers/contact pages for public emails, contact URLs, and profile links with confidence scoring.
- `AIDraftService`: generates personalized first-touch and follow-up drafts through LiteLLM with fallback drafting.
- `DraftQAAgent`: blocks risky or incomplete drafts before approval.
- `EmailSenderAgent`: sends only approved drafts, with dry-run as the default.
- `EmailInboxAgent`: fetches recent Gmail replies when reply sync is enabled.
- `ReplyClassifierAgent`: classifies replies into interested, interview, resume requested, not interested, out of office, bounce, unclear, or neutral.

## Cloud Run Deployment

The root `Dockerfile.cloudrun` packages the FastAPI backend and static dashboard into one Cloud Run service. The service serves the dashboard at `/` and `/dashboard`, and the API under `/api/v1`.

Use Cloud SQL or another managed PostgreSQL database for production `DATABASE_URL`. Keep `EMAIL_SENDING_ENABLED=false` until Gmail dry-run, approval, and reply sync are verified in production.

```bash
gcloud artifacts repositories create personal-outreach --repository-format=docker --location=us-central1
gcloud builds submit --config cloudbuild.yaml
```

The app starts with manual targets, job discovery rows, and CSV import so it stays focused on your personal outreach process.

## Roadmap

- Job discovery: pull matching roles from job boards, company career pages, or saved searches.
- Contact discovery: enrich target companies with recruiter or hiring-manager contacts.
- Optional tracker sync: connect a spreadsheet or other personal tracker later if it becomes useful.
- Resume/context memory: personalize outreach using selected project and resume highlights.
- Follow-up planner: show due follow-ups and suggested next actions.

## Architecture

```text
Manual entry / CSV import / job discovery import
        |
        v
Cloud Scheduler (cron) ---> FastAPI orchestration ---> PostgreSQL audit/state
                                 |
                                 +--> Draft + QA agents --> LiteLLM --> model provider
                                 |
                                 +--> Human approval dashboard
                                 |
                                 +--> Gmail send + inbox sync
```

All pipeline logic (API calls, conditions, AI drafting, data transformation,
email) lives in the FastAPI backend. Cloud Scheduler only decides *when* each
automation endpoint runs — there is no separate workflow engine.

Supporting services:

- PostgreSQL: durable contacts, campaigns, drafts, replies, audit events
- Redis: LiteLLM cache and future queue/rate-limit work
- Qdrant: available for future retrieval and memory features
- LiteLLM: model aliases, routing, budgets, and provider abstraction
- Cloud Scheduler (production): time-based triggers that POST to the automation endpoints

## Safety Defaults

- Every email requires human approval.
- `EMAIL_SENDING_ENABLED=false` performs a dry run instead of sending.
- `EMAIL_REPLY_SYNC_ENABLED=false` prevents mailbox polling.
- Scheduled jobs only prepare drafts; nothing is sent without approval.

## Local Windows Setup

```powershell
cd C:\personal-outreach-agent
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
docker compose up -d postgres redis qdrant litellm
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd C:\personal-outreach-agent
.\.venv\Scripts\python.exe -m http.server 3000 --directory dashboard --bind 127.0.0.1
```

Open:

- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs
- Readiness: http://localhost:8000/api/v1/system/readiness
- LiteLLM: http://localhost:4000

## Gmail Setup

This project is designed around a personal outreach Gmail account.

1. Create or select a Google Cloud project.
2. Configure an OAuth consent screen for your own account.
3. Create an OAuth client for a local web app.
4. Add this redirect URI: `http://localhost:8000/auth/google/callback`
5. Add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_SENDER_EMAIL`, and `GOOGLE_INBOX_EMAIL` to `.env`.
6. Start the backend and open `http://localhost:8000/auth/google/start`.
7. After consent, the app saves `GOOGLE_REFRESH_TOKEN` locally in `.env`.

Live sending still requires `EMAIL_SENDING_ENABLED=true`. Keep it disabled while testing.

## Scheduled Automation

Production automation runs on Google Cloud Scheduler — time-based cron jobs that
POST to the FastAPI automation endpoints. The scheduled jobs are:

1. Pipeline advancement (`/pipeline/run-batch`)
2. Draft queue generation (`/automation/generate-drafts`)
3. Email reply synchronization (`/integrations/email/sync-replies`)
4. Follow-up queue generation (`/automation/generate-followups`)

See [infra/scheduler/README.md](infra/scheduler/README.md) for the setup script
and cadences. Locally, trigger the same endpoints by hand or from the dashboard.

## External Credentials Still Required

Live AI requires a valid model-provider key behind LiteLLM. Live Gmail operation requires a Google Cloud OAuth client, Gmail API access, and a refresh token for the outreach mailbox.

Do not enable live sending until Gmail OAuth, dry-run send behavior, and the human approval flow have been tested end to end.

## Validation

```powershell
.\.venv\Scripts\python.exe -m ruff check backend\app
.\.venv\Scripts\python.exe -m compileall -q backend\app
docker compose config --quiet
node --check dashboard\app.js
```

Do not run the full database test suite against a populated local development database; the tests reset tables.
