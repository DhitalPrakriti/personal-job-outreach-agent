# Dashboard

Local approval and workflow dashboard for the Personal AI Outreach Agent.

This first version is dependency-free HTML, CSS, and JavaScript. It calls the FastAPI backend at `http://localhost:8001`.

## Run Locally

Start the backend first:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload --app-dir backend
```

Then serve the dashboard from this folder:

```powershell
cd dashboard
python -m http.server 3000
```

Open:

```text
http://localhost:3000
```

## What It Supports

- Create contacts
- Batch import contacts from simple CSV text
- Create campaigns
- Generate mock drafts
- Approve or reject drafts
- Simulate send
- Classify replies
- View audit events
