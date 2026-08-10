"""DB layer: seeding, assertions, FK enforcement, accessor ownership."""

from __future__ import annotations

import dataclasses

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from kdri import reports as acc
from kdri.db import (
    Base,
    ChatMessage,
    Interaction,
    KdriBand,
    Nutrient,
    make_engine,
    make_session_factory,
)
from kdri.seed import load_engine_inputs, run_seed_assertions, seed_all


@pytest.fixture
def sf():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def test_seed_assertions_pass_on_real_data():
    run_seed_assertions(load_engine_inputs(demo=False))


def test_seed_assertions_fail_on_dropped_band():
    inp = load_engine_inputs(demo=False)
    inp.bands = inp.bands[:-1]  # 299 rows
    with pytest.raises(AssertionError):
        run_seed_assertions(inp)


def test_seed_writes_300_bands_and_30_nutrients(sf):
    with sf() as s:
        seed_all(s)
        assert s.execute(select(func.count()).select_from(KdriBand)).scalar_one() == 300
        assert s.execute(select(func.count()).select_from(Nutrient)).scalar_one() == 30
        assert s.execute(select(func.count()).select_from(Interaction)).scalar_one() == 6


def test_reseed_is_idempotent(sf):
    with sf() as s:
        seed_all(s)
        first = s.execute(select(func.count()).select_from(KdriBand)).scalar_one()
        seed_all(s)
        second = s.execute(select(func.count()).select_from(KdriBand)).scalar_one()
        assert first == second == 300


def test_pragma_foreign_keys_enforced(sf):
    with sf() as s:
        assert s.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        # report_id references a non-existent report -> FK violation
        s.add(ChatMessage(report_id=999999, role="user", content="hi"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_delete_report_cascades_chat_and_nulls_children(sf):
    with sf() as s:
        parent = acc.create_report(s, "sidA", {"p": 1}, [], {})
        child = acc.create_report(s, "sidA", {"p": 2}, [], {}, parent_id=parent.id)
        acc.add_chat_message(s, parent.id, "user", "why?")
        assert acc.get_chat_messages(s, parent.id)

        acc.delete_report(s, parent.id, "sidA")
        assert not acc.get_chat_messages(s, parent.id)  # cascaded
        s.refresh(child)
        assert child.parent_id is None  # SET NULL, chain survives


def test_accessor_ownership_isolation(sf):
    with sf() as s:
        r = acc.create_report(s, "sidA", {"p": 1}, [], {})
        assert acc.get_report_owned(s, r.id, "sidA") is not None
        assert acc.get_report_owned(s, r.id, "sidB") is None  # 404-not-403
        assert acc.delete_report(s, r.id, "sidB") is False
