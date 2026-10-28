# Deployment guide

> Status: **not deployed.** This guide describes how to deploy; nothing here has been run against
> a public host. Do not put real patient data on a deployment that has not had a professional
> security, privacy (e.g. HIPAA / GDPR / India DPDP Act) and clinical-safety review.

## Overview

| Part | Suggested hosting | Notes |
|------|-------------------|-------|
| Frontend (static files) | Netlify, Vercel, Cloudflare Pages, GitHub Pages, S3+CloudFront | `npm run build` → `frontend/dist` |
| Backend (FastAPI) | Render, Railway, Fly.io, Azure App Service, a VM, or any Docker host | `backend/Dockerfile` |
| Database | Managed PostgreSQL (Neon, Supabase, Render, Railway, AWS RDS, Azure) | SQLite is refused when `APP_ENV=production` |
| Images | Persistent **private** disk/volume mounted at `UPLOAD_DIR` | never a public bucket |
| Model weights | Downloaded on the server with `fetch_pretrained.py`, or mounted read-only | not baked into git |

## 1. Prepare the code
1. Push to GitHub (see README). Confirm `git status` shows no `.env`, `*.db`, `backend/storage`, `ai/weights`.
2. Run `scripts\test.ps1` and make sure everything passes.

## 2. Database
Create a managed PostgreSQL database and note its URL, then convert it to the SQLAlchemy form:
`postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require`.

## 3. Backend
Environment variables (set in the host's dashboard, never in git):

| Variable | Production value |
|----------|------------------|
| `APP_ENV` | `production` |
| `JWT_SECRET_KEY` | new 48+ char random value (`python -c "import secrets;print(secrets.token_urlsafe(48))"`) |
| `DATABASE_URL` | PostgreSQL URL above |
| `CORS_ORIGINS` | exact frontend origin(s), e.g. `https://medai-demo.netlify.app` (no wildcard) |
| `UPLOAD_DIR` | mount path of the persistent private volume, e.g. `/data/xrays` |
| `MAX_UPLOAD_MB` | `10` |
| `CLINIC_TIMEZONE` | e.g. `Asia/Kolkata` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30`–`60` |
| `MODEL_CONFIG_PATH` | `/srv/medai/ai/model_config.json` (Docker image layout) |
| `FORWARDED_ALLOW_IPS` | address of your reverse proxy / load balancer (never `*` if the API port is reachable directly) |
| `RATE_LIMIT_ENABLED` | `true` (startup refuses `false` in production) |
| `ENABLE_API_DOCS` | leave unset → Swagger is **off** in production; set `true` only on staging |

Startup also refuses `CORS_ORIGINS=*` or non-HTTPS origins in production, and a SQLite database.

Docker build (from the `MedAI` folder):

```bash
docker build -f backend/Dockerfile --build-arg INSTALL_AI=true -t medai-backend .
docker run -p 8000:8000 --env-file prod.env -v medai-xrays:/data/xrays -v $PWD/ai/weights:/srv/medai/ai/weights:ro -v $PWD/ai/model_config.json:/srv/medai/ai/model_config.json:ro medai-backend
```

The container runs `alembic upgrade head` on start. **Take a database backup (`pg_dump`) before
deploying a version that contains new migrations.** To run migrations manually:
`cd backend && alembic upgrade head` (or `python -m app.cli migrate`).

**Create the administrator** (one-off shell on the server; the password is read interactively or from
`MEDAI_ADMIN_PASSWORD`, never from a URL):

```bash
cd backend && python -m app.cli create-admin --email admin@yourhospital.org --name "Administrator"
```

Never run `seed-demo` in production (it refuses when `APP_ENV=production`).

**HTTPS / proxy:** terminate TLS at the platform or a reverse proxy; uvicorn is started with
`--proxy-headers` and trusts `X-Forwarded-For` only from `FORWARDED_ALLOW_IPS`. The API sends HSTS
in production. MedAI has built-in rate limits, but they are in-memory **per process**: if you run
several instances, also rate-limit `/api/auth/*` and `/api/xrays` at the proxy/gateway. Set a strict
Content-Security-Policy on the frontend host, e.g.
`default-src 'self'; img-src 'self' blob:; connect-src https://your-backend.example.com; frame-ancestors 'none'`.

**Logs:** the backend logs to stdout (`medai.*` loggers: model state, failed sign-ins by IP,
rate-limit hits, unhandled errors with stack traces). They never contain passwords, tokens or clinical
text. Uvicorn access logs include request paths and client IPs.

## 4. AI model on the server
- Install the AI requirements (`INSTALL_AI=true` image) — adds ~1 GB; needs ≥ 2 GB RAM.
- Run `python ai/inference/fetch_pretrained.py` on the server (or mount `ai/weights` +
  `ai/model_config.json`), then restart. Check `GET /api/health/ready` → `"model_state": "ready"`.
- Inference is synchronous (~1.5 s/image on a laptop CPU). Use one worker per CPU core, a request
  timeout ≥ 30 s, and keep `MAX_UPLOAD_MB` low. For heavier use, move inference to a background
  worker/queue or a GPU host.
- Without weights, the app still works and reports *Model not configured*.

## 5. Frontend
Set `VITE_API_URL=https://your-backend.example.com` as a **build-time** variable, then:

```bash
cd frontend && npm ci && npm run build      # output: frontend/dist
```

Configure the host to serve `index.html` for unknown paths (SPA fallback):
Netlify `_redirects`: `/*  /index.html  200`; Vercel: a rewrite of `/(.*)` → `/index.html`.

## 6. Verify
1. `GET https://backend/api/health` → `{"status":"ok","environment":"production"}`
2. `GET https://backend/api/health/ready` → `database: true`
3. Open the frontend: the sign-in page must **not** show "Server unreachable".
4. Browser dev tools → Network: API calls succeed with no CORS errors.
5. Sign in as the administrator; register a test patient; upload a public-domain test image.
6. Optionally: `python scripts/smoke_test.py --api https://backend` (requires demo accounts — only on a staging environment).

## 7. Operations
- Back up PostgreSQL **and** the image volume together (see [DATA_HANDLING.md](DATA_HANDLING.md)).
- Before any human uses it with real data, complete [SECURITY_PRIVACY_CLINICAL_REVIEW.md](SECURITY_PRIVACY_CLINICAL_REVIEW.md).
- Rotate `JWT_SECRET_KEY` to force everyone to sign in again.
- Monitor `/api/health/ready`; read logs for `Unhandled error`.
- Review `/api/admin/audit` regularly.
