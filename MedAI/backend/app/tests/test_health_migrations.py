from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import BACKEND_DIR


def test_health_endpoints(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    r = client.get("/api/health/ready")
    assert r.status_code == 200 and r.json()["database"] is True
    assert client.get("/openapi.json").status_code == 200


def test_security_headers_and_cors(client):
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_alembic_migrations_upgrade_and_downgrade(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migrate.db').as_posix()}"
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert {"users", "doctor_profiles", "assignments", "appointments", "xray_uploads",
            "analysis_results", "clinical_reviews", "clinical_notes", "audit_events"} <= tables
    command.downgrade(cfg, "base")
    assert set(inspect(create_engine(url)).get_table_names()) <= {"alembic_version"}


def test_migrations_preserve_existing_data(tmp_path):
    """Regression (audit C-1): on SQLite, upgrading 0001 -> 0002 rebuilt `users` with foreign keys
    enabled, and ON DELETE CASCADE wiped every dependent table. Data must survive upgrade and downgrade."""
    import sqlite3

    db_file = tmp_path / "data.db"
    url = f"sqlite:///{db_file.as_posix()}"
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["database_url"] = url
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "0001")

    con = sqlite3.connect(db_file)
    con.executescript("""
        INSERT INTO users (id, email, password_hash, full_name, role, status, token_version, created_at, updated_at)
        VALUES (1, 'p@example.com', 'x', 'Patient', 'patient', 'active', 0, '2026-01-01', '2026-01-01'),
               (2, 'd@example.com', 'x', 'Doctor', 'doctor', 'active', 0, '2026-01-01', '2026-01-01');
        INSERT INTO doctor_profiles (id, user_id, specialty, license_number, years_experience, bio, clinic_location,
                                     status, created_at, updated_at)
        VALUES (1, 2, 'Radiology', 'L-1', 3, '', '', 'approved', '2026-01-01', '2026-01-01');
        INSERT INTO assignments (id, patient_id, doctor_id, status, request_reason, created_at, updated_at)
        VALUES (1, 1, 2, 'approved', '', '2026-01-01', '2026-01-01');
        INSERT INTO xray_uploads (id, owner_id, original_filename, stored_filename, content_type, size_bytes, width,
                                  height, sha256, status, created_at, updated_at)
        VALUES (1, 1, 'a.png', 'aaaa.png', 'image/png', 1, 64, 64, 'h', 'uploaded', '2026-01-01', '2026-01-01');
    """)
    con.commit()
    con.close()

    def counts():
        c = sqlite3.connect(db_file)
        try:
            return {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                    for t in ("users", "doctor_profiles", "assignments", "xray_uploads")}
        finally:
            c.close()

    expected = {"users": 2, "doctor_profiles": 1, "assignments": 1, "xray_uploads": 1}
    command.upgrade(cfg, "head")
    assert counts() == expected
    command.downgrade(cfg, "0001")
    assert counts() == expected
    command.upgrade(cfg, "head")
    assert counts() == expected
