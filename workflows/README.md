# n8n Workflows

These workflows call the FastAPI service. They are imported inactive so they cannot run accidentally.

| File | Schedule | Purpose |
| --- | --- | --- |
| 02-generate-draft-queue.json | Weekdays 7:15 AM | Generate QA-checked drafts for eligible contacts |
| 03-email-reply-sync.json | Every 30 minutes | Read and classify Gmail replies |
| 04-generate-followup-queue.json | Weekdays 9:00 AM | Create follow-up drafts for sent messages |

## Required environment

- `API_BASE_URL`: defaults to `http://host.docker.internal:8000`
- `AUTOMATION_API_KEY`: must match the backend value

## Import locally

```powershell
docker compose exec -T n8n n8n import:workflow --input=/workflows/02-generate-draft-queue.json
docker compose exec -T n8n n8n import:workflow --input=/workflows/03-email-reply-sync.json
docker compose exec -T n8n n8n import:workflow --input=/workflows/04-generate-followup-queue.json
```

Review credentials and test each workflow manually before activation. Keep `EMAIL_SENDING_ENABLED=false` until Gmail OAuth and human approval behavior have been verified.
