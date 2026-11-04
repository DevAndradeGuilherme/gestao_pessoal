BASE = "/api/v1/routines"
RULE = {
    "frequency": "weekly",
    "by_weekday": ["mon", "tue", "wed", "thu", "fri"],
    "time": "19:00",
    "timezone": "America/Sao_Paulo",
    "start_date": "2026-11-02",
}
WINDOW = {"window_start": "2026-11-02T00:00:00Z", "window_end": "2026-11-09T00:00:00Z"}


def create(api, **over):
    r = api.client.post(BASE, json={"title": "Estudar inglês", "recurrence_rule": RULE, **over})
    assert r.status_code == 201, r.text
    return r.json()


def generate(api, routine, window=WINDOW):
    r = api.client.post(f"{BASE}/{routine['id']}/occurrences/generate", json=window)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_returns_normalized_rule_and_audits(api):
    body = create(api)
    assert body["active"] is True
    assert body["recurrence_rule"]["interval"] == 1
    assert body["recurrence_rule"]["time"] == "19:00:00"
    assert api.audit_actions(body["id"]) == ["routine.created"]


def test_create_last_day_of_month_rule(api):
    rule = {
        "frequency": "monthly",
        "by_month_day": [-1],
        "time": "23:00",
        "timezone": "America/Sao_Paulo",
        "start_date": "2026-11-01",
    }
    assert create(api, recurrence_rule=rule)["recurrence_rule"]["by_month_day"] == [-1]


def test_invalid_rules_return_validation_error(api):
    bad_rules = [
        {**RULE, "by_weekday": []},
        {**RULE, "timezone": "Nao/Existe"},
        {**RULE, "frequency": "monthly"},
        {**RULE, "interval": 0},
    ]
    for rule in bad_rules:
        r = api.client.post(BASE, json={"title": "x", "recurrence_rule": rule})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"
    assert api.client.post(BASE, json={"title": "x"}).status_code == 422
    assert api.client.post(BASE, json={"recurrence_rule": RULE}).status_code == 422


def test_update_title_and_rule(api):
    routine = create(api)
    url = f"{BASE}/{routine['id']}"
    new_rule = {**RULE, "by_weekday": ["sat"]}
    r = api.client.patch(url, json={"title": "Inglês", "recurrence_rule": new_rule})
    assert r.status_code == 200
    assert r.json()["title"] == "Inglês" and r.json()["recurrence_rule"]["by_weekday"] == ["sat"]
    assert api.audit.entries[-1].action == "routine.updated"
    assert api.client.patch(url, json={"recurrence_rule": None}).status_code == 422
    assert (
        api.client.patch(url, json={"recurrence_rule": {**RULE, "interval": -1}}).status_code == 422
    )


def test_deactivate_and_activate_are_audited_and_idempotent(api):
    routine = create(api)
    url = f"{BASE}/{routine['id']}"
    assert api.client.post(f"{url}/deactivate").json()["active"] is False
    assert api.client.post(f"{url}/deactivate").json()["active"] is False
    assert api.client.get(url).status_code == 200  # desativar não exclui
    assert api.audit_actions(routine["id"]) == ["routine.created", "routine.deactivated"]
    assert api.client.post(f"{url}/activate").json()["active"] is True
    assert api.client.get(BASE, params={"active": "false"}).json()["total"] == 0
    assert api.client.get(BASE, params={"active": "true"}).json()["total"] == 1


def test_list_order_and_pagination(api):
    for n in range(3):
        create(api, title=f"r{n}")
        api.clock.advance(minutes=1)
    page = api.client.get(BASE, params={"limit": 2}).json()
    assert [i["title"] for i in page["items"]] == ["r2", "r1"] and page["total"] == 3


def test_generate_occurrences_weekdays_only_and_idempotent(api):
    routine = create(api)
    first = generate(api, routine)
    assert first["created"] == 5  # seg-sex; sábado/domingo fora
    assert [o["scheduled_for"] for o in first["occurrences"]][:2] == [
        "2026-11-02T22:00:00Z",
        "2026-11-03T22:00:00Z",
    ]
    assert {o["status"] for o in first["occurrences"]} == {"pending"}
    assert all(o["completed_at"] is None for o in first["occurrences"])
    second = generate(api, routine)
    assert second["created"] == 0 and len(second["occurrences"]) == 5
    assert [o["id"] for o in second["occurrences"]] == [o["id"] for o in first["occurrences"]]


