from app.models import UserRole
from app.tests.conftest import assign, login, make_user, upload

PROFILE = {"specialty": "Cardiology", "license_number": "LIC-999", "years_experience": 4,
           "bio": "Synthetic", "clinic_location": "Ward 1"}


def test_doctor_onboarding_and_approval_flow(client, people):
    users, h = people
    r = client.post("/api/admin/doctors", headers=h["admin"],
                    json={"email": "newdoc@example.com", "full_name": "Dr New", "temporary_password": "TempPass123!"})
    assert r.status_code == 201
    profile_id = r.json()["profile"]["id"]
    dh = login(client, "newdoc@example.com", "TempPass123!")
    # first sign-in: the temporary password must be replaced before anything else
    assert client.get("/api/doctors/me/profile", headers=dh).status_code == 403
    r = client.post("/api/auth/change-password", headers=dh,
                    json={"current_password": "TempPass123!", "new_password": "DoctorOwn456!"})
    assert r.status_code == 200
    dh = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # draft profile: not in directory, cannot access clinical endpoints
    assert client.get("/api/doctor/patients", headers=dh).status_code == 403
    assert client.post("/api/doctors/me/profile/submit", headers=dh).status_code == 422  # incomplete
    assert client.put("/api/doctors/me/profile", headers=dh, json=PROFILE).status_code == 200
    slots = {"slots": [{"weekday": 0, "start_time": "09:00", "end_time": "12:00"}]}
    assert client.put("/api/doctors/me/availability", headers=dh, json=slots).status_code == 200
    r = client.post("/api/doctors/me/profile/submit", headers=dh)
    assert r.status_code == 200 and r.json()["status"] == "pending"

    ids = [d["user_id"] for d in client.get("/api/doctors", headers=h["pat"]).json()["items"]]
    assert r.json()["user_id"] not in ids

    # rejection requires a reason
    assert client.post(f"/api/admin/doctors/{profile_id}/reject", headers=h["admin"], json={}).status_code == 422
    assert client.post(f"/api/admin/doctors/{profile_id}/approve", headers=h["pat"], json={}).status_code == 403
    r = client.post(f"/api/admin/doctors/{profile_id}/approve", headers=h["admin"], json={})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert client.post(f"/api/admin/doctors/{profile_id}/approve", headers=h["admin"], json={}).status_code == 409

    directory = client.get("/api/doctors", headers=h["pat"]).json()["items"]
    entry = next(d for d in directory if d["full_name"] == "Dr New")
    assert "license_number" not in entry
    assert client.get("/api/doctor/patients", headers=dh).status_code == 200


