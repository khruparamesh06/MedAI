"""
Regression tests for issues found in the security/quality audit (docs/AUDIT_REPORT.md).
Each test names the finding it covers.
"""
import io
import json
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from app.models import Appointment, AppointmentStatus, AnalysisResult, XrayUpload
from app.services import rate_limit
from app.tests.conftest import PASSWORD, assign, login, make_user, png_bytes, upload


def _slot(days=2, hour=10):
    d = (datetime.now(timezone.utc) + timedelta(days=days)).date()
    return {"date": d.isoformat(), "start_time": f"{hour:02d}:00"}


# H-1: brute force / credential stuffing — no rate limiting existed
def test_login_rate_limited_per_account(client, db):
    make_user(db, "victim@example.com")
    for _ in range(rate_limit.LOGIN_FAILURES_PER_ACCOUNT):
        assert client.post("/api/auth/login", json={"email": "victim@example.com", "password": "WrongPass999"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "victim@example.com", "password": PASSWORD})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_registration_rate_limited_per_ip(client):
    for i in range(rate_limit.REGISTRATIONS_PER_IP):
        client.post("/api/auth/register", json={"email": f"u{i}@example.com", "password": "Sup3rSecret!", "full_name": "User"})
    r = client.post("/api/auth/register", json={"email": "late@example.com", "password": "Sup3rSecret!", "full_name": "User"})
    assert r.status_code == 429


def test_successful_login_resets_failure_counter(client, db):
    make_user(db, "p@example.com")
    for _ in range(rate_limit.LOGIN_FAILURES_PER_ACCOUNT - 1):
        client.post("/api/auth/login", json={"email": "p@example.com", "password": "WrongPass999"})
    assert client.post("/api/auth/login", json={"email": "p@example.com", "password": PASSWORD}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "p@example.com", "password": "WrongPass999"}).status_code == 401


# H-2: request bodies were fully received/spooled before the upload size check
def test_oversized_request_rejected_by_content_length(client, people):
    _, h = people
    r = client.post("/api/xrays", headers={**h["pat"], "Content-Type": "multipart/form-data; boundary=x",
                                           "Content-Length": str(500 * 1024 * 1024)}, content=b"--x--")
    assert r.status_code == 413


def test_oversized_json_body_rejected(client):
    r = client.post("/api/auth/login", content=b'{"email":"' + b"a" * (2 * 1024 * 1024) + b'"}',
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413


# M-1: images between 1x and 2x Pillow's MAX_IMAGE_PIXELS were decoded (decompression-bomb window)
def test_huge_dimension_image_rejected_before_decoding(client, people):
    _, h = people
    buf = io.BytesIO()
    Image.new("1", (8000, 8000)).save(buf, format="PNG")  # 64M pixels, tiny file
    assert len(buf.getvalue()) < 2 * 1024 * 1024
    r = upload(client, h["pat"], buf.getvalue())
    assert r.status_code == 422 and "dimensions" in r.json()["detail"]


# M-2: client-side logout did not revoke the token on the server
def test_logout_revokes_only_current_token(client, db):
    make_user(db, "p@example.com")
    first, second = login(client, "p@example.com"), login(client, "p@example.com")
    assert client.post("/api/auth/logout", headers=first).status_code == 200
    assert client.get("/api/auth/me", headers=first).status_code == 401
    assert client.get("/api/auth/me", headers=second).status_code == 200


# M-3: administrator-created doctors kept the admin-known temporary password indefinitely
def test_temporary_password_must_be_changed(client, people):
    _, h = people
    client.post("/api/admin/doctors", headers=h["admin"],
                json={"email": "newdoc@example.com", "full_name": "Dr New", "temporary_password": "TempPass123!"})
    dh = login(client, "newdoc@example.com", "TempPass123!")
    me = client.get("/api/auth/me", headers=dh)
    assert me.status_code == 200 and me.json()["must_change_password"] is True
    r = client.get("/api/doctors/me/profile", headers=dh)
    assert r.status_code == 403 and "change your temporary password" in r.json()["detail"]
    r = client.post("/api/auth/change-password", headers=dh,
                    json={"current_password": "TempPass123!", "new_password": "TempPass123!"})
    assert r.status_code == 400  # must actually change it
    r = client.post("/api/auth/change-password", headers=dh,
                    json={"current_password": "TempPass123!", "new_password": "OwnSecret456!"})
    assert r.status_code == 200 and r.json()["user"]["must_change_password"] is False
    new_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/doctors/me/profile", headers=new_h).status_code == 200


# M-4: ending an assignment left open appointments the doctor could no longer manage
def test_ending_assignment_cancels_open_future_appointments(client, people, db):
    users, h = people
    a = assign(client, people)
    appt = client.post("/api/appointments", headers=h["pat"],
                       json={"doctor_id": users["doc"].id, "reason": "Follow-up", **_slot()}).json()
    client.post(f"/api/admin/assignments/{a['id']}/end", headers=h["admin"], json={})
    db.expire_all()
    assert db.get(Appointment, appt["id"]).status == AppointmentStatus.cancelled


# M-5: doctors could still list appointments (names, emails, reasons) of patients no longer assigned
def test_doctor_appointment_list_scoped_to_current_assignments(client, people):
    users, h = people
    a = assign(client, people)
    client.post("/api/appointments", headers=h["pat"], json={"doctor_id": users["doc"].id, "reason": "Visit", **_slot()})
    assert client.get("/api/appointments", headers=h["doc"]).json()["total"] == 1
    client.post(f"/api/admin/assignments/{a['id']}/end", headers=h["admin"], json={})
    assert client.get("/api/appointments", headers=h["doc"]).json()["total"] == 0
    assert client.get("/api/appointments", headers=h["pending_doc"]).status_code == 403


# L-1: patients could cancel appointments that had already taken place
def test_patient_cannot_cancel_past_appointment(client, people, db):
    users, h = people
    assign(client, people)
    past = Appointment(patient_id=users["pat"].id, doctor_id=users["doc"].id, reason="Past",
                       scheduled_at=datetime.now(timezone.utc) - timedelta(days=1), status=AppointmentStatus.confirmed)
    db.add(past)
    db.commit()
    assert client.patch(f"/api/appointments/{past.id}", headers=h["pat"], json={"status": "cancelled"}).status_code == 409
    assert client.patch(f"/api/appointments/{past.id}", headers=h["doc"], json={"status": "completed"}).status_code == 200


# L-2: validation errors echoed submitted values (including passwords) back in the response
def test_validation_errors_do_not_echo_input(client):
    r = client.post("/api/auth/register", json={"email": "x@example.com", "password": "secretpw", "full_name": "Xavier"})
    assert r.status_code == 422
    assert "secretpw" not in r.text and r.json()["detail"][0]["loc"][-1] == "password"


# L-3: an unreadable stored file or an unexpected model error produced an unhandled 500
def test_corrupted_stored_image_records_failed_analysis(client, people, db, monkeypatch):
    from app.routes import xrays as xrays_routes
    from app.services import storage
    _, h = people
    xid = upload(client, h["pat"]).json()["id"]
    storage.path_for(db.get(XrayUpload, xid).stored_filename).write_bytes(b"corrupted")

    class ReadyService:
        def status(self):
            from ai.inference.service import ModelStatus
            return ModelStatus("ready", model_name="Test double", model_version="t", score_type="sigmoid", labels=["A"])

        def predict(self, image):  # never reached for unreadable files
            raise AssertionError

    monkeypatch.setattr(xrays_routes, "get_model_service", lambda: ReadyService())
    r = client.post(f"/api/xrays/{xid}/analyze", headers=h["pat"])
    assert r.status_code == 201 and r.json()["status"] == "failed" and r.json()["findings"] == []


def test_unexpected_inference_error_is_recorded_not_crashed(client, people, monkeypatch):
    from app.routes import xrays as xrays_routes
    _, h = people
    xid = upload(client, h["pat"]).json()["id"]

    class BrokenService:
        def status(self):
            from ai.inference.service import ModelStatus
            return ModelStatus("ready", model_name="Test double", model_version="t", score_type="sigmoid", labels=["A"])

        def predict(self, image):
            raise RuntimeError("CUDA out of memory (simulated)")

    monkeypatch.setattr(xrays_routes, "get_model_service", lambda: BrokenService())
    r = client.post(f"/api/xrays/{xid}/analyze", headers=h["pat"])
    assert r.status_code == 201 and r.json()["status"] == "failed"
    assert "CUDA" not in r.json()["error_message"]  # internal details are logged, not shown


# M-6: weights were loaded without a pinned checksum when weights_sha256 was omitted
def test_model_requires_pinned_checksum(tmp_path):
    from app.services.ai import XrayModelService
    weights = tmp_path / "w.pt"
    weights.write_bytes(b"not really weights")
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"enabled": True, "backend": "checkpoint", "weights_path": str(weights)}))
    status = XrayModelService(cfg).status()
    assert status.state == "error" and "weights_sha256" in status.reason


