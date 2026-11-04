from uuid import UUID

from app.modules.appointments.schemas import SyncStatus

BASE = "/api/v1/appointments"
VALID = {"title": "Consulta", "starts_at": "2026-11-05T15:00:00-03:00"}


def create(api, **over):
    r = api.client.post(BASE, json={**VALID, **over})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_normalizes_utc_without_default_duration(api):
    body = create(api)
    assert body["starts_at"] == "2026-11-05T18:00:00Z"
    assert body["ends_at"] is None  # nenhuma duração presumida
    assert body["status"] == "scheduled"
    assert body["sync_status"] == "pending"
    assert body["user_id"] == str(api.user.id)
    assert api.audit_actions(body["id"]) == ["appointment.created"]


def test_create_with_explicit_end(api):
    body = create(api, ends_at="2026-11-05T16:00:00-03:00", location="  Clínica ", description=" ")
    assert body["ends_at"] == "2026-11-05T19:00:00Z"
    assert body["location"] == "Clínica"
    assert body["description"] is None


def test_create_requires_title_and_start(api):
    r = api.client.post(BASE, json={})
    assert r.status_code == 422
    fields = {d["field"] for d in r.json()["error"]["details"]}
    assert {"body.title", "body.starts_at"} <= fields


def test_blank_title_rejected(api):
    assert api.client.post(BASE, json={**VALID, "title": "   "}).status_code == 422


def test_naive_datetime_and_date_only_rejected(api):
    naive = {**VALID, "starts_at": "2026-11-05T15:00:00"}
    assert api.client.post(BASE, json=naive).status_code == 422
    assert api.client.post(BASE, json={**VALID, "starts_at": "2026-11-05"}).status_code == 422
    assert api.client.post(BASE, json={**VALID, "starts_at": "amanhã"}).status_code == 422


def test_end_must_be_after_start(api):
    for end in ("2026-11-05T15:00:00-03:00", "2026-11-05T14:00:00-03:00"):
        r = api.client.post(BASE, json={**VALID, "ends_at": end})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"


def test_user_id_in_body_is_rejected(api, user_b):
    r = api.client.post(BASE, json={**VALID, "user_id": str(user_b.id)})
    assert r.status_code == 422


