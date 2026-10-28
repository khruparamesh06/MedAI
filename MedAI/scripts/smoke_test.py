"""
End-to-end smoke test against a RUNNING MedAI backend, exercising the full workflow:
patient registration -> X-ray upload -> AI status / analysis -> doctor assignment request ->
administrator approval -> appointment booking -> doctor confirmation -> clinician review.

Requires the synthetic demo accounts (python -m app.cli seed-demo). Uses only a generated image.

    backend\\.venv\\Scripts\\python scripts\\smoke_test.py [--api http://localhost:8000]
"""
import argparse
import io
import sys
import uuid
from datetime import date, timedelta

import httpx
import numpy as np
from PIL import Image

DEMO_PASSWORD = "DemoPass123!"
ADMIN = "admin@medai.example.com"
DOCTOR = "dr.mehta@medai.example.com"


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        sys.exit(1)


def login(c: httpx.Client, email: str, password: str = DEMO_PASSWORD) -> dict:
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    check(r.status_code == 200, f"login {email}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def synthetic_png() -> bytes:
    y, x = np.mgrid[0:512, 0:512]
    arr = (127 + 100 * np.sin(x / 40.0) * np.cos(y / 55.0)).astype(np.uint8)  # not a medical image
    buf = io.BytesIO()
    Image.fromarray(arr, "L").save(buf, format="PNG")
    return buf.getvalue()


def next_weekday() -> date:
    d = date.today() + timedelta(days=2)
    while d.weekday() > 4:  # demo doctors work Monday-Friday
        d += timedelta(days=1)
    return d


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    c = httpx.Client(base_url=args.api, timeout=120)

    print("Health")
    check(c.get("/api/health").json()["status"] == "ok", "GET /api/health")
    check(c.get("/api/health/ready").json()["database"] is True, "database reachable")

    print("Patient registration")
    email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
    r = c.post("/api/auth/register", json={"email": email, "password": "SmokeTest123!", "full_name": "Smoke Test Patient"})
    check(r.status_code == 201 and r.json()["user"]["role"] == "patient", "register patient")
    pat = {"Authorization": f"Bearer {r.json()['access_token']}"}

    print("X-ray upload")
    r = c.post("/api/xrays", headers=pat, files={"file": ("synthetic.png", synthetic_png(), "image/png")},
               data={"view_position": "PA", "note": "smoke test"})
    check(r.status_code == 201, "upload synthetic image")
    xid = r.json()["id"]
    check(c.get(f"/api/xrays/{xid}/image").status_code == 401, "image requires authentication")
    check(c.get(f"/api/xrays/{xid}/image", headers=pat).status_code == 200, "owner can fetch image")

    print("AI")
    status = c.get("/api/ai/status", headers=pat).json()
    print(f"        model state: {status['state']} ({status.get('model_name') or status['reason']})")
    r = c.post(f"/api/xrays/{xid}/analyze", headers=pat)
    if status["available"]:
        check(r.status_code == 201 and r.json()["status"] == "completed", "analysis completed with genuine model")
        top = r.json()["findings"][:3]
        print("        top scores (synthetic image, meaningless clinically):",
              ", ".join(f"{f['display_name']}={f['score']:.2f}" for f in top))
    else:
        check(r.status_code == 503, "analysis refused: model not configured")

    print("Doctor assignment")
    doctors = c.get("/api/doctors", headers=pat).json()["items"]
    doc = next(d for d in doctors if d["full_name"] == "Dr. Vikram Mehta")
    r = c.post("/api/assignments", headers=pat, json={"doctor_id": doc["user_id"], "reason": "Smoke test"})
    check(r.status_code == 201 and r.json()["status"] == "pending", "assignment requested")
    aid = r.json()["id"]
    dh = login(c, DOCTOR)
    check(c.get(f"/api/xrays/{xid}", headers=dh).status_code == 404, "doctor blocked before approval")
    adm = login(c, ADMIN)
    r = c.post(f"/api/admin/assignments/{aid}/approve", headers=adm, json={})
    check(r.status_code == 200 and r.json()["status"] == "approved", "admin approved assignment")
    check(c.get(f"/api/xrays/{xid}", headers=dh).status_code == 200, "doctor can view after approval")

    print("Appointment")
    r = c.post("/api/appointments", headers=pat, json={
        "doctor_id": doc["user_id"], "date": next_weekday().isoformat(), "start_time": "10:00", "reason": "Discuss X-ray"})
    if r.status_code == 409:  # slot taken by an earlier smoke run
        r = c.post("/api/appointments", headers=pat, json={
            "doctor_id": doc["user_id"], "date": next_weekday().isoformat(),
            "start_time": f"{9 + uuid.uuid4().int % 3}:{(uuid.uuid4().int % 4) * 15:02d}", "reason": "Discuss X-ray"})
    check(r.status_code == 201, f"appointment requested ({r.status_code})")
    r = c.patch(f"/api/appointments/{r.json()['id']}", headers=dh, json={"status": "confirmed"})
    check(r.status_code == 200 and r.json()["status"] == "confirmed", "doctor confirmed appointment")

    print("Clinician review")
    detail = c.get(f"/api/xrays/{xid}", headers=dh).json()
    analysis_id = detail["analyses"][0]["id"] if detail["analyses"] else None
    r = c.post(f"/api/xrays/{xid}/reviews", headers=dh, json={
        "findings": "Synthetic test image; not a radiograph.", "impression": "Not interpretable.",
        "ai_agreement": "disagree" if analysis_id else "not_applicable", "status": "final", "analysis_id": analysis_id})
    check(r.status_code == 201, "doctor finalised review")
    check(len(c.get(f"/api/xrays/{xid}", headers=pat).json()["reviews"]) == 1, "patient sees final review")

    print("\nEnd-to-end workflow passed.")


if __name__ == "__main__":
    main()
