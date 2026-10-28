from datetime import datetime, timedelta, timezone

from app.tests.conftest import assign


def _slot(days=2, hour=10, minute=0):
    d = (datetime.now(timezone.utc) + timedelta(days=days)).date()
    return {"date": d.isoformat(), "start_time": f"{hour:02d}:{minute:02d}"}


def _book(client, people, patient="pat", doctor="doc", **slot):
    users, h = people
    body = {"doctor_id": users[doctor].id, "reason": "Follow-up on X-ray", **(slot or _slot())}
    return client.post("/api/appointments", json=body, headers=h[patient])


def test_booking_requires_assignment(client, people):
    r = _book(client, people)
    assert r.status_code == 403


def test_valid_booking_and_lifecycle(client, people):
    users, h = people
    assign(client, people)
    r = _book(client, people)
    assert r.status_code == 201, r.text
    appt = r.json()
    assert appt["status"] == "requested" and appt["doctor"]["id"] == users["doc"].id

    assert client.get("/api/appointments", headers=h["pat"]).json()["total"] == 1
    assert client.get("/api/appointments", headers=h["doc"]).json()["total"] == 1
    assert client.get("/api/appointments", headers=h["doc2"]).json()["total"] == 0
    assert client.get("/api/appointments", headers=h["pat2"]).json()["total"] == 0
    assert client.get("/api/appointments", headers=h["admin"]).json()["total"] == 1

    url = f"/api/appointments/{appt['id']}"
    assert client.patch(url, headers=h["doc2"], json={"status": "confirmed"}).status_code == 404
    assert client.patch(url, headers=h["pat2"], json={"status": "cancelled"}).status_code == 404
    assert client.patch(url, headers=h["pat"], json={"status": "confirmed"}).status_code == 409
    r = client.patch(url, headers=h["doc"], json={"status": "confirmed", "note": "See you then"})
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    assert client.patch(url, headers=h["doc"], json={"status": "completed"}).status_code == 409  # future
    assert client.patch(url, headers=h["pat"], json={"status": "cancelled"}).json()["status"] == "cancelled"


def test_invalid_dates_rejected(client, people):
    assign(client, people)
    yesterday = _slot(days=-1)
    assert _book(client, people, **yesterday).status_code == 422
    assert _book(client, people, **_slot(days=400)).status_code == 422
    assert _book(client, people, **_slot(minute=7)).status_code == 422
    users, h = people
    r = client.post("/api/appointments", headers=h["pat"],
                    json={"doctor_id": users["doc"].id, "reason": "x", **_slot()})
    assert r.status_code == 422  # reason too short


def test_conflicting_bookings_rejected(client, people):
    assign(client, people, "pat", "doc")
    assign(client, people, "pat2", "doc")
    assert _book(client, people, **_slot(hour=10)).status_code == 201
    r = _book(client, people, patient="pat2", **_slot(hour=10, minute=15))  # overlaps 10:00-10:30
    assert r.status_code == 409
    assert _book(client, people, patient="pat2", **_slot(hour=10, minute=30)).status_code == 201


def test_outside_availability_rejected(client, people, db):
    from datetime import time

    from app.models import DoctorAvailability
    users, h = people
    assign(client, people)
    profile = users["doc"].doctor_profile
    db.query(DoctorAvailability).filter_by(profile_id=profile.id).delete()
    target = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    db.add(DoctorAvailability(profile_id=profile.id, weekday=target.weekday(), start_time=time(9), end_time=time(12)))
    db.commit()
    ok = {"date": target.isoformat(), "start_time": "09:30"}
    bad = {"date": target.isoformat(), "start_time": "11:45"}  # would end 12:15
    assert _book(client, people, **bad).status_code == 422
    assert _book(client, people, **ok).status_code == 201


def test_admin_can_cancel(client, people):
    _, h = people
    assign(client, people)
    aid = _book(client, people).json()["id"]
    assert client.patch(f"/api/appointments/{aid}", headers=h["admin"], json={"status": "confirmed"}).status_code == 409
    assert client.patch(f"/api/appointments/{aid}", headers=h["admin"], json={"status": "cancelled"}).status_code == 200
