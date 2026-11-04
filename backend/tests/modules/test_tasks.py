BASE = "/api/v1/tasks"


def create(api, **over):
    r = api.client.post(BASE, json={"title": "Enviar orçamento", **over})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_with_all_attributes(api):
    body = create(
        api,
        description="para Ana",
        due_at="2026-11-06T09:00:00-03:00",
        priority="high",
        category="trabalho",
        sync_to_calendar=True,
    )
    assert body["status"] == "pending"
    assert body["completed_at"] is None
    assert body["due_at"] == "2026-11-06T12:00:00Z"
    assert body["priority"] == "high" and body["category"] == "trabalho"
    assert body["sync_to_calendar"] is True
    assert body["google_event_id"] is None
    assert api.audit_actions(body["id"]) == ["task.created"]


def test_defaults_do_not_infer_calendar_sync_from_due_date(api):
    body = create(api, due_at="2026-11-06T09:00:00Z")
    assert body["sync_to_calendar"] is False
    assert body["priority"] is None


def test_create_validation(api):
    assert api.client.post(BASE, json={}).status_code == 422
    assert api.client.post(BASE, json={"title": "x", "priority": "urgent"}).status_code == 422
    assert (
        api.client.post(BASE, json={"title": "x", "due_at": "2026-11-06T09:00:00"}).status_code
        == 422
    )
    assert api.client.post(BASE, json={"title": "x", "status": "completed"}).status_code == 422
    assert (
        api.client.post(
            BASE, json={"title": "x", "completed_at": "2026-11-01T00:00:00Z"}
        ).status_code
        == 422
    )


def test_patch_and_null_semantics(api):
    task = create(api, due_at="2026-11-06T09:00:00Z", priority="low", category="a")
    url = f"{BASE}/{task['id']}"
    r = api.client.patch(url, json={"due_at": None, "priority": "high"})
    body = r.json()
    assert r.status_code == 200
    assert body["due_at"] is None and body["priority"] == "high" and body["category"] == "a"
    assert api.client.patch(url, json={"title": None}).status_code == 422
    assert api.client.patch(url, json={"sync_to_calendar": None}).status_code == 422
    assert api.audit.entries[-1].action == "task.updated"


def test_complete_records_explicit_completion_instant(api):
    task = create(api)
    api.clock.advance(hours=2)
    r = api.client.post(f"{BASE}/{task['id']}/complete")
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "completed"
    assert body["completed_at"] == "2026-11-03T14:00:00Z"
    assert api.audit.entries[-1].action == "task.completed"


def test_complete_with_informed_instant_and_future_rejected(api):
    task = create(api)
    url = f"{BASE}/{task['id']}/complete"
    ok = api.client.post(url, json={"completed_at": "2026-11-02T21:00:00-03:00"})
    assert ok.json()["completed_at"] == "2026-11-03T00:00:00Z"
    other = create(api, title="outra")
    bad = api.client.post(
        f"{BASE}/{other['id']}/complete", json={"completed_at": "2026-11-04T00:00:00Z"}
    )
    assert bad.status_code == 422


def test_time_passing_never_completes(api):
    task = create(api, due_at="2026-11-03T13:00:00Z")
    api.clock.advance(days=30)
    body = api.client.get(f"{BASE}/{task['id']}").json()
    assert body["status"] == "pending" and body["completed_at"] is None


def test_complete_twice_keeps_first_instant(api):
    task = create(api)
    first = api.client.post(f"{BASE}/{task['id']}/complete").json()
    api.clock.advance(hours=1)
    second = api.client.post(f"{BASE}/{task['id']}/complete").json()
    assert second["completed_at"] == first["completed_at"]
    assert api.audit_actions(task["id"]).count("task.completed") == 1


def test_reopen_clears_completed_at(api):
    task = create(api)
    api.client.post(f"{BASE}/{task['id']}/complete")
    r = api.client.post(f"{BASE}/{task['id']}/reopen")
    assert r.status_code == 200
    assert r.json()["status"] == "pending" and r.json()["completed_at"] is None
    assert api.audit_actions(task["id"]) == ["task.created", "task.completed", "task.reopened"]
    # reabrir pendente é no-op
    api.client.post(f"{BASE}/{task['id']}/reopen")
    assert api.audit_actions(task["id"]).count("task.reopened") == 1


def test_cancelled_task_conflicts(api):
    task = create(api)
    assert api.client.post(f"{BASE}/{task['id']}/cancel").json()["status"] == "cancelled"
    for call in (
        api.client.post(f"{BASE}/{task['id']}/complete"),
        api.client.post(f"{BASE}/{task['id']}/reopen"),
        api.client.patch(f"{BASE}/{task['id']}", json={"title": "x"}),
    ):
        assert call.status_code == 409 and call.json()["error"]["code"] == "conflict"


def test_cannot_cancel_completed_task(api):
    task = create(api)
    api.client.post(f"{BASE}/{task['id']}/complete")
    assert api.client.post(f"{BASE}/{task['id']}/cancel").status_code == 409


def test_list_filters_and_ordering(api):
    create(api, title="sem prazo")
    create(api, title="tarde", due_at="2026-11-10T10:00:00Z", priority="low", category="casa")
    cedo = create(api, title="cedo", due_at="2026-11-02T10:00:00Z", priority="high")
    done = create(api, title="feita", due_at="2026-11-01T10:00:00Z")
    api.client.post(f"{BASE}/{done['id']}/complete")

    titles = lambda **p: [i["title"] for i in api.client.get(BASE, params=p).json()["items"]]  # noqa: E731
    assert titles() == ["feita", "cedo", "tarde", "sem prazo"]
    assert titles(status="completed") == ["feita"]
    assert titles(priority="high") == ["cedo"]
    assert titles(category="casa") == ["tarde"]
    # vencidas: pendentes com prazo < agora (2026-11-03T12:00Z); concluída não conta
    assert titles(overdue="true") == ["cedo"]
    assert titles(due_at_from="2026-11-02T00:00:00Z", due_at_to="2026-11-10T10:00:00Z") == ["cedo"]
    page = api.client.get(BASE, params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 4 and [i["id"] for i in page["items"]] == [cedo["id"]]


def test_isolation_between_users(api, user_b):
    task = create(api)
    api.as_user(user_b)
    url = f"{BASE}/{task['id']}"
    assert api.client.get(url).status_code == 404
    assert api.client.patch(url, json={"title": "x"}).status_code == 404
    for action in ("complete", "reopen", "cancel"):
        assert api.client.post(f"{url}/{action}").status_code == 404
    assert api.client.get(BASE).json()["total"] == 0
