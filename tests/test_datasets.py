"""MinIO-backed dataset upload/list/download/delete (on the in-memory store)."""

from __future__ import annotations

import io
import zipfile


def _upload(client, dataset_files, name="SIM-01"):
    return client.post("/datasets", files=dataset_files, data={"name": name})


def test_upload_creates_dataset(client, dataset_files):
    r = _upload(client, dataset_files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["dataset_id"].startswith("ds_")
    assert body["name"] == "SIM-01"
    assert body["file_count"] == 3
    assert body["total_size"] > 0
    assert {f["filename"] for f in body["files"]} == {
        "SIM-01_log.csv",
        "SIM-01_labels.csv",
        "SIM-01_truth.json",
    }


def test_list_and_detail(client, dataset_files):
    did = _upload(client, dataset_files).json()["dataset_id"]
    lst = client.get("/datasets").json()
    assert lst["total"] == 1
    assert lst["items"][0]["file_count"] == 3
    assert lst["items"][0]["total_size"] > 0

    detail = client.get(f"/datasets/{did}").json()
    assert len(detail["files"]) == 3


def test_download_zip_is_byte_exact(client, dataset_files):
    did = _upload(client, dataset_files).json()["dataset_id"]
    z = client.get(f"/datasets/{did}/download")
    assert z.status_code == 200
    assert z.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(z.content))
    assert set(zf.namelist()) == {
        "SIM-01_log.csv",
        "SIM-01_labels.csv",
        "SIM-01_truth.json",
    }
    original = dict((f[1][0], f[1][1]) for f in dataset_files)  # filename -> bytes
    for name in zf.namelist():
        assert zf.read(name) == original[name]


def test_download_single_file(client, dataset_files):
    detail = _upload(client, dataset_files).json()
    did = detail["dataset_id"]
    f = next(f for f in detail["files"] if f["filename"] == "SIM-01_log.csv")
    got = client.get(f"/datasets/{did}/files/{f['id']}")
    assert got.status_code == 200
    assert got.content == b"run_id,time_h\nTST,0\nTST,1\n"
    assert "SIM-01_log.csv" in got.headers["content-disposition"]


def test_delete_removes_dataset(client, dataset_files):
    did = _upload(client, dataset_files).json()["dataset_id"]
    r = client.delete(f"/datasets/{did}")
    assert r.status_code == 200 and r.json()["deleted"] == did
    assert client.get(f"/datasets/{did}").status_code == 404
    assert client.get("/datasets").json()["total"] == 0


def test_upload_requires_a_file(client):
    assert client.post("/datasets", data={"name": "x"}).status_code == 422


def test_duplicate_filename_rejected(client):
    files = [
        ("files", ("dup.csv", b"a", "text/csv")),
        ("files", ("dup.csv", b"b", "text/csv")),
    ]
    assert client.post("/datasets", files=files).status_code == 422


def test_unknown_dataset_404(client):
    assert client.get("/datasets/ds_nope").status_code == 404
    assert client.delete("/datasets/ds_nope").status_code == 404
    assert client.get("/datasets/ds_nope/download").status_code == 404
