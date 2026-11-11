"""Generic CRUD behaviour across the reflected entity routers."""

from __future__ import annotations


def test_feedstock_crud_roundtrip(client):
    created = client.post(
        "/feedstocks",
        json={"feedstock_id": "FS-1", "feedstock_name": "Spent grain", "physical_form": "solid"},
    )
    assert created.status_code == 201
    assert created.json()["feedstock_name"] == "Spent grain"

    got = client.get("/feedstocks/FS-1").json()
    assert got["feedstock_id"] == "FS-1"

    patched = client.patch("/feedstocks/FS-1", json={"availability": "seasonal"}).json()
    assert patched["availability"] == "seasonal"
    assert patched["feedstock_name"] == "Spent grain"  # untouched

    assert client.get("/feedstocks").json()["total"] == 1
    assert client.delete("/feedstocks/FS-1").status_code == 200
    assert client.get("/feedstocks/FS-1").status_code == 404


def test_duplicate_natural_key_conflict(client):
    client.post("/feedstocks", json={"feedstock_id": "FS-1"})
    assert client.post("/feedstocks", json={"feedstock_id": "FS-1"}).status_code == 409


def test_missing_required_field_422(client):
    assert client.post("/feedstocks", json={"feedstock_name": "no id"}).status_code == 422


def test_unknown_field_rejected(client):
    r = client.post("/feedstocks", json={"feedstock_id": "FS-2", "bogus": 1})
    assert r.status_code == 422


def test_child_fk_and_filter(client):
    client.post("/feedstocks", json={"feedstock_id": "FS-1"})
    comp = client.post(
        "/feedstock-compositions",
        json={
            "feedstock_id": "FS-1",
            "measured_property": "protein",
            "value_num": 12.5,
            "unit": "%",
        },
    )
    assert comp.status_code == 201
    assert isinstance(comp.json()["id"], int)

    filtered = client.get("/feedstock-compositions", params={"feedstock_id": "FS-1"}).json()
    assert filtered["total"] == 1


def test_bad_foreign_key_conflict(client):
    r = client.post(
        "/feedstock-compositions",
        json={"feedstock_id": "DOES-NOT-EXIST", "measured_property": "protein"},
    )
    assert r.status_code == 409


def test_enum_value_validation(client):
    ok = client.post(
        "/runs", json={"run_id": "R1", "process_status": "completed", "run_scale": "pilot"}
    )
    assert ok.status_code == 201
    assert ok.json()["process_status"] == "completed"
    bad = client.post("/runs", json={"run_id": "R2", "process_status": "not-a-status"})
    assert bad.status_code == 422
