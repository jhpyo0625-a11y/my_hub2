"""HTTP layer via FastAPI TestClient. Engine is real — nothing is mocked."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from kdri.api.app import create_app


@pytest.fixture
def client():
    app = create_app("sqlite://", demo=True)
    return TestClient(app)


def _valid_body(**over):
    body = {
        "profile": {"age": 34, "sex": "M", "weight_kg": 72},
        "supplements": [
            {
                "nutrient_code": "magnesium",
                "form_ko": "산화마그네슘",
                "dose": 600,
                "unit": "mg",
                "doses_per_day": 1,
            }
        ],
        "medications": ["quinolone"],
    }
    body.update(over)
    return body


# ── reference ────────────────────────────────────────────────────────────


def test_reference_returns_30_nutrients(client):
    r = client.get("/api/reference")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nutrients"]) == 30
    assert data["kdri_version"] == "2025"
    mg = next(n for n in data["nutrients"] if n["nutrient_code"] == "magnesium")
    assert mg["target_unit"] == "mg" and "forms" in mg
    assert {"carbohydrate", "protein", "fat"} == {
        e["macronutrient"] for e in data["energy_ratios"]
    }


# ── health ───────────────────────────────────────────────────────────────


def test_health_band_rows_300(client):
    data = client.get("/api/health").json()
    assert data["band_rows"] == 300
    assert data["seed_assertions"] == "passed"
    assert data["status"] == "ok"


def test_seed_assertion_failure_aborts_startup():
    # a broken engine input must abort create_app (PF-04)
    import sys

    appmod = sys.modules["kdri.api.app"]
    orig = appmod.load_engine_inputs

    def broken(demo=None):
        inp = orig(demo)
        inp.bands = inp.bands[:-1]
        return inp

    appmod.load_engine_inputs = broken
    try:
        with pytest.raises(AssertionError):
            create_app("sqlite://", demo=False)
    finally:
        appmod.load_engine_inputs = orig


# ── POST /api/reports ────────────────────────────────────────────────────


def test_post_returns_201_with_30_results_and_summary(client):
    r = client.post("/api/reports", json=_valid_body())
    assert r.status_code == 201
    data = r.json()
    assert len(data["results"]) == 30
    s = data["summary"]
    assert s["over"] + s["deficit"] + s["adequate"] + s["unknown"] == 30
    assert data["disclaimer"]
    assert data["demo_data"] is True
    # magnesium overshoots its supplemental-only limit -> OVER, at the top
    assert data["results"][0]["nutrient_code"] == "magnesium"
    assert data["results"][0]["status"] == "OVER"
    assert "초과" in data["results"][0]["message_ko"]
    # interaction attached (magnesium x quinolone)
    assert data["results"][0]["interactions"][0]["drug_class"] == "quinolone"
    # AMDR reference present and labelled
    assert data["energy_ratios_reference"][0]["note_ko"].startswith("참고용")


def test_invariants(client):
    data = client.post("/api/reports", json=_valid_body()).json()
    results = data["results"]
    assert len(results) == 30
    for res in results:
        assert res["trace"], f"{res['nutrient_code']} has no trace"
        assert res["recommend"] >= 0
        assert res["recommend"] <= res["gap"] + 1e-9
        if res["limit"] is not None and res["headroom"] is not None:
            assert res["recommend"] <= max(0.0, res["headroom"]) + 1e-9


def test_get_after_post_byte_identical_results(client):
    post = client.post("/api/reports", json=_valid_body()).json()
    rid = post["report_id"]
    get = client.get(f"/api/reports/{rid}").json()
    assert json.dumps(get["results"], ensure_ascii=False) == json.dumps(
        post["results"], ensure_ascii=False
    )


# ── scope refusals (SC) — no numbers ─────────────────────────────────────


@pytest.mark.parametrize(
    "mutation,code",
    [
        ({"profile": {"age": 18, "sex": "M"}}, "AGE_OUT_OF_SCOPE"),
        ({"profile": {"age": 30, "sex": "M", "is_pregnant": True}}, "PREGNANCY_OUT_OF_SCOPE"),
        ({"profile": {"age": 30}}, "SEX_REQUIRED"),
        ({"profile": {"age": 30, "sex": "X"}}, "SEX_REQUIRED"),
    ],
)
def test_scope_refusals(client, mutation, code):
    r = client.post("/api/reports", json=_valid_body(**mutation))
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == code
    assert body["error"]["message"]
    assert "results" not in body  # SC-09: refusals never return results


def test_invalid_intake_bad_dose(client):
    body = _valid_body()
    body["supplements"][0]["dose"] = 0
    r = client.post("/api/reports", json=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_INTAKE"


def test_unknown_drug_class_does_not_fail(client):
    body = _valid_body(medications=["totally_unknown_drug"])
    r = client.post("/api/reports", json=body)
    assert r.status_code == 201  # SC-07


# ── ownership (SE-01) ─────────────────────────────────────────────────────


def test_non_owner_gets_404_not_403():
    app = create_app("sqlite://", demo=True)
    owner = TestClient(app)
    stranger = TestClient(app)
    rid = owner.post("/api/reports", json=_valid_body()).json()["report_id"]
    r = stranger.get(f"/api/reports/{rid}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "REPORT_NOT_FOUND"


def test_idempotency_key_returns_same_report(client):
    h = {"Idempotency-Key": "abc-123"}
    first = client.post("/api/reports", json=_valid_body(), headers=h).json()
    second = client.post("/api/reports", json=_valid_body(), headers=h).json()
    assert first["report_id"] == second["report_id"]


def test_delete_report(client):
    rid = client.post("/api/reports", json=_valid_body()).json()["report_id"]
    assert client.delete(f"/api/reports/{rid}").status_code == 204
    assert client.get(f"/api/reports/{rid}").status_code == 404
