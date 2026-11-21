# Local development

Prerequisites: Python 3.12+, Node.js 22+, and a trusted local Pytest project.

## Backend (PowerShell)

```powershell
cd backend
py -3.12 -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
$env:QA_HUB_ALLOW_LOCAL_PATHS = "true"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Frontend (another terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The Vite development server proxies /api to the backend.

**Security:** This is a local-only development scaffold, not an authenticated production service. Do not expose port 8000 or 5173 to your LAN or the internet. Repository scans execute Pytest collection hooks and therefore must be limited to trusted project folders. The backend Python environment must have the test project's Pytest plugins/dependencies installed. Jira PATs are not yet implemented; do not store them in this project.
