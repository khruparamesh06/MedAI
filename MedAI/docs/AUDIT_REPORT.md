# MedAI security & quality audit — 2026-10-28

Scope: full codebase (frontend, backend, migrations, AI module, scripts, docs). Method: code review,
reproduction of each suspected defect with an automated test *before* fixing it
(`backend/app/tests/test_audit_regressions.py`; 14 of its tests failed on the unmodified code),
live HTTP checks against a running server, migrations and the full test suite on PostgreSQL 16.2,
and page-by-page inspection of the real UI in headless Microsoft Edge (desktop 1280 px and mobile 390 px).

Status legend: **Fixed** (fix + regression test) · **Mitigated** (reduced, residual risk documented) · **Open** (needs a human decision or infrastructure).

## Critical

| ID | Finding | Evidence | Impact | Fix / status |
|----|---------|----------|--------|--------------|
| C-1 | **Migration 0002 wiped all clinical data on SQLite.** Introduced during this audit (the first version of the new migration), caught before release. | `migrations/env.py` reused the app engine, which sets `PRAGMA foreign_keys=ON`. Alembic batch mode rebuilds `users` via `DROP TABLE` + rename; the drop fired `ON DELETE CASCADE`, emptying doctor_profiles, availability, assignments, appointments, uploads, analyses and reviews in the dev database (users survived). Reproduced with SQL logging on a copy. | Irrecoverable loss of medical records on upgrade. | **Fixed.** Migrations run with SQLite FK enforcement off and finish with `PRAGMA foreign_key_check`; 0002 uses a plain `ADD COLUMN`; new `python -m app.cli migrate` backs up SQLite before any pending migration (used by all scripts). Regression test `test_migrations_preserve_existing_data` (fails on the old env, passes now). The dev database was restored from the pre-upgrade backup; row counts verified. |

## High

| ID | Finding | Evidence | Impact | Fix / status |
|----|---------|----------|--------|--------------|
| H-1 | No rate limiting on sign-in, registration, upload or analysis. | No limiter existed; unlimited 401s in tests. | Password guessing / credential stuffing; storage and CPU exhaustion. | **Fixed (per process).** `app/services/rate_limit.py`: 30 sign-in attempts/5 min/IP, 5 failed attempts/15 min/account (429 + `Retry-After`), 10 registrations/h/IP, 30 uploads/h/user, 60 analyses/h/user, 10 password changes/h/user. Cannot be disabled in production. Multi-instance deployments still need a gateway limit (see DEPLOYMENT). |
| H-2 | Request bodies were fully received before the size check. | Starlette's `max_part_size` applies only to non-file fields; file parts are spooled to disk unbounded, and `read_limited` ran afterwards. | Disk/memory exhaustion with one large request. | **Fixed.** `app/core/middleware.py` rejects bodies over the limit by `Content-Length` and while streaming (chunked). Verified live: 12 MB chunked and 15 MB uploads → 413. JSON bodies are capped at 1 MB. |
| H-3 | Docker image trusted `X-Forwarded-For` from any client (`--forwarded-allow-ips='*'`). | `backend/Dockerfile` CMD. | Clients could spoof their IP and bypass IP-based rate limits / pollute logs. | **Fixed.** Uses `FORWARDED_ALLOW_IPS` (default `127.0.0.1`), documented to be set to the proxy address. |

## Medium

