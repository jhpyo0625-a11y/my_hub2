"""Guard tests for the MCP engine wrapper.

The point of these is regression protection: the previous version of this server
invented nutrient targets from a BMR formula with silent 80kg/male defaults,
which is exactly what the product forbids. These assertions pin the honest
behavior — numbers from the real engine, refusals instead of guesses, and no
body-weight path.

Runnable anywhere the `kdri` package is importable (backend venv or this one):
    python test_server.py
fastmcp is stubbed so the tool bodies can be exercised without the transport.
"""

import asyncio
import sys
import types


def _stub_fastmcp():
    fm = types.ModuleType("fastmcp")

    class FastMCP:
        def __init__(self, *a, **k):
            pass

        def tool(self, *a, **k):
            return lambda fn: fn

        def run(self):
            pass

    fm.FastMCP = FastMCP
    sys.modules.setdefault("fastmcp", fm)


_stub_fastmcp()
import server  # noqa: E402


async def _run():
    # sex is required and can never be defaulted (iron F != M)
    r = await server.analyze_intake_against_kdri(age=34, sex=None)
    assert r["status"] == "refused" and r["code"] == "SEX_REQUIRED", r

    # adults only — refuse, do not compute a pediatric guess
    r = await server.analyze_intake_against_kdri(age=15, sex="F")
    assert r["status"] == "refused" and r["code"] == "AGE_OUT_OF_SCOPE", r

    # unknown nutrient code is refused, not silently dropped
    r = await server.analyze_intake_against_kdri(
        age=34, sex="F", supplements=[{"nutrient_code": "unobtainium", "dose": 1}]
    )
    assert r["status"] == "refused" and r["code"] == "INVALID_INTAKE", r

    # real engine: 600 mg MgO (60.3% elemental) = 361.8 mg over the 350 supplemental
    # limit -> OVER; low hemoglobin flags iron; unsourced baseline -> UNKNOWN.
    r = await server.analyze_intake_against_kdri(
        age=34, sex="F",
        supplements=[{"nutrient_code": "magnesium", "dose": 600, "form_ko": "산화마그네슘"}],
        biomarkers=[{"code": "hemoglobin", "value": 10.5, "unit": "g/dL"}],
    )
    assert r["status"] == "ok"
    by = {x["nutrient_code"]: x for x in r["results"]}
    assert by["magnesium"]["status"] == "OVER"
    assert abs(by["magnesium"]["from_supplements"] - 361.8) < 0.1
    assert by["iron"]["biomarker_flag"]["direction"] == "low"
    assert by["zinc"]["status"] == "UNKNOWN"

    # there is no body-weight / BMR path anywhere in the surface
    blob = str(r).lower()
    assert "bmr" not in blob and "tdee" not in blob and "weight" not in blob

    # unit normalization reads the standard unit from the real profile
    u = await server.normalize_supplement_component("vitamin_d", 1000, "IU")
    assert u["status"] == "success" and abs(u["standard_value"] - 25.0) < 1e-9
    assert u["standard_unit"] == "µg"

    u = await server.normalize_supplement_component("unobtainium", 5, "mg")
    assert u["status"] == "error"

    print("mcp/test_server: all guard checks passed")


if __name__ == "__main__":
    asyncio.run(_run())
