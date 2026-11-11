"""Dataset ingest, browse, and download behaviour."""

from __future__ import annotations


def test_upload_melts_log_and_labels(client, sim_files):
    r = client.post("/datasets", files=sim_files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["run_id"] == "TST"
    assert body["created"] is True and body["replaced"] is False
    # 2 log rows x 3 channels = 6 ; labels 1 row x 2 cols = 2
    assert body["n_measurements"] == 6
    assert body["n_labels"] == 2
    assert body["n_files"] == 3


def test_upload_conflict_then_replace(client, sim_files):
    assert client.post("/datasets", files=sim_files).status_code == 201
    assert client.post("/datasets", files=sim_files).status_code == 409
    r = client.post("/datasets", files=sim_files, params={"replace": "true"})
    assert r.status_code == 201
    assert r.json()["replaced"] is True


def test_list_and_detail(client, sim_files):
    client.post("/datasets", files=sim_files)
    lst = client.get("/datasets").json()
    assert lst["total"] == 1
    summary = lst["items"][0]
    assert summary["run_id"] == "TST"
    assert summary["is_synthetic"] is True
    assert summary["process_mode"] == "fed-batch"  # spec has feed_rate_L_h
    assert summary["has_spec"] is True
    assert summary["n_files"] == 3

    detail = client.get("/datasets/TST").json()
    assert detail["synthetic_spec"]["spec"]["seed"] == 42
    assert detail["synthetic_spec"]["kinetics"]["mu_max_1_h"] == 0.03
    props = {(p["measured_property"], p["is_ground_truth"]): p for p in detail["properties"]}
    assert props[("do_pct", False)]["count"] == 2
    assert props[("do_pct", False)]["unit"] == "%"
    # 2 from the log's truth_biomass_g_L column + 1 from the label's truth column
    assert props[("biomass_g_L", True)]["count"] == 3
    assert props[("biomass_g_L", False)]["count"] == 1  # the observed label


def test_ground_truth_flagging(client, sim_files):
    client.post("/datasets", files=sim_files)
    truth = client.get(
        "/runs/TST/measurements", params={"property": "biomass_g_L", "is_ground_truth": "true"}
    ).json()
    assert truth["total"] == 3  # 2 log truth rows + 1 label truth
    observed = client.get(
        "/runs/TST/measurements", params={"property": "biomass_g_L", "is_ground_truth": "false"}
    ).json()
    assert observed["total"] == 1
    assert observed["items"][0]["method_or_sensor"] == "synthetic DCW"


def test_download_is_byte_exact(client, sim_files):
    client.post("/datasets", files=sim_files)
    original_log = sim_files["log"][1]
    got = client.get("/datasets/TST/files/log")
    assert got.status_code == 200
    assert got.content == original_log
    assert "TST_log.csv" in got.headers["content-disposition"]

    zip_resp = client.get("/datasets/TST/download")
    assert zip_resp.status_code == 200
    assert zip_resp.headers["content-type"] == "application/zip"


def test_measurements_time_filter(client, sim_files):
    client.post("/datasets", files=sim_files)
    page = client.get(
        "/runs/TST/measurements", params={"property": "do_pct", "from_h": 0.5, "to_h": 2}
    ).json()
    assert page["total"] == 1
    assert page["items"][0]["time_h"] == 1.0


def test_csv_export_pivots_back_to_wide(client, sim_files):
    client.post("/datasets", files=sim_files)
    text = client.get("/runs/TST/measurements.csv", params={"include_ground_truth": "false"}).text
    lines = text.strip().splitlines()
    header = lines[0].split(",")
    assert header[:2] == ["run_id", "time_h"]
    assert "do_pct" in header and "temp_C" in header
    assert "truth_biomass_g_L" not in header  # excluded
    assert len(lines) == 1 + 2  # header + 2 timesteps


def test_delete_dataset_cascades(client, sim_files):
    client.post("/datasets", files=sim_files)
    assert client.get("/runs/TST/measurements").json()["total"] > 0
    r = client.delete("/datasets/TST")
    assert r.status_code == 200 and r.json()["deleted"] == "TST"
    # run and all its data are gone
    assert client.get("/datasets/TST").status_code == 404
    assert client.get("/runs/TST/measurements").status_code == 404
    assert client.get("/datasets").json()["total"] == 0


def test_unknown_dataset_404(client):
    assert client.get("/datasets/NOPE").status_code == 404
    assert client.get("/runs/NOPE/measurements").status_code == 404
    assert client.delete("/datasets/NOPE").status_code == 404
