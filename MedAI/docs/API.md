# API guide

Interactive documentation with request/response schemas: **http://localhost:8000/docs**
(OpenAPI JSON at `/openapi.json`). Authenticate in Swagger with *Authorize* → paste the
`access_token` returned by `/api/auth/login`.

Conventions
- JSON bodies; uploads are `multipart/form-data`.
- Auth header: `Authorization: Bearer <access_token>`.
- Errors: `{"detail": "message"}`; validation errors (422): `{"detail": [{"loc": [...], "msg": "..."}]}`.
- Lists are paginated: `?limit=20&offset=0` → `{"items": [...], "total": n, "limit": 20, "offset": 0}`.
- Status codes: 200/201/204 success · 401 missing/invalid/expired token · 403 wrong role or disabled
  account *or temporary password not yet changed* · 404 not found *or not yours* · 409 conflict/invalid
  state · 413 request/file too large · 415 unsupported file · 422 invalid input (field + message only;
  submitted values are never echoed) · 429 rate limited (see `Retry-After`) · 503 model not configured.

| Method & path | Role | Purpose |
|---------------|------|---------|
| GET `/api/health` | public | liveness, environment, clinic time zone |
| GET `/api/health/ready` | public | DB reachability (503 if down) and model state |
| POST `/api/auth/register` | public | create **patient** account → token |
| POST `/api/auth/login` | public | `{email, password}` → `{access_token, expires_in, user}` |
| GET / PATCH `/api/auth/me` | any | current user / update name (+ demographics for patients) |
| POST `/api/auth/change-password` | any | rotates token version, returns new token |
| POST `/api/auth/logout` | any | revoke the token used for this request |
| POST `/api/auth/logout-all` | any | revoke all tokens |
| GET `/api/ai/status` | any | model availability, labels, score type |
| GET `/api/doctors` | any | approved doctors (`q`, `specialty`, pagination) |
| GET `/api/doctors/specialties` · `/api/doctors/{id}` | any | directory helpers |
| GET / PUT `/api/doctors/me/profile` | doctor | own profile |
| PUT `/api/doctors/me/availability` | doctor | `{slots: [{weekday 0-6, start_time, end_time}]}` |
| POST `/api/doctors/me/profile/submit` | doctor | draft/rejected → pending |
| POST `/api/assignments` | patient | `{doctor_id, reason}` |
| GET `/api/assignments/mine` · POST `/api/assignments/{id}/cancel` | patient | own requests |
| POST `/api/xrays` | patient | multipart `file`, `view_position` (PA/AP/lateral/unknown), `note` |
| GET `/api/xrays` | patient | own uploads |
| GET `/api/xrays/{id}` · `/api/xrays/{id}/image` | owner / assigned doctor | detail with analyses + reviews / private image |
| DELETE `/api/xrays/{id}` | owner | only if no final review |
| POST `/api/xrays/{id}/analyze` | owner / assigned doctor | run genuine inference (503 if not configured) |
| POST `/api/xrays/{id}/reviews` · PUT `/api/xrays/reviews/{id}` | approved, assigned doctor | create / edit own draft |
| GET `/api/patients/me/record` | patient | uploads, shared notes, appointments |
| POST `/api/appointments` | patient | `{doctor_id, date, start_time, reason, duration_minutes}` (clinic time) |
| GET `/api/appointments` | any | own (patient/doctor) or all (admin); `status`, `upcoming` |
| PATCH `/api/appointments/{id}` | role-dependent | `{status, note}` |
| GET `/api/doctor/patients` · `/api/doctor/patients/{id}` | approved doctor | assigned patients / record |
| POST `/api/doctor/patients/{id}/notes` | approved doctor | `{body, visible_to_patient}` |
| GET `/api/doctor/review-queue` | approved doctor | uploads without a final review |
| GET `/api/admin/stats` | admin | dashboard counts |
| GET `/api/admin/users` · PATCH `/api/admin/users/{id}/status` | admin | accounts |
| POST `/api/admin/doctors` · GET `/api/admin/doctors?status=` | admin | create doctor account / list profiles |
| POST `/api/admin/doctors/{profile_id}/approve` · `/reject` | admin | `{note}` (required to reject) |
| GET `/api/admin/assignments` · POST `.../{id}/approve` · `/reject` · `/end` | admin | assignment decisions |
| GET `/api/admin/audit` | admin | audit log |

Example (PowerShell):

```powershell
$login = Invoke-RestMethod -Method Post http://localhost:8000/api/auth/login `
  -ContentType 'application/json' -Body '{"email":"patient@medai.example.com","password":"DemoPass123!"}'
$h = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod http://localhost:8000/api/xrays -Headers $h
```
