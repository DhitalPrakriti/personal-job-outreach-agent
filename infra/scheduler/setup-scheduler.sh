#!/usr/bin/env sh
# Create/update the Cloud Scheduler jobs that drive the automation loop.
#
# These jobs replace the old local n8n workflows. Each job is a time-based
# trigger that POSTs to one FastAPI automation endpoint; all pipeline logic
# (API calls, conditions, AI drafting, data transformation, email) runs
# inside the backend, not here.
#
# Usage:
#   SERVICE_URL=https://<your-cloud-run-url> \
#   AUTOMATION_API_KEY=<your-token> \
#   REGION=us-central1 \
#   TIME_ZONE=America/Los_Angeles \
#   sh infra/scheduler/setup-scheduler.sh
#
# Requires: gcloud CLI authenticated against the target project
#   (gcloud auth login && gcloud config set project <project-id>),
#   and the Cloud Scheduler API enabled
#   (gcloud services enable cloudscheduler.googleapis.com).
set -eu

: "${SERVICE_URL:?Set SERVICE_URL to your Cloud Run service URL}"
: "${AUTOMATION_API_KEY:?Set AUTOMATION_API_KEY (must match the backend env var)}"
REGION="${REGION:-us-central1}"
TIME_ZONE="${TIME_ZONE:-America/Los_Angeles}"

HEADERS="Content-Type=application/json,X-Automation-Token=${AUTOMATION_API_KEY}"

# create_or_update_job NAME SCHEDULE PATH BODY
create_or_update_job() {
  name="$1"
  schedule="$2"
  path="$3"
  body="$4"
  uri="${SERVICE_URL%/}${path}"

  if gcloud scheduler jobs describe "$name" --location="$REGION" >/dev/null 2>&1; then
    echo "Updating job: $name ($schedule)"
    gcloud scheduler jobs update http "$name" \
      --location="$REGION" \
      --schedule="$schedule" \
      --time-zone="$TIME_ZONE" \
      --uri="$uri" \
      --http-method=POST \
      --headers="$HEADERS" \
      --message-body="$body"
  else
    echo "Creating job: $name ($schedule)"
    gcloud scheduler jobs create http "$name" \
      --location="$REGION" \
      --schedule="$schedule" \
      --time-zone="$TIME_ZONE" \
      --uri="$uri" \
      --http-method=POST \
      --headers="$HEADERS" \
      --message-body="$body"
  fi
}

# 1. Advance the pipeline (discovery -> analyzed -> company researched) every 6 hours.
create_or_update_job "outreach-run-batch" \
  "0 */6 * * *" \
  "/api/v1/pipeline/run-batch" \
  '{}'

# 2. Fill the approval queue with first-touch drafts, 7:15am on weekdays.
create_or_update_job "outreach-generate-drafts" \
  "15 7 * * 1-5" \
  "/api/v1/automation/generate-drafts" \
  '{}'

# 3. Sync Gmail replies every 30 minutes (only acts when reply sync is enabled).
create_or_update_job "outreach-sync-replies" \
  "*/30 * * * *" \
  "/api/v1/integrations/email/sync-replies" \
  '{}'

# 4. Generate follow-up drafts for un-answered outreach, 8:00am on weekdays.
create_or_update_job "outreach-generate-followups" \
  "0 8 * * 1-5" \
  "/api/v1/automation/generate-followups" \
  '{}'

echo ""
echo "Done. List jobs with:  gcloud scheduler jobs list --location=$REGION"
echo "Drafts still require human approval in the dashboard before any email is sent."
