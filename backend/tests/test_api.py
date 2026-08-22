import sqlite3
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_approval_repository, get_detector
from backend.app.core.config import get_settings
from backend.app.domain.errors import ApprovalPersistenceError
from backend.app.main import create_app
from backend.app.repositories.approvals import ApprovalRepository


def _configure_safety_task(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    image_dir = tmp_path / "safety_signs" / "images"
    label_dir = tmp_path / "safety_signs" / "labels"
    visualization_dir = tmp_path / "safety_signs" / "visualizations"
    model_path = tmp_path / "weights" / "sign.pt"
    database_path = tmp_path / "state" / "labeling_db.sqlite3"

    monkeypatch.setenv("SAFETY_SIGN_IMAGE_DIR", str(image_dir))
    monkeypatch.setenv("SAFETY_SIGN_LABEL_DIR", str(label_dir))
    monkeypatch.setenv("SAFETY_SIGN_VISUALIZATION_DIR", str(visualization_dir))
    monkeypatch.setenv("SAFETY_SIGN_MODEL_PATH", str(model_path))
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    get_settings.cache_clear()

    image_dir.mkdir(parents=True)
    label_dir.mkdir(parents=True)
    visualization_dir.mkdir(parents=True)
    model_path.parent.mkdir(parents=True)
    return image_dir, label_dir, visualization_dir, model_path


def test_tasks_endpoint_lists_safety_sign_profile(monkeypatch, tmp_path: Path) -> None:
    _configure_safety_task(monkeypatch, tmp_path)

    client = TestClient(create_app())
    response = client.get("/api/v1/tasks")

    assert response.status_code == 200
    tasks = response.json()
    safety_task = next(task for task in tasks if task["id"] == "safety_signs")
    assert safety_task["temporary_class_id"] is None
    assert safety_task["class_names"]["0"].startswith("M014")
    assert safety_task["class_names"]["3"].startswith("W011")
    assert "4" not in safety_task["class_names"]
    ppe_task = next(task for task in tasks if task["id"] == "ppe")
    assert ppe_task["class_names"]["3"] == "Cleaning Coverall"


def test_openapi_keeps_the_bounding_box_component_name(monkeypatch, tmp_path: Path) -> None:
    _configure_safety_task(monkeypatch, tmp_path)

    schema = TestClient(create_app()).get("/openapi.json").json()["components"]["schemas"]

    assert "BoundingBox" in schema
    assert "BoundingBoxSchema" not in schema
    assert schema["LabelPayload"]["properties"]["boxes"]["items"]["$ref"] == "#/components/schemas/BoundingBox"


def test_task_image_list_uses_scoped_media_urls(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")
    (label_dir / "sample.txt").write_text("", encoding="utf-8")

    client = TestClient(create_app())
    response = client.get("/api/v1/tasks/safety_signs/images")

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "sample.jpg",
            "has_label": True,
            "is_approved": False,
            "image_url": "/media/safety_signs/images/sample.jpg",
            "visualization_url": None,
        }
    ]


def test_task_media_route_returns_scoped_image(monkeypatch, tmp_path: Path) -> None:
    image_dir, _, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    image_content = b"image-content"
    (image_dir / "sample.jpg").write_bytes(image_content)

    client = TestClient(create_app())
    response = client.get("/media/safety_signs/images/sample.jpg")

    assert response.status_code == 200
    assert response.content == image_content


def test_task_visualization_route_keeps_the_requested_visualization_filename(monkeypatch, tmp_path: Path) -> None:
    _, _, visualization_dir, _ = _configure_safety_task(monkeypatch, tmp_path)
    visualization_content = b"visualization-content"
    (visualization_dir / "verified_sample.jpg").write_bytes(visualization_content)

    response = TestClient(create_app()).get("/media/safety_signs/visualizations/verified_sample.jpg")

    assert response.status_code == 200
    assert response.content == visualization_content


def test_non_inference_route_does_not_resolve_detector(monkeypatch, tmp_path: Path) -> None:
    image_dir, _, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    image_dir.joinpath("sample.jpg").write_bytes(b"image")
    app = create_app()

    def detector_must_not_be_resolved():
        raise AssertionError("list route must not resolve an inference detector")

    app.dependency_overrides[get_detector] = detector_must_not_be_resolved
    response = TestClient(app).get("/api/v1/tasks/safety_signs/images")

    assert response.status_code == 200


def test_media_and_export_do_not_require_approval_sqlite(monkeypatch, tmp_path: Path) -> None:
    image_dir, _, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    image_dir.joinpath("sample.jpg").write_bytes(b"image-content")
    app = create_app()

    def unavailable_approvals():
        raise ApprovalPersistenceError("Approval persistence is unavailable")

    app.dependency_overrides[get_approval_repository] = unavailable_approvals
    client = TestClient(app, raise_server_exceptions=False)

    media_response = client.get("/media/safety_signs/images/sample.jpg")
    export_response = client.get("/api/v1/tasks/safety_signs/images/sample.jpg/export")
    approval_dependent_response = client.get("/api/v1/tasks/safety_signs/images")

    assert media_response.status_code == 200
    assert media_response.content == b"image-content"
    assert export_response.status_code == 200
    with ZipFile(BytesIO(export_response.content)) as archive:
        assert sorted(archive.namelist()) == ["images/sample.jpg", "labels/sample.txt"]
    assert approval_dependent_response.status_code == 503
    assert approval_dependent_response.json() == {"detail": "Approval persistence is unavailable"}