def test_corrupted_weights_with_matching_checksum_report_error(tmp_path):
    pytest.importorskip("torch")
    import hashlib

    from app.services.ai import XrayModelService
    weights = tmp_path / "w.pt"
    weights.write_bytes(b"\x00garbage\x01" * 100)
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"enabled": True, "backend": "torchxrayvision", "weights_path": str(weights),
                               "weights_sha256": hashlib.sha256(weights.read_bytes()).hexdigest()}))
    status = XrayModelService(cfg).status()
    assert status.state == "error" and "Failed to load" in status.reason


def test_incompatible_state_dict_reports_error(tmp_path):
    torch = pytest.importorskip("torch")
    import hashlib

    from app.services.ai import XrayModelService
    weights = tmp_path / "w.pt"
    torch.save({"architecture": "densenet121_grayscale", "labels": ["A"], "state_dict": {"bogus": torch.zeros(1)}}, weights)
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"enabled": True, "backend": "checkpoint", "weights_path": str(weights),
                               "weights_sha256": hashlib.sha256(weights.read_bytes()).hexdigest()}))
    status = XrayModelService(cfg).status()
    assert status.state == "error"


# Ensures every AI result is linked to the image it was computed from
def test_analysis_linked_to_requested_image(client, people, db):
    _, h = people
    first = upload(client, h["pat"]).json()["id"]
    second = upload(client, h["pat"]).json()["id"]
    db.add(AnalysisResult(upload_id=second, status="completed", model_name="m", model_version="v",
                          score_type="sigmoid", findings=[], preprocessing={}))
    db.commit()
    assert client.get(f"/api/xrays/{first}", headers=h["pat"]).json()["analyses"] == []
    assert len(client.get(f"/api/xrays/{second}", headers=h["pat"]).json()["analyses"]) == 1


# L-4: reviews defaulted to "agree" with the AI (automation bias) — now an explicit choice is required
def test_review_requires_explicit_agreement(client, people):
    _, h = people
    assign(client, people)
    xid = upload(client, h["pat"]).json()["id"]
    r = client.post(f"/api/xrays/{xid}/reviews", headers=h["doc"], json={"findings": "abc", "impression": "def"})
    assert r.status_code == 422


def test_png_bytes_helper_still_valid():
    assert png_bytes()[:4] == b"\x89PNG"