| ID | Finding | Evidence | Impact | Fix / status |
|----|---------|----------|--------|--------------|
| M-1 | Decompression-bomb window. | Pillow only *raises* above 2×`MAX_IMAGE_PIXELS` (warns in between); an 8000×8000 PNG of ~100 KB was decoded. | Large memory spikes per upload. | **Fixed.** Dimensions are checked from the header before decoding (≤ 36 MP, ≤ 12 000 px per side) → 422. |
| M-2 | Sign-out did not revoke the token on the server. | Frontend only deleted it from `sessionStorage`. | A copied token stayed valid until expiry. | **Fixed.** Tokens carry a `jti`; `POST /api/auth/logout` stores it in `revoked_tokens`; checked on every request. Frontend calls it on sign-out. |
| M-3 | Administrator-created doctors could keep the admin-chosen temporary password indefinitely. | No forced change. | Shared credential known to another person. | **Fixed.** `users.must_change_password`; all endpoints except `me`/change-password/logout return 403 until changed; new password must differ; UI redirects to Account settings. |
| M-4 | Ending an assignment left open appointments the doctor could no longer manage. | Doctor got 404 on its own appointment after the end. | Stuck "confirmed" appointments; patient confusion. | **Fixed.** Ending cancels open future appointments of that pair (noted on the appointment, counted in the audit event). |
| M-5 | Doctors could list appointments (patient name, email, reason) of patients no longer assigned, and unapproved doctors could list appointments. | `GET /api/appointments` filtered only by `doctor_id`. | Disclosure of patient data outside an active care relationship. | **Fixed.** Requires approved profile and currently approved assignment; UI shows an approval gate instead of an error. |
| M-6 | Model weights could load with no pinned checksum. | `weights_sha256` was optional. | Swapped/corrupted weights loaded silently. | **Fixed.** Checksum is mandatory; tests for missing checksum, corrupted file and incompatible state dict. |
| M-7 | Missing defensive handling around inference. | Unreadable stored file (`UnidentifiedImageError`) or a runtime model error → unhandled 500, nothing recorded. | Confusing failures. | **Fixed.** Recorded as a *failed* analysis with a generic message (details logged), never a score. Inference uses its own lock so status checks are not blocked during inference; model preloads at startup in the background. |
| M-8 | UI: mobile pages scrolled horizontally (117–151 px) and the X-ray result page was clipped. | Measured in headless Edge at 390 px. Cause: visually-hidden table headers positioned against the page, and `1fr` grid tracks that cannot shrink. | Poor mobile usability. | **Fixed.** All 25 mobile pages now report 0 px overflow. |

## Low

| ID | Finding | Fix / status |
|----|---------|--------------|
| L-1 | Patients could cancel appointments in the past. | **Fixed** (409). |
| L-2 | 422 responses echoed submitted values (including passwords) back. | **Fixed**: only `type`, `loc`, `msg` returned. |
| L-3 | Review form pre-selected "Agree" with the AI (automation-bias risk). | **Fixed**: explicit choice required; hint asks for an independent read first. |
| L-4 | Desktop showed the mobile menu button; tabs showed stray scroll arrows; closed mobile menu was still keyboard-focusable and cast a shadow. | **Fixed** (CSS; off-canvas menu now `visibility: hidden` when closed). |
| L-5 | Pending doctor's Appointments page showed a red error with a useless "Try again". | **Fixed**: approval gate with a link to the profile. |
| L-6 | `stop.ps1` killed whatever listened on ports 8000/5173. | **Fixed**: only python/node processes are stopped. `start.ps1` now quotes paths safely. |
| L-7 | Production could start with `CORS_ORIGINS=*` or `http://` origins; Swagger exposed in production; no HSTS; API responses cacheable. | **Fixed**: refused at startup; docs off by default in production; HSTS in production; `Cache-Control: no-store`. |
| L-8 | Registration reveals whether an email is registered (409). | **Open (accepted)**: common UX trade-off; mitigated by registration rate limit. |
| L-9 | Account lockout (5 failures/15 min) can be triggered by others to block a user temporarily. | **Mitigated / accepted**: limited window; admins can see audit log. Review for production. |
| L-10 | Rate limits are in-memory (reset on restart, per process). | **Open**: add proxy/gateway limits for multi-instance deployments. |
| L-11 | Access tokens in `sessionStorage` are readable by injected script (XSS). | **Open**: no XSS sink found (React escaping, no `dangerouslySetInnerHTML`); add a strict CSP at the host; consider HttpOnly cookies. |
| L-12 | Patients see AI scores before any clinician review. | **Open — needs clinical decision** (see SECURITY_PRIVACY_CLINICAL_REVIEW.md). |

## Verified as already correct (no change needed)
- Argon2id hashing; minimum password policy; constant-message, timing-equalised login failures.
- Role checks on every protected route; patient ownership and approved-assignment checks centralised in `services/access.py`; inaccessible records return 404 (tested for X-rays, images, reviews, notes, patients, appointments).
- Disabled accounts: sign-in refused, existing tokens revoked (token version).
- No SQL built from strings (SQLAlchemy parameters only); LIKE searches are parameterised.
- Stored file names are server-generated (`uuid4().hex + .png`), validated by regex, resolved and checked against the storage root; no static route serves uploads.
- EXIF/metadata removed by re-encoding; content validated with Pillow, not by extension/MIME.
- Audit log contains IDs and actions only; server logs checked live — no passwords, tokens or clinical text.
- AI: architecture/weights/labels/preprocessing match TorchXRayVision `densenet121-res224-all` (strict state-dict load, 18 outputs); safe restricted unpickler; analysis rows are linked to the exact upload (test `test_analysis_linked_to_requested_image`).