def test_upload_images_adds_files_to_task(monkeypatch, tmp_path: Path) -> None:
    image_dir, _, _, _ = _configure_safety_task(monkeypatch, tmp_path)

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/tasks/safety_signs/images/upload",
        files=[
            ("files", ("sample.jpg", b"image-one", "image/jpeg")),
            ("files", ("sample.jpg", b"image-two", "image/jpeg")),
        ],
    )

    assert response.status_code == 200
    assert sorted(path.name for path in image_dir.iterdir()) == ["sample.jpg", "sample_001.jpg"]


def test_export_current_image_includes_image_and_empty_label(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "sample.jpg").write_bytes(b"image")

    client = TestClient(create_app())
    response = client.get("/api/v1/tasks/safety_signs/images/sample.jpg/export")

    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["images/sample.jpg", "labels/sample.txt"]
        assert archive.read("labels/sample.txt") == b""
    assert (label_dir / "sample.txt").exists()


def test_export_all_includes_all_image_label_pairs(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "a.jpg").write_bytes(b"a")
    (image_dir / "b.png").write_bytes(b"b")
    (label_dir / "a.txt").write_text("0 0.500000 0.500000 0.200000 0.200000\n", encoding="utf-8")

    client = TestClient(create_app())
    response = client.get("/api/v1/tasks/safety_signs/export")

    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["images/a.jpg", "images/b.png", "labels/a.txt", "labels/b.txt"]


def test_rename_sequential_keeps_images_and_labels_together(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, visualization_dir, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "z.png").write_bytes(b"z")
    (image_dir / "a.jpg").write_bytes(b"a")
    (label_dir / "z.txt").write_text("3 0.500000 0.500000 0.200000 0.200000\n", encoding="utf-8")
    (visualization_dir / "verified_z.jpg").write_bytes(b"visual")

    client = TestClient(create_app())
    approval_response = client.put(
        "/api/v1/tasks/safety_signs/images/z.png/approve",
        json={"is_approved": True},
    )
    assert approval_response.status_code == 200
    response = client.post("/api/v1/tasks/safety_signs/rename-sequential")

    assert response.status_code == 200
    assert sorted(path.name for path in image_dir.iterdir()) == ["image_00000.jpg", "image_00001.png"]
    assert (label_dir / "image_00000.txt").read_text(encoding="utf-8") == ""
    assert (label_dir / "image_00001.txt").read_text(encoding="utf-8").startswith("3 ")
    assert (visualization_dir / "verified_image_00001.jpg").exists()
    images_response = client.get("/api/v1/tasks/safety_signs/images")
    approvals = {item["name"]: item["is_approved"] for item in images_response.json()}
    assert approvals["image_00001.png"] is True


def test_put_empty_labels_persists_empty_label_file(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")

    client = TestClient(create_app())
    response = client.put("/api/v1/tasks/safety_signs/images/sample.jpg/labels", json={"boxes": []})

    assert response.status_code == 200
    assert (label_dir / "sample.txt").read_text(encoding="utf-8") == ""


def test_task_label_api_round_trip(monkeypatch, tmp_path: Path) -> None:
    image_dir, _, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")
    client = TestClient(create_app())
    boxes = [{"class_id": 3, "x_center": 0.5, "y_center": 0.4, "w": 0.2, "h": 0.1}]

    save_response = client.put(
        "/api/v1/tasks/safety_signs/images/sample.jpg/labels",
        json={"boxes": boxes},
    )
    read_response = client.get("/api/v1/tasks/safety_signs/images/sample.jpg/labels")

    assert save_response.status_code == 200
    assert read_response.status_code == 200
    assert read_response.json() == {"filename": "sample.jpg", "boxes": boxes}


def test_labels_for_a_missing_image_are_rejected_without_creating_an_orphan_file(monkeypatch, tmp_path: Path) -> None:
    _, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)

    response = TestClient(create_app()).put(
        "/api/v1/tasks/safety_signs/images/missing.jpg/labels",
        json={"boxes": []},
    )

    assert response.status_code == 404
    assert not label_dir.joinpath("missing.txt").exists()


def test_labels_for_a_missing_image_return_the_empty_label_contract(monkeypatch, tmp_path: Path) -> None:
    _, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)

    response = TestClient(create_app()).get("/api/v1/tasks/safety_signs/images/missing.jpg/labels")

    assert response.status_code == 200
    assert response.json() == {"filename": "missing.jpg", "boxes": []}
    assert not label_dir.joinpath("missing.txt").exists()