def test_generate_window_validation_and_inactive(api):
    routine = create(api)
    url = f"{BASE}/{routine['id']}/occurrences/generate"
    inverted = {"window_start": WINDOW["window_end"], "window_end": WINDOW["window_start"]}
    assert api.client.post(url, json=inverted).status_code == 422
    too_long = {"window_start": "2026-01-01T00:00:00Z", "window_end": "2027-06-01T00:00:00Z"}
    assert api.client.post(url, json=too_long).status_code == 422
    assert api.client.post(url, json={"window_start": "2026-01-01T00:00:00"}).status_code == 422
    api.client.post(f"{BASE}/{routine['id']}/deactivate")
    r = api.client.post(url, json=WINDOW)
    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict"


def test_complete_skip_reopen_occurrence(api):
    routine = create(api)
    occ = generate(api, routine)["occurrences"][0]
    url = f"{BASE}/{routine['id']}/occurrences/{occ['id']}"
    api.clock.advance(hours=1)

    done = api.client.post(f"{url}/complete").json()
    assert done["status"] == "completed" and done["completed_at"] == "2026-11-03T13:00:00Z"
    skipped = api.client.post(f"{url}/skip").json()
    assert skipped["status"] == "skipped" and skipped["completed_at"] is None
    reopened = api.client.post(f"{url}/reopen").json()
    assert reopened["status"] == "pending"
    actions = api.audit_actions(occ["id"])
    assert actions == [
        "routine_occurrence.complete",
        "routine_occurrence.skip",
        "routine_occurrence.reopen",
    ]
    # repetir o mesmo estado não gera nova auditoria
    api.client.post(f"{url}/reopen")
    assert len(api.audit_actions(occ["id"])) == 3


def test_time_passing_never_completes_occurrence(api):
    routine = create(api)
    generate(api, routine)
    api.clock.advance(days=60)
    listed = api.client.get(f"{BASE}/{routine['id']}/occurrences").json()
    assert {o["status"] for o in listed["items"]} == {"pending"}


def test_complete_occurrence_rejects_future_instant(api):
    routine = create(api)
    occ = generate(api, routine)["occurrences"][0]
    r = api.client.post(
        f"{BASE}/{routine['id']}/occurrences/{occ['id']}/complete",
        json={"completed_at": "2026-12-01T00:00:00Z"},
    )
    assert r.status_code == 422


def test_list_occurrences_filters(api):
    routine = create(api)
    occs = generate(api, routine)["occurrences"]
    api.client.post(f"{BASE}/{routine['id']}/occurrences/{occs[0]['id']}/complete")
    url = f"{BASE}/{routine['id']}/occurrences"
    assert api.client.get(url, params={"status": "completed"}).json()["total"] == 1
    window = {
        "scheduled_for_from": "2026-11-03T00:00:00Z",
        "scheduled_for_to": "2026-11-05T00:00:00Z",
    }
    assert api.client.get(url, params=window).json()["total"] == 2
    page = api.client.get(url, params={"limit": 2, "offset": 3}).json()
    assert len(page["items"]) == 2 and page["total"] == 5
    inverted = {
        "scheduled_for_from": window["scheduled_for_to"],
        "scheduled_for_to": window["scheduled_for_from"],
    }
    assert api.client.get(url, params=inverted).status_code == 422


def test_isolation_between_users(api, user_b):
    routine = create(api)
    occ = generate(api, routine)["occurrences"][0]
    api.as_user(user_b)
    url = f"{BASE}/{routine['id']}"
    assert api.client.get(url).status_code == 404
    assert api.client.patch(url, json={"title": "x"}).status_code == 404
    assert api.client.post(f"{url}/deactivate").status_code == 404
    assert api.client.get(f"{url}/occurrences").status_code == 404
    assert api.client.post(f"{url}/occurrences/generate", json=WINDOW).status_code == 404
    assert api.client.post(f"{url}/occurrences/{occ['id']}/complete").status_code == 404
    assert api.client.get(BASE).json()["total"] == 0


def test_occurrence_of_other_routine_is_not_found(api):
    first, second = create(api), create(api, title="outra")
    occ = generate(api, first)["occurrences"][0]
    r = api.client.post(f"{BASE}/{second['id']}/occurrences/{occ['id']}/complete")
    assert r.status_code == 404
