# Implementation & verification checklist

Status after the 2026-10-28 audit, verified in the build environment (Windows 11, Python 3.12.10,
Node 24.17, PostgreSQL 16.2 via a local throwaway server). See [AUDIT_REPORT.md](AUDIT_REPORT.md).

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Frontend ↔ backend integration | ✅ | `scripts/smoke_test.py` passes against a live server (rate limits on); headless-Edge walk-through of 25 pages × 2 widths with no JS errors |
| SQLite migrations | ✅ | `app.cli migrate` (auto-backup) ; data-preservation regression test |
| PostgreSQL | ✅ tested locally | migrations up/down + `alembic check` + 73/73 backend tests on PostgreSQL 16.2 |
| Authentication, revocation, temp passwords | ✅ tested | test_auth.py, test_audit_regressions.py |
| Rate limiting & request-size limits | ✅ tested (+ live 413 check) | per-process limits; gateway limits still needed for multi-instance |
| Role/ownership/assignment authorization | ✅ tested | IDOR tests across X-rays, images, reviews, notes, patients, appointments |
| Upload validation (type, content, size, dimensions, metadata) | ✅ tested | test_xrays_ai.py, test_audit_regressions.py |
| AI: genuine model, checksum, safe loading, failure states | ✅ tested | real inference test; missing/corrupted/incompatible/unpinned weights tests |
| Appointments (booking, conflicts, cancellation rules) | ✅ tested | test_appointments.py, regressions |
| Frontend tests, lint, type check, build | ✅ | 22 tests, oxlint 0 findings, `tsc -b`, `vite build` |
| Responsive layout | ✅ inspected | 0 px horizontal overflow on all mobile pages (390 px) |
| Windows scripts | ✅ setup/test run; stop/start reviewed | start/stop not launched in this session (new windows) |
| Docker image | ⚠️ not built | Docker is not installed here |
| Public deployment | ❌ not done | guide only |
| Clinical validation | ❌ none | see SECURITY_PRIVACY_CLINICAL_REVIEW.md |
| Messaging / email / SMS / MFA | ❌ not implemented | |