def test_missing_delete_cannot_remove_artifacts_for_an_existing_same_stem_image(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    image_dir.joinpath("same.jpg").write_bytes(b"image")
    label_dir.joinpath("same.txt").write_text("0 0.500000 0.500000 0.200000 0.200000\n", encoding="utf-8")
    database_path = tmp_path / "state" / "labeling_db.sqlite3"
    ApprovalRepository(database_path).set_approval("safety_signs", "same.png", True)

    response = TestClient(create_app()).delete("/api/v1/tasks/safety_signs/images/same.png")

    assert response.status_code == 200
    assert image_dir.joinpath("same.jpg").exists()
    assert label_dir.joinpath("same.txt").exists()
    assert ApprovalRepository(database_path).approved_filenames("safety_signs") == set()


def test_put_labels_rejects_classes_outside_task_map(monkeypatch, tmp_path: Path) -> None:
    image_dir, _, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")

    client = TestClient(create_app())
    response = client.put(
        "/api/v1/tasks/safety_signs/images/sample.jpg/labels",
        json={"boxes": [{"class_id": 8, "x_center": 0.5, "y_center": 0.5, "w": 0.2, "h": 0.2}]},
    )

    assert response.status_code == 422
    assert "Allowed class IDs: 0, 1, 2, 3" in response.json()["detail"]


def test_custom_task_class_map_accepts_added_class(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    monkeypatch.setenv("SAFETY_SIGN_CLASS_NAMES", "0=Base Sign|8=Extra Sign")
    get_settings.cache_clear()
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")

    client = TestClient(create_app())
    response = client.put(
        "/api/v1/tasks/safety_signs/images/sample.jpg/labels",
        json={"boxes": [{"class_id": 8, "x_center": 0.5, "y_center": 0.5, "w": 0.2, "h": 0.2}]},
    )

    assert response.status_code == 200
    assert (label_dir / "sample.txt").read_text(encoding="utf-8").startswith("8 ")


def test_approval_status_is_persisted_in_sqlite(monkeypatch, tmp_path: Path) -> None:
    image_dir, _, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")
    database_path = tmp_path / "state" / "labeling_db.sqlite3"

    client = TestClient(create_app())
    response = client.put(
        "/api/v1/tasks/safety_signs/images/sample.jpg/approve",
        json={"is_approved": True},
    )

    assert response.status_code == 200
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT is_approved FROM approval_status WHERE task_id = ? AND filename = ?",
            ("safety_signs", "sample.jpg"),
        ).fetchone()
    assert row == (1,)

    response = client.put(
        "/api/v1/tasks/safety_signs/images/sample.jpg/approve",
        json={"is_approved": False},
    )
    assert response.status_code == 200
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT is_approved FROM approval_status WHERE task_id = ? AND filename = ?",
            ("safety_signs", "sample.jpg"),
        ).fetchone()
    assert row is None
    image_response = client.get("/api/v1/tasks/safety_signs/images")
    assert image_response.json()[0]["is_approved"] is False

    response = client.put(
        "/api/v1/tasks/safety_signs/images/sample.jpg/approve",
        json={"is_approved": True},
    )
    assert response.status_code == 200

    response = client.delete("/api/v1/tasks/safety_signs/images/sample.jpg")
    assert response.status_code == 200
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT 1 FROM approval_status WHERE task_id = ? AND filename = ?",
            ("safety_signs", "sample.jpg"),
        ).fetchone()
    assert row is None


def test_approval_for_a_missing_image_is_rejected_without_creating_metadata(monkeypatch, tmp_path: Path) -> None:
    _configure_safety_task(monkeypatch, tmp_path)
    database_path = tmp_path / "state" / "labeling_db.sqlite3"
    client = TestClient(create_app())

    response = client.put(
        "/api/v1/tasks/safety_signs/images/missing.jpg/approve",
        json={"is_approved": True},
    )

    assert response.status_code == 404
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT 1 FROM approval_status WHERE task_id = ? AND filename = ?",
            ("safety_signs", "missing.jpg"),
        ).fetchone()
    assert row is None

    response = client.put(
        "/api/v1/tasks/safety_signs/images/missing.jpg/approve",
        json={"is_approved": False},
    )
    assert response.status_code == 200


def test_sequential_rename_rejects_manual_filesystem_duplicate_stems(monkeypatch, tmp_path: Path) -> None:
    image_dir, _, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    image_dir.joinpath("same.jpg").write_bytes(b"jpg")
    image_dir.joinpath("same.png").write_bytes(b"png")

    response = TestClient(create_app()).post("/api/v1/tasks/safety_signs/rename-sequential")

    assert response.status_code == 409
    assert sorted(path.name for path in image_dir.iterdir()) == ["same.jpg", "same.png"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/images"),
        ("DELETE", "/api/v1/images/sample.jpg"),
        ("GET", "/api/v1/images/sample.jpg/labels"),
        ("PUT", "/api/v1/images/sample.jpg/labels"),
        ("PUT", "/api/v1/images/sample.jpg/approve"),
        ("POST", "/api/v1/images/sample.jpg/auto-label"),
        ("POST", "/api/v1/auto-label"),
        ("POST", "/api/v1/visualizations"),
    ],
)
def test_legacy_active_task_routes_are_not_registered(method: str, path: str) -> None:
    response = TestClient(create_app()).request(method, path)

    assert response.status_code == 404
