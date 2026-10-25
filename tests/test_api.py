import os
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_upload_invalid_file():
    response = client.post("/upload", files={"file": ("notcsv.txt", b"foo", "text/plain")})
    assert response.status_code == 400


def test_upload_valid_csv(tmp_path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "timestamp,src_ip,dst_ip,src_port,dst_port,protocol,bytes\n"
        "2023-10-01T12:00:00,192.168.1.10,10.0.0.5,10000,80,TCP,500\n"
    )

    with open(csv_path, "rb") as fp:
        files = {"file": ("sample.csv", fp, "text/csv")}
        response = client.post("/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_dashboard_upload(tmp_path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "timestamp,src_ip,dst_ip,src_port,dst_port,protocol,bytes\n"
        "2023-10-01T12:00:00,192.168.1.10,10.0.0.5,10000,22,TCP,100\n"
    )
    with open(csv_path, "rb") as fp:
        files = {"file": ("sample.csv", fp, "text/csv")}
        response = client.post("/upload-dash", files=files)
    assert response.status_code == 200
    assert "Net Sentinel" in response.text
