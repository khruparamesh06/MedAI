# Architecture

```
 Browser (React SPA, :5173)
   │  fetch + Authorization: Bearer <JWT>          (JSON; multipart for uploads)
   ▼
 FastAPI (:8000)  ── routes/ ── services/ ── models/ (SQLAlchemy) ── SQLite | PostgreSQL
   │                    │
   │                    ├── services/storage.py → private folder UPLOAD_DIR (random names)
   │                    └── services/ai.py → ai/inference/service.py → PyTorch model (optional)
   └── /docs (OpenAPI)
```

The frontend, backend and AI code are separate folders. The backend imports the AI package; the
AI package does not depend on the web app, so training and evaluation scripts share its exact
preprocessing and inference code.

## Backend layout

| Module | Responsibility |
|--------|----------------|
| `app/main.py` | app factory, CORS, security headers, generic 500 handler, router registration |
| `app/core/config.py` | environment-based settings (`.env`), refuses to start without a strong secret, refuses SQLite in production |
| `app/core/security.py` | Argon2id hashing, JWT creation/validation |
| `app/core/deps.py` | `get_current_user`, `require_roles`, `require_approved_doctor` |
| `app/services/access.py` | **central patient-data authorization rules** |
| `app/services/images.py` | upload size limit, content validation, re-encoding |
| `app/services/storage.py` | private storage with path-traversal protection |
| `app/services/audit.py` | audit events written in the same transaction as the change |
| `app/routes/*` | thin HTTP layer per area (auth, doctors, assignments, xrays, appointments, doctor portal, patients, admin, health) |
| `app/cli.py` | `create-admin`, `seed-demo` (refuses in production), `model-status` |
| `migrations/` | Alembic; `render_as_batch` so the same migrations run on SQLite and PostgreSQL. SQLite migrations run with foreign-key enforcement **off** (batch table rebuilds would otherwise cascade-delete child rows) and end with `PRAGMA foreign_key_check` |

## Data model

```
users (role: patient|doctor|admin, status, token_version)
 ├─1:1─ doctor_profiles (status: draft|pending|approved|rejected) ─1:n─ doctor_availability
 ├─ assignments (patient_id, doctor_id, status: pending|approved|rejected|cancelled|ended)
 │     UNIQUE(patient_id, doctor_id) WHERE status IN (pending, approved)
 ├─ appointments (patient_id, doctor_id, scheduled_at UTC, status)
 │     UNIQUE(doctor_id, scheduled_at) WHERE status IN (requested, confirmed) + overlap check in code
 ├─ xray_uploads (owner_id, stored_filename UNIQUE, sha256, status)
 │     ├─ analysis_results (model name/version/weights sha256, score_type, findings JSON, preprocessing JSON)
 │     └─ clinical_reviews (doctor_id, analysis_id?, findings, impression, ai_agreement, draft|final)
 ├─ clinical_notes (patient_id, doctor_id, visible_to_patient)
 └─ audit_events (actor_id, action, entity, detail JSON)
```

Statuses are VARCHAR + CHECK constraints (portable). All tables have timestamps; foreign keys and
indexes are declared on every relationship column.

## Core workflows

**Doctor onboarding:** admin creates doctor account (temporary password) → doctor signs in, edits
profile & availability → *submit* (draft/rejected → pending) → admin approves/rejects (rejection
requires a reason) → only `approved` + `active` doctors appear in the directory and can use
clinical endpoints. Changing the specialty or licence number of an approved profile returns it to
`pending`.

**Assignment:** patient requests an approved doctor (duplicates → 409; max 5 active) → admin
approves (re-checks doctor still approved and both accounts active) or rejects → approval grants
access; admin can *end* it, which revokes access immediately.

**X-ray:** upload (≤ `MAX_UPLOAD_MB`, PNG/JPEG verified by Pillow, EXIF orientation applied,
re-encoded to PNG which drops metadata, random `uuid4.png` name, saved with exclusive-create) →
history → *analyze*: if model unavailable → **503, nothing stored**; if image unsuitable → a
*failed* analysis record with the reason and no scores; else real inference and a completed record.

**Appointments:** patient books with an *assigned* doctor using clinic-local date + time; checks:
≥ 1 h ahead, ≤ 180 days, 15-minute grid, inside availability (if published), no overlap for the
doctor or the patient. Transitions are role-specific (doctor: confirm/decline/complete/cancel;
patient & admin: cancel). Completion is only allowed after the start time.

## Authorization model

Enforced in the backend on every request (the frontend route guards are only for UX):
- every protected route depends on `get_current_user`, which validates the JWT signature, expiry,
  type, the user's current `token_version` and role, and that the account is active;
- role dependencies protect whole routers (`/api/admin/*` requires admin);
- patient data access goes through `services/access.py`: patients → own records only; doctors →
  approved profile **and** approved assignment; admins → no clinical images/results;
- resources outside the caller's scope return **404** so IDs cannot be enumerated.

## Authentication & token handling

- Passwords: Argon2id (`argon2-cffi` defaults), min. 10 chars with letters + digits/symbols.
- Access token: HS256 JWT, `exp` = `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60), claims `sub`, `role`,
  `tv` (token version), `type`.
- Revocation: every token has a `jti`; *sign out* stores it in `revoked_tokens` (checked on every
  request, purged after expiry). Incrementing `users.token_version` invalidates all of a user's tokens —
  used by *sign out everywhere*, password change and account disabling.
- Temporary passwords: accounts created by an administrator have `must_change_password`; until it is
  changed, every endpoint except `me`, change-password and sign-out returns 403.
- Abuse limits: `services/rate_limit.py` (sign-in per IP and per account, registration, uploads,
  analyses, password changes) and `core/middleware.py` (request body size, enforced while streaming).
- Client storage: `sessionStorage` (cleared when the tab closes), sent as a Bearer header.
  *Trade-off:* no cookies means no CSRF exposure, but a successful XSS could read the token. React
  escapes all output, the app never renders API HTML, and the backend sets `nosniff`, `DENY` framing
  and `no-referrer`. For a production hospital system, prefer an `HttpOnly; Secure; SameSite=Strict`
  cookie set by the API plus CSRF protection, and a strict Content-Security-Policy at the host.
- Login failures use a constant message and equalised hashing time for unknown emails.

## Frontend

`src/api` (typed client + endpoint functions mirroring the Pydantic schemas) · `src/hooks`
(`useAuth`, `useApi`, `useToast`) · `src/components` (buttons, form fields with labelled errors,
badges, notices, dialogs built on `<dialog>`, pager, protected image) · `src/layouts/AppLayout`
(role-based navigation, responsive sidebar) · `src/pages/{public,patient,doctor,admin}` ·
`src/styles/global.css` (design tokens, responsive breakpoints, print styles).

Private images are fetched with the token as a Blob and displayed through a temporary object URL.
