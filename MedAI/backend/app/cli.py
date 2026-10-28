"""
Command-line administration tasks (requires shell access to the server, never exposed over HTTP).

    python -m app.cli create-admin --email admin@example.com --name "Site Admin"
    python -m app.cli seed-demo           # development only: synthetic demo accounts
    python -m app.cli model-status
    python -m app.cli migrate             # back up SQLite (if migrations are pending), then upgrade
    python -m app.cli backup-db           # copy of the SQLite database into backend/backups/
"""
import argparse
import getpass
import os
import sys
from datetime import date, time

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models import (
    Assignment, AssignmentStatus, DoctorAvailability, DoctorProfile, DoctorProfileStatus, User, UserRole,
)
from app.schemas import _validate_password


def _read_password(env_var: str) -> str:
    password = os.environ.get(env_var)
    if password:
        return password
    if not sys.stdin.isatty():
        sys.exit(f"No TTY available: set the {env_var} environment variable instead.")
    first = getpass.getpass("Password (min 10 chars, letters + numbers): ")
    if first != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    return first


def create_admin(email: str, name: str) -> None:
    password = _read_password("MEDAI_ADMIN_PASSWORD")
    try:
        _validate_password(password)
    except ValueError as exc:
        sys.exit(str(exc))
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(func.lower(User.email) == email.lower())):
            sys.exit(f"A user with email {email} already exists.")
        db.add(User(email=email.lower(), full_name=name, role=UserRole.admin, password_hash=hash_password(password)))
        db.commit()
    print(f"Administrator {email} created.")


DEMO_PASSWORD = "DemoPass123!"
DEMO_USERS = [
    # (email, name, role) - all synthetic; no real people or patient data
    ("admin@medai.example.com", "Demo Administrator", UserRole.admin),
    ("dr.rao@medai.example.com", "Dr. Ananya Rao", UserRole.doctor),
    ("dr.mehta@medai.example.com", "Dr. Vikram Mehta", UserRole.doctor),
    ("dr.new@medai.example.com", "Dr. Sam Pending", UserRole.doctor),
    ("patient@medai.example.com", "Demo Patient", UserRole.patient),
    ("patient2@medai.example.com", "Second Demo Patient", UserRole.patient),
]


def seed_demo() -> None:
    settings = get_settings()
    if settings.is_production:
        sys.exit("Refusing to seed demo accounts when APP_ENV=production.")
    with SessionLocal() as db:
        if db.scalar(select(func.count(User.id))):
            print("Database already contains users; demo seed skipped (nothing was changed).")
            return
        users = {}
        for email, name, role in DEMO_USERS:
            u = User(email=email, full_name=name, role=role, password_hash=hash_password(DEMO_PASSWORD))
            if role == UserRole.patient:
                u.date_of_birth = date(1990, 1, 1)
            db.add(u)
            users[email] = u
        db.flush()

        rao = DoctorProfile(user_id=users["dr.rao@medai.example.com"].id, specialty="Radiology", license_number="DEMO-RAD-001",
                            years_experience=12, bio="Synthetic demo profile: thoracic imaging.",
                            clinic_location="Demo Hospital, Block A", status=DoctorProfileStatus.approved)
        mehta = DoctorProfile(user_id=users["dr.mehta@medai.example.com"].id, specialty="Pulmonology",
                              license_number="DEMO-PUL-002", years_experience=8,
                              bio="Synthetic demo profile: respiratory medicine.",
                              clinic_location="Demo Hospital, Block B", status=DoctorProfileStatus.approved)
        pending = DoctorProfile(user_id=users["dr.new@medai.example.com"].id, specialty="General Medicine",
                                license_number="DEMO-GEN-003", years_experience=3,
                                bio="Synthetic demo profile awaiting approval.", status=DoctorProfileStatus.pending,
                                submitted_at=utcnow())
        db.add_all([rao, mehta, pending])
        db.flush()
        for profile in (rao, mehta):
            for weekday in range(0, 5):  # Monday-Friday, 09:00-13:00 and 14:00-17:00 clinic time
                db.add(DoctorAvailability(profile_id=profile.id, weekday=weekday, start_time=time(9), end_time=time(13)))
                db.add(DoctorAvailability(profile_id=profile.id, weekday=weekday, start_time=time(14), end_time=time(17)))
        db.add(Assignment(patient_id=users["patient@medai.example.com"].id, doctor_id=users["dr.rao@medai.example.com"].id,
                          status=AssignmentStatus.approved, request_reason="Demo assignment",
                          decided_by_id=users["admin@medai.example.com"].id, decided_at=utcnow()))
        db.add(Assignment(patient_id=users["patient2@medai.example.com"].id, doctor_id=users["dr.mehta@medai.example.com"].id,
                          status=AssignmentStatus.pending, request_reason="Persistent cough (synthetic demo request)"))
        db.commit()
    print("Demo data created. All demo accounts use the password:", DEMO_PASSWORD)
    for email, _, role in DEMO_USERS:
        print(f"  {role.value:8s} {email}")


def backup_db() -> str | None:
    """Consistent copy of the SQLite database (sqlite3 online-backup API). PostgreSQL: use pg_dump."""
    import sqlite3
    from datetime import datetime
    from pathlib import Path

    from sqlalchemy.engine import make_url

    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite" or not url.database or not Path(url.database).is_file():
        print("No SQLite database file to back up (for PostgreSQL use pg_dump; see docs/DEPLOYMENT.md).")
        return None
    src = Path(url.database).resolve()
    dest_dir = src.parent / "backups"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / f"{src.stem}-{datetime.now():%Y%m%d-%H%M%S}.db"
    with sqlite3.connect(src) as source, sqlite3.connect(dest) as target:
        source.backup(target)
    print(f"Database backed up to {dest}")
    return str(dest)


def migrate() -> None:
    """Apply pending Alembic migrations, backing up a SQLite database first."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    from app.db.session import engine

    backend_dir = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    if current == head:
        print(f"Database is up to date (revision {head}).")
        return
    if current is not None:
        backup_db()
    command.upgrade(cfg, "head")
    print(f"Database migrated {current or 'empty'} -> {head}.")


def model_status() -> None:
    from app.services.ai import get_model_service
    s = get_model_service().status()
    print(f"state: {s.state}\nreason: {s.reason or '-'}\nmodel: {s.model_name} {s.model_version or ''}\n"
          f"labels: {', '.join(s.labels) or '-'}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin", help="Create an administrator account")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="Administrator")
    sub.add_parser("seed-demo", help="Create synthetic demo accounts (development only)")
    sub.add_parser("model-status", help="Show whether a genuine AI model is configured")
    sub.add_parser("migrate", help="Back up SQLite (if needed) and apply database migrations")
    sub.add_parser("backup-db", help="Back up the SQLite database to backend/backups/")
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.name)
    elif args.command == "seed-demo":
        seed_demo()
    elif args.command == "migrate":
        migrate()
    elif args.command == "backup-db":
        backup_db()
    else:
        model_status()


if __name__ == "__main__":
    main()
