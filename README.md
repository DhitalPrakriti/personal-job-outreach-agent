# AI Email Automation Agent

An intelligent email outreach automation system powered by AI agents. Handles lead enrichment, personalized email drafting, human-in-the-loop approval, sending, follow-ups, and reply classification.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        SYSTEM OVERVIEW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Lead Source (Notion/CSV)                                       │
│         │                                                        │
│         ▼                                                        │
│   ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐   │
│   │  n8n        │───▶│  AI Agents   │───▶│  Approval Queue │   │
│   │  Workflows  │    │  (via Dify)  │    │  (Dashboard)    │   │
│   └─────────────┘    └──────────────┘    └────────┬────────┘   │
│                                                    │             │
│                                                    ▼             │
│   ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐   │
│   │  Reply      │◀───│  Amazon SES  │◀───│  Send Pipeline  │   │
│   │  Handler    │    │  (Sending)   │    │  (Rate Limited) │   │
│   └─────────────┘    └──────────────┘    └─────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| LLM Gateway | LiteLLM | Model routing, budget caps, fallbacks |
| Primary Model | Claude Sonnet 4 | Research + email drafting |
| Fast Model | Claude Haiku 3.5 | Classification, QA checks |
| Agent Framework | Dify (self-hosted) | Visual agent builder |
| Workflow Engine | n8n (self-hosted) | Orchestration + scheduling |
| Database | PostgreSQL | Leads, campaigns, emails, audit log |
| Vector DB | Qdrant | Lead profiles, email memory |
| Cache/Queue | Redis | Job queue, rate limiting, caching |
| Email Sending | Amazon SES | Transactional email delivery |
| Dashboard | Next.js + Tailwind | Approval UI, lead management |
| Reverse Proxy | Caddy | SSL termination, routing |
| Hosting | Hetzner VPS (CX31) | All services via Docker Compose |

## Project Structure

```
email-automation-aiagent/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/            # API route handlers
│   │   ├── agents/         # AI agent interfaces
│   │   ├── core/           # Config, security, dependencies
│   │   ├── db/             # Database models + migrations
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # Business logic layer
│   │   └── workers/        # Background task processors
│   ├── tests/
│   ├── alembic/            # DB migrations
│   └── requirements.txt
├── dashboard/              # Next.js frontend
│   ├── src/
│   │   ├── app/           # App router pages
│   │   ├── components/    # UI components
│   │   └── lib/           # API client, utilities
│   └── package.json
├── workflows/              # n8n workflow exports (JSON)
├── agents/                 # Dify agent configs (YAML/JSON)
├── infra/                  # Infrastructure configs
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   ├── caddy/Caddyfile
│   └── scripts/           # Setup, backup, deploy scripts
├── docs/                   # Documentation
├── .env.example
├── .gitignore
└── README.md
```

## Quick Start (Local Development)

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 20+
- Anthropic API key (for Claude)

### Setup

```bash
# Clone the repo
git clone git@github.com:<ORG>/email-automation-aiagent.git
cd email-automation-aiagent

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# Start infrastructure services
docker compose up -d postgres redis qdrant

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Dashboard (separate terminal)
cd dashboard
npm install
npm run dev
```

### Full Stack (Docker)

```bash
docker compose up -d
```

Services will be available at:
- API: http://localhost:8000
- Dashboard: http://localhost:3000
- n8n: http://localhost:5678
- Dify: http://localhost:3100

## Development

- **Backend**: FastAPI with async SQLAlchemy. Run tests with `pytest`.
- **Dashboard**: Next.js 14 with App Router. Run with `npm run dev`.
- **Migrations**: `alembic revision --autogenerate -m "description"` then `alembic upgrade head`
- **Workflows**: Export from n8n UI → save JSON to `workflows/`

## Environment Variables

See [.env.example](.env.example) for all required configuration.

## License

Proprietary — Internal use only.