def test_reject_doctor_then_resubmit(client, people):
    users, h = people
    profile_id = client.get("/api/admin/doctors?status=pending", headers=h["admin"]).json()[0]["profile"]["id"]
    r = client.post(f"/api/admin/doctors/{profile_id}/reject", headers=h["admin"], json={"note": "License unclear"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    ph = h["pending_doc"]
    assert client.get("/api/doctors/me/profile", headers=ph).json()["review_note"] == "License unclear"
    assert client.post("/api/doctors/me/profile/submit", headers=ph).json()["status"] == "pending"


def test_directory_shows_only_approved_doctors(client, people):
    users, h = people
    items = client.get("/api/doctors", headers=h["pat"]).json()["items"]
    ids = {d["user_id"] for d in items}
    assert users["doc"].id in ids and users["doc2"].id in ids
    assert users["pending_doc"].id not in ids
    assert client.get(f"/api/doctors/{users['pending_doc'].id}", headers=h["pat"]).status_code == 404
    assert client.get("/api/doctors").status_code == 401


def test_public_registration_cannot_create_doctor(client):
    r = client.post("/api/auth/register",
                    json={"email": "x@example.com", "password": "Sup3rSecret!", "full_name": "Xavier", "role": "doctor"})
    assert r.json()["user"]["role"] == "patient"


def test_assignment_request_duplicate_and_approval(client, people):
    users, h = people
    body = {"doctor_id": users["doc"].id, "reason": "Cough"}
    r = client.post("/api/assignments", json=body, headers=h["pat"])
    assert r.status_code == 201 and r.json()["status"] == "pending"
    aid = r.json()["id"]
    assert client.post("/api/assignments", json=body, headers=h["pat"]).status_code == 409

    # doctor cannot see the patient until approved
    assert client.get(f"/api/doctor/patients/{users['pat'].id}", headers=h["doc"]).status_code == 404
    assert client.post(f"/api/admin/assignments/{aid}/approve", headers=h["doc"], json={}).status_code == 403
    r = client.post(f"/api/admin/assignments/{aid}/approve", headers=h["admin"], json={})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert client.post("/api/assignments", json=body, headers=h["pat"]).status_code == 409

    patients = client.get("/api/doctor/patients", headers=h["doc"]).json()
    assert [p["patient"]["id"] for p in patients] == [users["pat"].id]
    assert client.get("/api/doctor/patients", headers=h["doc2"]).json() == []
    assert client.get("/api/assignments/mine", headers=h["pat"]).json()[0]["status"] == "approved"


def test_assignment_rejection_and_cancel(client, people):
    users, h = people
    aid = client.post("/api/assignments", json={"doctor_id": users["doc"].id}, headers=h["pat"]).json()["id"]
    assert client.post(f"/api/admin/assignments/{aid}/reject", headers=h["admin"], json={"note": "Full"}).json()["status"] == "rejected"
    # after rejection the patient may request again
    aid2 = client.post("/api/assignments", json={"doctor_id": users["doc"].id}, headers=h["pat"]).json()["id"]
    assert client.post(f"/api/assignments/{aid2}/cancel", headers=h["pat2"]).status_code == 404  # not theirs
    assert client.post(f"/api/assignments/{aid2}/cancel", headers=h["pat"]).json()["status"] == "cancelled"


def test_cannot_request_unapproved_or_non_doctor(client, people):
    users, h = people
    assert client.post("/api/assignments", json={"doctor_id": users["pending_doc"].id}, headers=h["pat"]).status_code == 404
    assert client.post("/api/assignments", json={"doctor_id": users["pat2"].id}, headers=h["pat"]).status_code == 404
    assert client.post("/api/assignments", json={"doctor_id": users["doc"].id}, headers=h["doc2"]).status_code == 403


def test_doctor_access_restricted_to_assigned_patients(client, people):
    users, h = people
    assign(client, people, "pat", "doc")
    xid = upload(client, h["pat"]).json()["id"]
    xid2 = upload(client, h["pat2"]).json()["id"]

    assert client.get(f"/api/xrays/{xid}", headers=h["doc"]).status_code == 200
    assert client.get(f"/api/xrays/{xid}/image", headers=h["doc"]).status_code == 200
    assert client.get(f"/api/xrays/{xid2}", headers=h["doc"]).status_code == 404
    assert client.get(f"/api/xrays/{xid}", headers=h["doc2"]).status_code == 404
    assert client.get(f"/api/doctor/patients/{users['pat2'].id}", headers=h["doc"]).status_code == 404
    assert client.post(f"/api/doctor/patients/{users['pat2'].id}/notes", headers=h["doc"], json={"body": "x"}).status_code == 404
    # administrators manage workflow but do not read clinical images
    assert client.get(f"/api/xrays/{xid}", headers=h["admin"]).status_code == 404


def test_ending_assignment_revokes_access(client, people):
    users, h = people
    a = assign(client, people)
    xid = upload(client, h["pat"]).json()["id"]
    assert client.get(f"/api/xrays/{xid}", headers=h["doc"]).status_code == 200
    assert client.post(f"/api/admin/assignments/{a['id']}/end", headers=h["admin"], json={}).status_code == 200
    assert client.get(f"/api/xrays/{xid}", headers=h["doc"]).status_code == 404


def test_doctor_notes_and_reviews(client, people):
    users, h = people
    assign(client, people)
    xid = upload(client, h["pat"]).json()["id"]
    r = client.post(f"/api/doctor/patients/{users['pat'].id}/notes", headers=h["doc"],
                    json={"body": "Shared follow-up note", "visible_to_patient": True})
    assert r.status_code == 201
    client.post(f"/api/doctor/patients/{users['pat'].id}/notes", headers=h["doc"], json={"body": "Internal note"})
    record = client.get("/api/patients/me/record", headers=h["pat"]).json()
    assert [n["body"] for n in record["notes"]] == ["Shared follow-up note"]

    review = {"findings": "Clear lung fields", "impression": "No acute process", "ai_agreement": "not_applicable"}
    r = client.post(f"/api/xrays/{xid}/reviews", headers=h["doc"], json=review)
    assert r.status_code == 201 and r.json()["status"] == "draft"
    rid = r.json()["id"]
    # drafts are hidden from the patient
    assert client.get(f"/api/xrays/{xid}", headers=h["pat"]).json()["reviews"] == []
    assert client.put(f"/api/xrays/reviews/{rid}", headers=h["doc2"], json=review).status_code == 404
    r = client.put(f"/api/xrays/reviews/{rid}", headers=h["doc"], json={**review, "status": "final"})
    assert r.status_code == 200
    assert client.put(f"/api/xrays/reviews/{rid}", headers=h["doc"], json=review).status_code == 409
    assert len(client.get(f"/api/xrays/{xid}", headers=h["pat"]).json()["reviews"]) == 1
    assert client.post(f"/api/xrays/{xid}/reviews", headers=h["pat"], json=review).status_code == 403
    # finalised record cannot be deleted by the patient
    assert client.delete(f"/api/xrays/{xid}", headers=h["pat"]).status_code == 409


def test_admin_user_status_and_audit(client, people):
    users, h = people
    r = client.patch(f"/api/admin/users/{users['pat2'].id}/status", headers=h["admin"], json={"status": "disabled"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=h["pat2"]).status_code == 401  # token revoked
    assert client.patch(f"/api/admin/users/{users['admin'].id}/status", headers=h["admin"],
                        json={"status": "disabled"}).status_code == 409
    events = client.get("/api/admin/audit", headers=h["admin"]).json()["items"]
    assert any(e["action"] == "user.disabled" for e in events)
    stats = client.get("/api/admin/stats", headers=h["admin"]).json()
    assert stats["patients"] == 2 and stats["doctors_pending"] == 1


def test_pending_doctor_cannot_access_clinical_endpoints(client, db, people):
    _, h = people
    assert client.get("/api/doctor/patients", headers=h["pending_doc"]).status_code == 403
    assert client.get("/api/doctor/review-queue", headers=h["pending_doc"]).status_code == 403
    make_user(db, "other-admin@example.com", UserRole.admin)
