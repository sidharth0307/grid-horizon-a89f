"""Ingest pipeline against a mocked Elexon API (no network)."""
import asyncio
import sqlite3

import httpx
import pytest

from scripts import ingest_elexon as ing

FUELHH = [
    {"fuelType": "WIND", "startTime": "2026-01-02T00:00:00Z", "generation": 15228},
    {"fuelType": "WIND", "startTime": "2026-01-02T00:30:00Z", "generation": 15505},
    {"fuelType": "CCGT", "startTime": "2026-01-02T00:00:00Z", "generation": 9000},
]
WINDFOR = [
    {"publishTime": "2026-01-01T07:30:00Z", "startTime": "2026-01-02T00:00:00Z", "generation": 18781.0},
    {"publishTime": "2026-01-01T09:30:00Z", "startTime": "2026-01-02T00:00:00Z", "generation": 18500.0},
]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_):
        return None
    monkeypatch.setattr(ing.asyncio, "sleep", instant)


def make_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def run(coro):
    return asyncio.run(coro)


def test_parse_fuelhh_keeps_only_wind_and_canonicalises_time():
    rows = ing.parse_fuelhh(FUELHH)
    assert rows == [("2026-01-02T00:00:00Z", 15228.0), ("2026-01-02T00:30:00Z", 15505.0)]
    assert ing.parse_fuelhh({"data": FUELHH}) == rows          # wrapped payload shape
    assert ing.parse_fuelhh([{"fuelType": "WIND", "startTime": "2026-01-02T01:00:00+00:00", "generation": 1}]) == [
        ("2026-01-02T01:00:00Z", 1.0)]                         # offset form -> canonical Z form


def test_parse_windfor_skips_incomplete_rows():
    rows = ing.parse_windfor(WINDFOR + [{"publishTime": "2026-01-01T07:30:00Z", "startTime": None, "generation": 1}])
    assert len(rows) == 2 and rows[0][0] == "2026-01-01T07:30:00Z"


def ok_handler(request: httpx.Request) -> httpx.Response:
    if "FUELHH" in request.url.path:
        assert request.url.params["settlementDateFrom"] == ing.ACTUALS_DATE_FROM
        return httpx.Response(200, json=FUELHH)
    assert request.url.params["publishDateTimeFrom"] == ing.FC_PUBLISH_FROM
    return httpx.Response(200, json=WINDFOR)


def test_build_snapshot_writes_audited_database(tmp_path):
    target = tmp_path / "snap.sqlite"

    async def go():
        async with make_client(ok_handler) as c:
            return await ing.build_snapshot(c, target)

    audit = run(go())
    assert audit["actual_rows"] == 2 and audit["forecast_rows"] == 2 and audit["forecast_runs"] == 2
    assert dict(audit["publish_cadence"]) == {"07:30": 1, "09:30": 1}
    assert not target.with_name(target.name + ".tmp").exists()
    conn = sqlite3.connect(target)
    assert conn.execute("SELECT COUNT(*) FROM forecast_generation").fetchone()[0] == 2
    conn.close()


def seed_old_db(path):
    ing.init_db(path)
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO actual_generation VALUES ('2026-01-02T00:00:00Z', 1.0)")
    conn.commit()
    conn.close()


def assert_old_db_intact(path):
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT generation_mw FROM actual_generation").fetchall() == [(1.0,)]
    conn.close()
    assert not path.with_name(path.name + ".tmp").exists()


def test_failed_forecast_fetch_leaves_existing_snapshot_untouched(tmp_path):
    target = tmp_path / "snap.sqlite"
    seed_old_db(target)

    def handler(request):
        return httpx.Response(200, json=FUELHH) if "FUELHH" in request.url.path else httpx.Response(503, text="down")

    async def go():
        async with make_client(handler) as c:
            await ing.build_snapshot(c, target)

    with pytest.raises(RuntimeError, match="503"):
        run(go())
    assert_old_db_intact(target)


def test_non_retryable_error_fails_fast(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(404, text="nope")

    async def go():
        async with make_client(handler) as c:
            await ing.build_snapshot(c, tmp_path / "x.sqlite")

    with pytest.raises(RuntimeError, match="404"):
        run(go())
    assert len(calls) == 1


def test_zero_wind_rows_is_an_error_not_an_empty_database(tmp_path):
    target = tmp_path / "snap.sqlite"
    seed_old_db(target)

    def handler(request):
        return httpx.Response(200, json=[{"fuelType": "CCGT", "startTime": "2026-01-02T00:00:00Z", "generation": 1}])

    async def go():
        async with make_client(handler) as c:
            await ing.build_snapshot(c, target)

    with pytest.raises(RuntimeError, match="Zero WIND"):
        run(go())
    assert_old_db_intact(target)


def test_transient_errors_are_retried_then_succeed(tmp_path):
    attempts = {"n": 0}

    def handler(request):
        if "FUELHH" in request.url.path:
            attempts["n"] += 1
            if attempts["n"] < 3:
                return httpx.Response(502, text="bad gateway")
            return httpx.Response(200, json=FUELHH)
        return httpx.Response(200, json=WINDFOR)

    async def go():
        async with make_client(handler) as c:
            return await ing.build_snapshot(c, tmp_path / "snap.sqlite")

    assert run(go())["actual_rows"] == 2 and attempts["n"] == 3
