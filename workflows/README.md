# n8n Workflow Exports

Store exported n8n workflow JSON files here for version control.

## Naming Convention

- `01-lead-import.json` — CSV/Notion import → validate → enrich
- `02-research-draft.json` — Research agent → Draft agent → QA → approval queue
- `03-send-email.json` — Approved email → rate limit check → SES send
- `04-follow-up.json` — Timer trigger → check replies → generate follow-up
- `05-reply-handler.json` — IMAP poll → classify → update status → alerts
- `06-bounce-handler.json` — SES webhook → add to DNC list

## How to Export

1. Open n8n UI
2. Select workflow → Menu → Download
3. Save JSON here with the naming convention above
4. Commit to git
