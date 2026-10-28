# MedAI — AI-Assisted Chest X-ray Analysis and Hospital Management System

MedAI is a hospital portal for **patients**, **doctors** and **administrators**. Patients upload chest
X-rays, request a doctor, and book appointments. Approved doctors review their assigned patients'
images alongside scores from a genuine pretrained deep-learning model and write their own clinical
review. Administrators approve doctors and doctor–patient assignments.

> ⚠️ **MedAI is an experimental, educational decision-support project. It is not a medical device,
> it is not clinically validated, and its AI output is never a diagnosis.**

| Layer    | Technology |
|----------|------------|
| Frontend | React 19, TypeScript, Vite, React Router, Lucide icons, plain CSS design tokens |
| Backend  | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Argon2id, JWT |
| Database | SQLite (local default) · PostgreSQL (deployment) |
| AI       | PyTorch, TorchXRayVision DenseNet-121 (pretrained), Pillow, scikit-image |

---

## Contents
1. [Features](#features)
2. [Project structure](#project-structure)
3. [Windows setup (step by step)](#windows-setup-step-by-step)
4. [Running the app](#running-the-app)
5. [Enabling the AI model](#enabling-the-ai-model)
6. [Trying the complete workflow](#trying-the-complete-workflow)
7. [Running the tests](#running-the-tests)
8. [Troubleshooting](#troubleshooting)
9. [Publishing to GitHub & deployment](#publishing-to-github--deployment)
10. [Known limitations](#known-limitations)

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/API.md](docs/API.md) ·
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) · [docs/AI_MODEL_PROVENANCE.md](docs/AI_MODEL_PROVENANCE.md) ·
[ai/README.md](ai/README.md) · [docs/CHECKLIST.md](docs/CHECKLIST.md) ·
[docs/AUDIT_REPORT.md](docs/AUDIT_REPORT.md) · [docs/DATA_HANDLING.md](docs/DATA_HANDLING.md) ·
[docs/SECURITY_PRIVACY_CLINICAL_REVIEW.md](docs/SECURITY_PRIVACY_CLINICAL_REVIEW.md)

---

## Features

**Patients** register (public registration always creates a *patient*), edit their profile, upload
PNG/JPEG chest X-rays to private storage, view their history, request AI analysis, browse approved
doctors, request a doctor assignment and see its status, book/cancel appointments within the
doctor's availability, and view a printable medical record with finalised clinician reviews.

**Doctors** (accounts created by an administrator) complete a professional profile and weekly
availability and submit it for approval. Once approved they see only *assigned* patients, review
X-rays with the AI output, write draft/final clinical reviews and notes, and confirm, decline,
complete or cancel their appointments.

**Administrators** approve/reject doctor profiles and assignment requests, end assignments,
disable/enable accounts (revoking their sessions), see all appointments, and read an audit log.

**AI** — a genuine pretrained model (TorchXRayVision DenseNet-121, 18 findings) runs only when its
verified weights are installed. Otherwise the app clearly shows **“Model not configured”** and never
displays a result. Scores are labelled as uncalibrated, severity is never inferred, and every result
records model name, version, weights checksum and preprocessing.

**Security** — Argon2id password hashing; short-lived JWTs revocable per session (sign-out) or for
all sessions; forced change of administrator-issued temporary passwords; rate limiting of sign-in,
registration, uploads and analysis; request-size limits enforced while the body streams in; backend
role and ownership checks on every endpoint (IDs cannot be probed — inaccessible records return
404); images served only through an authorised endpoint; uploads validated by content and pixel
dimensions, re-encoded (metadata stripped) and stored under random names; audit trail; strict CORS;
no secrets in code. See the [audit report](docs/AUDIT_REPORT.md).

## Project structure

```
MedAI/
├── README.md              ← you are here
├── .env.example           ← configuration template (copy to .env)
├── docker-compose.yml     ← optional PostgreSQL + backend containers
├── backend/
│   ├── requirements.txt / requirements-ai.txt
│   ├── alembic.ini, migrations/        ← database migrations
│   └── app/
│       ├── main.py                     ← FastAPI entry point
│       ├── cli.py                      ← create-admin, seed-demo, model-status
│       ├── core/  (config, security, auth dependencies)
│       ├── db/    (engine, base model)
│       ├── models/ schemas/ routes/ services/
│       └── tests/                      ← pytest suite
├── frontend/
│   └── src/ (api/, components/, layouts/, pages/, hooks/, styles/, test/)
├── ai/
│   ├── model_config.default.json       ← shipped config (model disabled)
│   ├── preprocessing/ inference/ training/ evaluation/
│   └── weights/                        ← downloaded weights (git-ignored)
├── scripts/  (setup.ps1, start.ps1, stop.ps1, init-db.ps1, test.ps1, smoke_test.py)
└── docs/
```

---

## Windows setup (step by step)

### 0. Install the prerequisites (once)

| Tool | Version | Where |
|------|---------|-------|
| Python | **3.12** (tick *“Add python.exe to PATH”*) | https://www.python.org/downloads/ |
| Node.js | 20 LTS or newer | https://nodejs.org/ |
| Git (optional, for GitHub) | any | https://git-scm.com/ |

Open **PowerShell** and check:

```powershell
py -3.12 --version
node --version
npm --version
```

All commands below are run in PowerShell from the `MedAI` folder:

```powershell
cd C:\path\to\MedAI
```

### Option A — automatic setup (recommended)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -SeedDemo
```

This creates `backend\.venv`, installs all dependencies, creates `.env` with a random
`JWT_SECRET_KEY`, applies the migrations to a local SQLite database, loads **synthetic** demo
accounts and runs `npm install`. Add `-WithAI` to also install PyTorch (~1 GB download).

### Option B — manual setup (useful for troubleshooting)

```powershell
# 1. Python virtual environment
py -3.12 -m venv backend\.venv

# 2. Backend dependencies
backend\.venv\Scripts\python -m pip install --upgrade pip
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
#    (optional) AI stack:
backend\.venv\Scripts\python -m pip install -r backend\requirements-ai.txt

# 3. Configuration
Copy-Item .env.example .env
backend\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"
notepad .env      # paste the printed value after JWT_SECRET_KEY=  and save

# 4. Database (SQLite by default: backend\medai.db). "migrate" backs up an existing
#    SQLite database to backend\backups\ before applying pending migrations.
cd backend
.\.venv\Scripts\python -m app.cli migrate

# 5a. Create your own administrator (you will be asked for a password)
.\.venv\Scripts\python -m app.cli create-admin --email admin@yourdomain.com --name "Site Admin"
# 5b. ...and/or load synthetic demo accounts (development only)
.\.venv\Scripts\python -m app.cli seed-demo
cd ..

# 6. Frontend dependencies
cd frontend
npm install
cd ..
```

**Using PostgreSQL locally instead of SQLite:** install PostgreSQL, create a database and user,
then set in `.env`:
`DATABASE_URL=postgresql+psycopg://medai:YOUR_PASSWORD@localhost:5432/medai` and rerun
`alembic upgrade head`. (Or run `docker compose up db` if you have Docker.)

### Demo accounts (created by `seed-demo`)

All use the password **`DemoPass123!`**. They are synthetic and must never exist in production.

| Role | Email | Notes |
|------|-------|-------|
| Administrator | `admin@medai.example.com` | |
| Doctor | `dr.rao@medai.example.com` | approved, assigned to the demo patient |
| Doctor | `dr.mehta@medai.example.com` | approved |
| Doctor | `dr.new@medai.example.com` | profile **pending** approval |

Doctor accounts created later from *Doctor approvals → Create doctor account* get a temporary
password; on first sign-in the doctor must choose a new password before doing anything else.
| Patient | `patient@medai.example.com` | assigned to Dr. Rao |
| Patient | `patient2@medai.example.com` | has a **pending** request for Dr. Mehta |

---

## Running the app

### With the start script

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

Two windows open (backend and frontend). To stop: close them, or run
`powershell -ExecutionPolicy Bypass -File scripts\stop.ps1`.

### Manually (two PowerShell windows)

```powershell
# Window 1 — backend API
cd C:\path\to\MedAI\backend
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

```powershell
# Window 2 — frontend
cd C:\path\to\MedAI\frontend
npm run dev
```

Stop either one with **Ctrl + C**.

| What | URL |
|------|-----|
| Frontend | http://localhost:5173 |
| API health | http://localhost:8000/api/health |
| API readiness (DB + model state) | http://localhost:8000/api/health/ready |
| Swagger / OpenAPI docs | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

The frontend reads the API address from `frontend\.env` (`VITE_API_URL`, default
`http://localhost:8000`). Copy `frontend\.env.example` to `frontend\.env` to change it.

---

## Enabling the AI model

Without weights, everything except AI analysis works and the UI shows **Model not configured**.
To install the genuine pretrained model (≈28 MB download, Apache-2.0 code, see provenance doc):

```powershell
backend\.venv\Scripts\python -m pip install -r backend\requirements-ai.txt
backend\.venv\Scripts\python ai\inference\fetch_pretrained.py
cd backend; .\.venv\Scripts\python -m app.cli model-status; cd ..
```

`fetch_pretrained.py` downloads the file from the official TorchXRayVision GitHub release,
**verifies its SHA-256**, statically checks that it references only allowlisted PyTorch classes,
loads it with a restricted unpickler, converts it to a plain `state_dict`, and writes
`ai\model_config.json`. Restart the backend afterwards. Details and training your own model:
[ai/README.md](ai/README.md).

---

## Trying the complete workflow

With the demo data loaded and both servers running:

1. **Patient** — open http://localhost:5173, *Create patient account* (or sign in as
   `patient2@medai.example.com`).
2. **Upload** — *Upload X-ray* → choose a PNG/JPEG chest X-ray you are allowed to use (for a demo,
   use a public-domain sample, never a real patient's image) → *Upload securely*.
3. **AI** — on the result page choose *Run AI analysis* (or see *Model not configured*). Read the
   score explanation and limitations.
4. **Doctor assignment** — *Find a doctor* → *Dr. Vikram Mehta* → *Request this doctor*.
5. **Administrator** — sign out, sign in as `admin@medai.example.com` → *Assignment requests* →
   *Approve*. (Also try *Doctor approvals* → approve *Dr. Sam Pending*.)
6. **Appointment** — sign in as the patient → *Appointments* → *New appointment* → pick a weekday
   and time inside the doctor's hours.
7. **Doctor** — sign in as `dr.mehta@medai.example.com` → *Appointments* → *Confirm*; *My patients*
   → open the patient → open the X-ray → write and *Finalise review*.
8. **Patient** — sign back in: the review appears on the X-ray page and in *Medical record*
   (printable via *Print / save as PDF*).

An automated version of this flow runs against a live server:

```powershell
backend\.venv\Scripts\python scripts\smoke_test.py
```

---

## Running the tests

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1      # everything
```

or individually:

```powershell
cd backend;  .\.venv\Scripts\python -m pytest -q;  cd ..
cd frontend; npm test; npm run lint; npm run build; cd ..
```

Backend tests use a temporary SQLite database and generated images only. The
genuine-model inference test runs automatically when the weights are installed and is skipped
(reported as `s`) otherwise. To run the same suite on PostgreSQL, point it at an **empty, disposable**
database (tables are dropped between tests):

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://user:password@localhost:5432/medai_test'
cd backend; .\.venv\Scripts\python -m pytest -q; Remove-Item Env:TEST_DATABASE_URL
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `running scripts is disabled on this system` | Use `powershell -ExecutionPolicy Bypass -File scripts\...ps1`, or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. |
| `JWT_SECRET_KEY is missing or shorter than 32 characters` | `.env` is missing or the secret is empty — see setup step 3. |
| Sign-in page says **Server unreachable** | The backend is not running on port 8000, or `VITE_API_URL` is wrong. Open http://localhost:8000/api/health to check. |
| Browser console shows a **CORS** error | Add your frontend address to `CORS_ORIGINS` in `.env` and restart the backend. |
| `Port 5173 is in use` / `address already in use` | Run `scripts\stop.ps1`, or close the old window. |
| `no such table: users` | Run `.\.venv\Scripts\python -m app.cli migrate` inside `backend`. |
| `Too many sign-in attempts` (429) | Wait the number of minutes shown (5 failed attempts lock an account for 15 minutes). Restarting the backend also clears the in-memory counters during development. |
| *Please change your temporary password* | Open Account settings and change it; administrator-created accounts must do this once. |
| `Database already contains users; demo seed skipped` | Expected — the seed only runs on an empty database. Delete `backend\medai.db` to start over (this erases all data). |
| AI says *Model not configured* | Follow [Enabling the AI model](#enabling-the-ai-model) and restart the backend. |
| `pip` fails installing `torch` | Use Python 3.12 (64-bit). PyTorch wheels may not exist for very new Python versions. |
| Back up the local database | `cd backend; .\.venv\Scripts\python -m app.cli backup-db` (writes `backend\backups\medai-<timestamp>.db`). |
| Reset everything | **Erases all local data.** Back up first, stop the servers, delete `backend\medai.db` and `backend\storage`, then rerun `scripts\init-db.ps1 -SeedDemo`. |

---

## Publishing to GitHub & deployment

```powershell
git init
git add .
git status        # check: no .env, *.db, backend/storage, ai/weights, node_modules
git commit -m "MedAI initial version"
git branch -M main
git remote add origin https://github.com/<your-user>/medai.git
git push -u origin main
```

`.gitignore` already excludes secrets, databases, uploaded images, model weights and build output.
Never commit real patient images. Public deployment (frontend hosting, FastAPI hosting, managed
PostgreSQL, private storage, CORS, admin creation, health checks, model resources) is described in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). **This project has not been deployed publicly.**

---

## Known limitations

- **Not clinically validated.** The pretrained model was trained on public research datasets; it has
  not been evaluated on your population, scanners or workflow. It also produces scores for images
  that are not chest X-rays (only colour photos and tiny images are rejected).
- Scores are **uncalibrated** and **not probabilities**; no severity estimation is performed.
- PNG/JPEG only — DICOM is not supported. Frontal (PA/AP) views are what the model was trained on.
- No email/SMS/notifications are sent; users see status changes when they sign in.
- Doctor accounts are created by an administrator with a temporary password (no invitation e-mail).
- Access tokens live in `sessionStorage`; there is no refresh token — users sign in again after
  `ACCESS_TOKEN_EXPIRE_MINUTES`. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#authentication--token-handling).
- Inference runs synchronously inside the API process (fine for a demo; use a worker queue at scale).
- Rate limits are kept in memory per backend process; multi-instance deployments also need limits at the proxy/gateway.
- Appointment times use a single clinic time zone (`CLINIC_TIMEZONE`).
- Verified on Windows 11 with SQLite, and against a local PostgreSQL 16.2 server (migrations up/down,
  `alembic check`, and the full backend test suite). Docker images and a public deployment have **not** been tested.
- Patients currently see AI scores before a clinician reviews them — a clinical-governance decision
  listed in [docs/SECURITY_PRIVACY_CLINICAL_REVIEW.md](docs/SECURITY_PRIVACY_CLINICAL_REVIEW.md).
