import json
from pathlib import Path

import pytest

from app.core.config import PROJECT_DIR
from app.models import AnalysisResult, XrayUpload
from app.tests.conftest import assign, png_bytes, upload

REAL_CONFIG = PROJECT_DIR / "ai" / "model_config.json"


def _real_weights_installed() -> bool:
    try:
        cfg = json.loads(REAL_CONFIG.read_text())
        import torch  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return bool(cfg.get("enabled")) and (PROJECT_DIR / "ai" / cfg["weights_path"]).is_file()


def test_valid_upload_is_private_and_listed(client, people, db):
    _, h = people
    r = upload(client, h["pat"], filename="../../etc/passwd.png")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "uploaded" and body["original_filename"] == "passwd.png"
    stored = db.get(XrayUpload, body["id"]).stored_filename
    assert ".." not in stored and stored.endswith(".png") and len(stored) == 36

    listing = client.get("/api/xrays", headers=h["pat"]).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == body["id"]
    assert client.get("/api/xrays", headers=h["pat2"]).json()["total"] == 0

    img = client.get(f"/api/xrays/{body['id']}/image", headers=h["pat"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert "no-store" in img.headers["cache-control"]
    assert client.get(f"/api/xrays/{body['id']}/image").status_code == 401
    assert client.get(f"/api/xrays/{body['id']}/image", headers=h["pat2"]).status_code == 404
    assert client.get(f"/api/xrays/{body['id']}", headers=h["pat2"]).status_code == 404


def test_no_public_static_route_for_uploads(client, people, db):
    _, h = people
    xid = upload(client, h["pat"]).json()["id"]
    stored = db.get(XrayUpload, xid).stored_filename
    for path in (f"/storage/xrays/{stored}", f"/uploads/{stored}", f"/static/{stored}", f"/{stored}"):
        assert client.get(path).status_code == 404


def test_invalid_file_rejected(client, people):
    _, h = people
    r = client.post("/api/xrays", files={"file": ("fake.png", b"%PDF-1.4 not an image", "image/png")}, headers=h["pat"])
    assert r.status_code == 415
    r = client.post("/api/xrays", files={"file": ("empty.png", b"", "image/png")}, headers=h["pat"])
    assert r.status_code == 422
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("L", (300, 300)).save(buf, format="GIF")
    r = client.post("/api/xrays", files={"file": ("x.gif", buf.getvalue(), "image/gif")}, headers=h["pat"])
    assert r.status_code == 415
    r = upload(client, h["pat"], png_bytes((32, 32)))
    assert r.status_code == 422


def test_oversized_upload_rejected(client, people):
    _, h = people
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024 + 10)  # MAX_UPLOAD_MB=2 in tests
    r = client.post("/api/xrays", files={"file": ("big.png", big, "image/png")}, headers=h["pat"])
    assert r.status_code == 413


def test_exif_metadata_is_stripped(client, people, db, tmp_path):
    import io

    from PIL import Image

    from app.services import storage
    _, h = people
    img = Image.new("L", (300, 300), 128)
    exif = Image.Exif()
    exif[0x010E] = "Patient Name Here"  # ImageDescription
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    xid = client.post("/api/xrays", files={"file": ("x.jpg", buf.getvalue(), "image/jpeg")}, headers=h["pat"]).json()["id"]
    data = storage.path_for(db.get(XrayUpload, xid).stored_filename).read_bytes()
    assert b"Patient Name Here" not in data


def test_patient_can_delete_unreviewed_upload(client, people):
    _, h = people
    xid = upload(client, h["pat"]).json()["id"]
    assert client.delete(f"/api/xrays/{xid}", headers=h["pat2"]).status_code == 404
    assert client.delete(f"/api/xrays/{xid}", headers=h["pat"]).status_code == 204
    assert client.get(f"/api/xrays/{xid}", headers=h["pat"]).status_code == 404


def test_model_not_configured_returns_503_and_records_nothing(client, people, db):
    _, h = people
    status = client.get("/api/ai/status", headers=h["pat"]).json()
    assert status["available"] is False and status["state"] == "not_configured"
    xid = upload(client, h["pat"]).json()["id"]
    r = client.post(f"/api/xrays/{xid}/analyze", headers=h["pat"])
    assert r.status_code == 503 and "Model not configured" in r.json()["detail"]
    assert db.query(AnalysisResult).count() == 0
    detail = client.get(f"/api/xrays/{xid}", headers=h["pat"]).json()
    assert detail["analyses"] == [] and detail["latest_analysis"] is None
    assert client.post(f"/api/xrays/{xid}/analyze", headers=h["pat2"]).status_code == 404


def test_model_service_reports_missing_weights(tmp_path):
    from app.services.ai import XrayModelService
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"enabled": True, "backend": "torchxrayvision", "weights_path": "does/not/exist.pt"}))
    status = XrayModelService(cfg).status()
    assert status.state == "not_configured" and "not found" in status.reason


def test_model_service_rejects_checksum_mismatch(tmp_path):
    from app.services.ai import XrayModelService
    weights = Path(__file__).resolve()  # any existing file; checksum will not match
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"enabled": True, "backend": "torchxrayvision",
                               "weights_path": str(weights), "weights_sha256": "0" * 64}))
    assert XrayModelService(cfg).status().state == "error"


def test_model_unavailable_predict_raises(tmp_path):
    from app.services.ai import ModelUnavailable, XrayModelService
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"enabled": False}))
    with pytest.raises(ModelUnavailable):
        XrayModelService(cfg).predict(None)


@pytest.mark.skipif(not _real_weights_installed(), reason="Genuine model weights are not installed")
def test_real_model_inference(client, people, db, monkeypatch):
    """Runs the genuine pretrained model on a synthetic image. Asserts structure, not clinical values."""
    from app.routes import xrays as xrays_routes
    from app.services.ai import XrayModelService

    service = XrayModelService(REAL_CONFIG)
    assert service.status().available, service.status().reason
    monkeypatch.setattr(xrays_routes, "get_model_service", lambda: service)

    users, h = people
    assign(client, people)
    xid = upload(client, h["pat"]).json()["id"]
    r = client.post(f"/api/xrays/{xid}/analyze", headers=h["pat"])
    assert r.status_code == 201, r.text
    result = r.json()
    assert result["status"] == "completed"
    assert result["score_type"] == "op_norm_sigmoid" and "NOT probabilities" in result["score_description"]
    labels = {f["label"] for f in result["findings"]}
    assert labels == set(service.status().labels)
    assert all(0.0 <= f["score"] <= 1.0 for f in result["findings"])
    assert result["preprocessing"]["image_size"] == 224
    assert result["weights_sha256"] == service.status().weights_sha256

    # assigned doctor can also request analysis; colour photographs are refused, not scored
    assert client.post(f"/api/xrays/{xid}/analyze", headers=h["doc"]).status_code == 201
    cid = upload(client, h["pat"], png_bytes(color=True)).json()["id"]
    r = client.post(f"/api/xrays/{cid}/analyze", headers=h["pat"])
    assert r.status_code == 201 and r.json()["status"] == "failed" and r.json()["findings"] == []
    assert "colour photograph" in r.json()["error_message"]
