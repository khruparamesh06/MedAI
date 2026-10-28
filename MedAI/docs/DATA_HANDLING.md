# Data handling: storage, deletion, retention, backups

This describes what MedAI **currently does**. Retention periods and legal obligations (medical-record
laws, HIPAA, GDPR, India's DPDP Act, local hospital policy) must be decided by the operator — see
[SECURITY_PRIVACY_CLINICAL_REVIEW.md](SECURITY_PRIVACY_CLINICAL_REVIEW.md).

## Where data lives
| Data | Location | Notes |
|------|----------|-------|
| Accounts, profiles, assignments, appointments, notes, reviews, AI results, audit log | Database (`DATABASE_URL`) | SQLite file `backend/medai.db` locally; PostgreSQL in production |
| X-ray images | `UPLOAD_DIR` (default `backend/storage/xrays`) | Re-encoded PNG, metadata removed, random file names, never served statically; only via `GET /api/xrays/{id}/image` after an access check |
| Model weights | `ai/weights/` | Not personal data; never committed |
| Logs | stdout of the backend process | Operational only: no passwords, tokens, image content or clinical text. Access logs contain URL paths (record IDs) and client IPs |

## Deletion and deactivation
- **Patient deletes an X-ray:** allowed only while it has no *finalised* clinician review. The image
  file, its AI analyses and any draft reviews are deleted; an `xray.deleted` audit event remains.
  Once a review is final the image is part of the medical record and cannot be deleted by the patient.
- **Account disabled by an administrator:** sign-in is refused and all existing sessions are revoked
  immediately. **All data is retained** (records, images, appointments). Doctors keep access to a
  disabled patient's records while an approved assignment exists — administrators should end the
  assignment if access must stop.
- **Assignment ended:** the doctor loses access immediately; open future appointments between the
  two are cancelled automatically.
- **Full account erasure:** not implemented in the application. An operator can delete a user row
  (database `ON DELETE CASCADE` removes their uploads/records metadata) but must also delete the image
  files listed in `xray_uploads.stored_filename` for that user. Decide first whether erasure is legally
  allowed for medical records in your jurisdiction.
- **Revoked tokens** (`revoked_tokens`) are purged automatically once expired (on the next sign-out).

## Backups
- **Local SQLite:** `cd backend; .\.venv\Scripts\python -m app.cli backup-db` writes a consistent copy
  to `backend/backups/` (git-ignored, excluded from the ZIP). `app.cli migrate` (used by the setup and
  start scripts) does this automatically before applying pending migrations.
- **PostgreSQL:** `pg_dump --format=custom "$DATABASE_URL" > medai-YYYYMMDD.dump`, or the managed
  provider's point-in-time recovery.
- **Images:** back up the `UPLOAD_DIR` volume **at the same time** as the database — a database
  restore without the matching images (or vice versa) leaves broken records.
- Encrypt backups, restrict who can read them, and test restores regularly.

## Restore (SQLite example)
Stop the backend, copy the backup file over `backend/medai.db`, restore the matching images folder,
then run `python -m app.cli migrate` and start the backend.
