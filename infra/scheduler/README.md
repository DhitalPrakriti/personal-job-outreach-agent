# Automation triggers — Google Cloud Scheduler

Production automation is driven by **Cloud Scheduler**: managed cron jobs that
POST to the FastAPI automation endpoints on a schedule. There is no separate
workflow engine — every step of the pipeline (job discovery, company research,
contact finding, fit scoring, AI drafting, QA, reply classification, follow-ups)
runs *inside the backend*. Cloud Scheduler only decides **when** each endpoint is
called; the backend decides **what** happens.

```
Cloud Scheduler (cron)  ──►  POST /api/v1/...  ──►  FastAPI runs the full step
```

## Jobs

| Job | Schedule (Pacific) | Endpoint | Purpose |
|-----|--------------------|----------|---------|
| `outreach-run-batch` | every 6 hours | `POST /api/v1/pipeline/run-batch` | Advance leads: discovered → analyzed → company researched |
| `outreach-generate-drafts` | 7:15 weekdays | `POST /api/v1/automation/generate-drafts` | Fill the approval queue with first-touch drafts |
| `outreach-sync-replies` | every 30 min | `POST /api/v1/integrations/email/sync-replies` | Pull and classify Gmail replies (no-op until reply sync is enabled) |
| `outreach-generate-followups` | 8:00 weekdays | `POST /api/v1/automation/generate-followups` | Draft follow-ups for un-answered outreach |

Each request carries an `X-Automation-Token` header matching the backend's
`AUTOMATION_API_KEY`, so only Cloud Scheduler can trigger these routes.

**The human approval gate is unchanged.** These jobs only *prepare* drafts;
nothing is sent until you approve it in the dashboard, and live sending stays off
until `EMAIL_SENDING_ENABLED=true`.

## Setup

```sh
# One-time: enable the API and authenticate
gcloud services enable cloudscheduler.googleapis.com
gcloud config set project <your-project-id>

# Create/update all jobs (idempotent — safe to re-run)
SERVICE_URL=https://<your-cloud-run-url> \
AUTOMATION_API_KEY=<your-token> \
REGION=us-central1 \
sh infra/scheduler/setup-scheduler.sh
```

Set the **same** `AUTOMATION_API_KEY` on the Cloud Run service so the token check
passes.

## Managing jobs

```sh
gcloud scheduler jobs list --location=us-central1
gcloud scheduler jobs run  outreach-run-batch --location=us-central1   # trigger now
gcloud scheduler jobs pause outreach-sync-replies --location=us-central1
gcloud scheduler jobs delete outreach-run-batch --location=us-central1
```

## Local development

For local runs you don't need Cloud Scheduler — trigger the same endpoints by
hand, or from the dashboard buttons:

```sh
curl -X POST http://localhost:8000/api/v1/pipeline/run-batch \
  -H 'Content-Type: application/json' -d '{}'

curl -X POST http://localhost:8000/api/v1/automation/generate-drafts \
  -H 'Content-Type: application/json' \
  -H "X-Automation-Token: $AUTOMATION_API_KEY" -d '{}'
```

## Security note

The dashboard-triggered variants (`/replies/sync`, `/followups/generate`,
`/drafts/generate`) and `/pipeline/run-batch` are **not** token-protected so the
browser dashboard can call them. On a public Cloud Run URL that means they are
reachable by anyone who knows the path. Before going fully live, put the whole
service behind access control (e.g. Cloud Run IAP or an auth layer), or add token
protection to those routes and have the dashboard supply the token.