def test_get_and_not_found(api):
    created = create(api)
    assert api.client.get(f"{BASE}/{created['id']}").json() == created
    r = api.client.get(f"{BASE}/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert api.client.get(f"{BASE}/nao-e-uuid").status_code == 422


def test_patch_updates_and_clears_with_null(api):
    created = create(api, description="x", location="y")
    api.clock.advance(minutes=1)
    r = api.client.patch(f"{BASE}/{created['id']}", json={"title": "Novo", "location": None})
    body = r.json()
    assert r.status_code == 200
    assert (body["title"], body["location"], body["description"]) == ("Novo", None, "x")
    assert body["updated_at"] > created["updated_at"]
    entry = api.audit.entries[-1]
    assert entry.action == "appointment.updated"
    assert entry.changes == {
        "title": {"from": "Consulta", "to": "Novo"},
        "location": {"from": "y", "to": None},
    }


def test_patch_rejects_null_title_and_time_fields(api):
    created = create(api)
    url = f"{BASE}/{created['id']}"
    assert api.client.patch(url, json={"title": None}).status_code == 422
    assert api.client.patch(url, json={"starts_at": "2026-11-06T10:00:00Z"}).status_code == 422


def test_patch_without_change_is_not_audited(api):
    created = create(api)
    api.client.patch(f"{BASE}/{created['id']}", json={"title": "Consulta"})
    assert api.audit_actions(created["id"]) == ["appointment.created"]


def test_reschedule_without_end_clears_previous_end_and_audits(api):
    created = create(api, ends_at="2026-11-05T16:00:00-03:00")
    r = api.client.post(
        f"{BASE}/{created['id']}/reschedule", json={"starts_at": "2026-11-06T10:00:00-03:00"}
    )
    body = r.json()
    assert r.status_code == 200
    assert body["starts_at"] == "2026-11-06T13:00:00Z" and body["ends_at"] is None
    entry = api.audit.entries[-1]
    assert entry.action == "appointment.rescheduled"
    assert entry.changes["starts_at"]["from"] == "2026-11-05T18:00:00Z"


def test_reschedule_validates_range(api):
    created = create(api)
    r = api.client.post(
        f"{BASE}/{created['id']}/reschedule",
        json={"starts_at": "2026-11-06T10:00:00Z", "ends_at": "2026-11-06T09:00:00Z"},
    )
    assert r.status_code == 422


def test_change_marks_synced_item_for_resync(api):
    created = create(api)
    # GP-06 marcaria como synced; simulado direto no fake do repositório.
    repo = api.stores.appointments
    row = repo.get(api.user.id, UUID(created["id"]))
    repo._rows[row.id] = row.model_copy(update={"sync_status": SyncStatus.SYNCED})
    r = api.client.patch(f"{BASE}/{created['id']}", json={"title": "Outro"})
    assert r.json()["sync_status"] == "pending"


def test_cancel_is_state_change_with_audit_and_blocks_edits(api):
    created = create(api)
    r = api.client.post(f"{BASE}/{created['id']}/cancel", json={"reason": "Doente"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    # Não é exclusão física.
    assert api.client.get(f"{BASE}/{created['id']}").status_code == 200
    entry = api.audit.entries[-1]
    assert entry.action == "appointment.cancelled"
    assert entry.changes["reason"] == "Doente"
    assert entry.changes["status"] == {"from": "scheduled", "to": "cancelled"}
    resched = {"starts_at": "2026-12-01T10:00:00Z"}
    for call in (
        api.client.patch(f"{BASE}/{created['id']}", json={"title": "x"}),
        api.client.post(f"{BASE}/{created['id']}/reschedule", json=resched),
    ):
        assert call.status_code == 409 and call.json()["error"]["code"] == "conflict"


def test_cancel_without_body_and_repeated_cancel_is_noop(api):
    created = create(api)
    assert api.client.post(f"{BASE}/{created['id']}/cancel").status_code == 200
    assert api.client.post(f"{BASE}/{created['id']}/cancel").status_code == 200
    assert api.audit_actions(created["id"]).count("appointment.cancelled") == 1


def test_list_filters_order_and_pagination(api):
    for day in (9, 7, 8):
        create(api, title=f"d{day}", starts_at=f"2026-11-0{day}T10:00:00Z")
    last = create(api, title="cancelado", starts_at="2026-11-10T10:00:00Z")
    api.client.post(f"{BASE}/{last['id']}/cancel")

    r = api.client.get(BASE, params={"limit": 2}).json()
    assert [i["title"] for i in r["items"]] == ["d7", "d8"]
    assert (r["total"], r["limit"], r["offset"]) == (4, 2, 0)

    r = api.client.get(BASE, params={"limit": 2, "offset": 2}).json()
    assert [i["title"] for i in r["items"]] == ["d9", "cancelado"]

    r = api.client.get(BASE, params={"status": "scheduled"}).json()
    assert r["total"] == 3

    window = {"starts_at_from": "2026-11-08T00:00:00Z", "starts_at_to": "2026-11-09T10:00:00Z"}
    r = api.client.get(BASE, params=window).json()
    assert [i["title"] for i in r["items"]] == ["d8"]  # intervalo semiaberto [from, to)


def test_list_invalid_params(api):
    assert api.client.get(BASE, params={"limit": 0}).status_code == 422
    assert api.client.get(BASE, params={"limit": 201}).status_code == 422
    assert api.client.get(BASE, params={"offset": -1}).status_code == 422
    inverted = {"starts_at_from": "2026-11-09T00:00:00Z", "starts_at_to": "2026-11-08T00:00:00Z"}
    assert api.client.get(BASE, params=inverted).status_code == 422


def test_isolation_between_users(api, user_b):
    mine = create(api)
    api.as_user(user_b)
    url = f"{BASE}/{mine['id']}"
    assert api.client.get(url).status_code == 404
    assert api.client.patch(url, json={"title": "x"}).status_code == 404
    assert api.client.post(f"{url}/cancel").status_code == 404
    resched = {"starts_at": "2026-12-01T10:00:00Z"}
    assert api.client.post(f"{url}/reschedule", json=resched).status_code == 404
    assert api.client.get(BASE).json()["total"] == 0
