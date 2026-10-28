# Items that require human security, privacy, or clinical review

Automated tests and this audit do **not** establish that MedAI is secure, lawful to operate with real
patient data, or clinically safe. Before any real-world use, qualified people must review:

## Security
1. Independent penetration test of the deployed system (auth, IDOR/BOLA, upload handling, headers, TLS).
2. Token strategy: `sessionStorage` bearer tokens vs. HttpOnly/SameSite cookies + CSRF; token lifetime; need for refresh tokens.
3. A strict Content-Security-Policy and other headers at the frontend host.
4. Gateway-level rate limiting / WAF for multi-instance deployments (in-app limits are per process), and the account-lockout policy (L-9).
5. Secret management (where `JWT_SECRET_KEY` and database credentials live, rotation procedure).
6. Dependency vulnerability scanning (`pip-audit`, `npm audit`) in CI and an update policy.
7. Multi-factor authentication for administrators and doctors (not implemented).
8. Monitoring/alerting on the audit log (e.g. repeated failed sign-ins, mass record access).

## Privacy / legal
1. Lawful basis, consent text, privacy notice and terms of use (none are included).
2. Applicable law: HIPAA (US), GDPR (EU), DPDP Act 2023 (India), local medical-record retention rules.
3. Data retention periods and whether patient-initiated erasure is permitted ([DATA_HANDLING.md](DATA_HANDLING.md)).
4. Data residency of the hosting provider, database and backups; encryption at rest; backup access.
5. Whether administrators should see patient names/emails in assignment and appointment lists.
6. Data-processing agreements with hosting providers.
7. Licence terms of the datasets behind the pretrained weights before any commercial or clinical use.

## Clinical safety
1. **The model is not validated** on any local population, scanner or protocol. A formal evaluation
   (`ai/evaluation/evaluate.py` on representative, labelled, held-out local data) and review by
   radiologists is required before any clinical reliance.
2. **Should patients see AI scores before a clinician has reviewed them?** Currently they do (with
   warnings). Many services hide AI output from patients until clinician sign-off. This is a clinical
   governance decision (finding L-12).
3. The model scores non-chest and out-of-distribution images; no OOD detector is included.
4. Wording of all patient-facing disclaimers and score explanations.
5. Regulatory status: software that informs diagnosis may be a medical device (FDA, EU MDR, CDSCO).
   MedAI is an educational project and must not be marketed or used as a diagnostic device.
6. Workflow safety: how urgent findings are escalated (MedAI sends no notifications), review turnaround
   expectations, and what happens when an assignment ends with unreviewed images.
