"""
Baseline DB behavior tests (issue #149).

Every model can be created, fetched, and deleted with its declared fields
intact, and get_or_create() is idempotent under sequential calls.

Originally these ran against both ORMs so a model moved from the Peewee suite
to the Tortoise one the moment it was converted, with the counts shifting
between them acting as the migration's progress bar. The Peewee half has now
been removed: no Peewee models remain.

Caveat: this harness does not bind to the production SqliteQueueDatabase that
app/main.py's init_db() used. The write-queue race issue #149 is about only
manifested through that background write thread, so these tests do not attempt
to reproduce it (doing so under a real queue is timing-dependent and would be
flaky in CI). They establish correctness of ordinary CRUD plus the specific
get_or_create race behaviour documented on the two tests at the bottom.
"""

import os
import sys
import uuid
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pytest
from tortoise import Tortoise, fields

# ---------------------------------------------------------------------------
# Tortoise side (issue #149) -- same guarantees, for models already ported.
# ---------------------------------------------------------------------------


def _tortoise_models():
    """Every model registered in the Tortoise app registry.

    There is no subclass walking: Tortoise requires models be declared up
    front (see db.discover_model_modules), and its registry already excludes
    abstract bases, so the registry IS the model list. Reading it requires an
    initialized Tortoise, so this runs inside the fixture rather than at import
    time, which is why this suite iterates instead of parametrizing.
    """
    return sorted(Tortoise.apps["models"].values(), key=lambda m: m.__name__)


_TORTOISE_FIELD_GENERATORS = {
    fields.BigIntField: lambda i: 10_000_000_000 + i,
    fields.IntField: lambda i: 1000 + i,
    fields.FloatField: lambda i: 1.5 + i,
    fields.BooleanField: lambda i: True,
    fields.CharField: lambda i: f"test-value-{i}",
    fields.TextField: lambda i: f"test text {i}",
    fields.DatetimeField: lambda i: datetime(2026, 1, 1),
    fields.DateField: lambda i: date(2026, 1, 1),
    fields.UUIDField: lambda i: uuid.uuid4(),
}


def _tortoise_sample_kwargs(model, i):
    kwargs = {}
    for name, field in model._meta.fields_map.items():
        # Generated PKs are assigned by the DB. auto_now/auto_now_add are
        # stamped on save, so passing a value would be silently overwritten.
        if getattr(field, "generated", False):
            continue
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            continue
        for field_type, generate in _TORTOISE_FIELD_GENERATORS.items():
            if isinstance(field, field_type):
                kwargs[name] = generate(i)
                break
        else:
            raise AssertionError(
                f"{model.__name__}.{name} is a {type(field).__name__} with no "
                "sample-value generator; add one to _TORTOISE_FIELD_GENERATORS "
                "in tests/test_db_baseline.py"
            )
    return kwargs


async def test_tortoise_models_crud_roundtrip(tortoise_db):
    """Every ported model round-trips create -> fetch -> delete with its
    declared fields intact.

    Iterates inside one test rather than parametrizing, because the model list
    only exists once Tortoise is initialized (i.e. after the fixture runs),
    which is too late for collection-time parametrization.
    """
    models = _tortoise_models()
    assert models, "no Tortoise models registered -- check discover_model_modules()"

    for i, model in enumerate(models):
        kwargs = _tortoise_sample_kwargs(model, i)
        obj = await model.create(**kwargs)

        for name, value in kwargs.items():
            assert (
                getattr(obj, name) == value
            ), f"{model.__name__}.{name} mismatch immediately after create()"

        fetched = await model.get(pk=obj.pk)
        for name, value in kwargs.items():
            assert (
                getattr(fetched, name) == value
            ), f"{model.__name__}.{name} mismatch after fetching a fresh instance"

        await fetched.delete()
        assert await model.all().count() == 0, f"{model.__name__} not deleted"


async def test_tortoise_get_or_create_is_idempotent(tortoise_db):
    """Sequential get_or_create() calls for the same key return the same row
    exactly once -- the same call shape as the facebookembed race that issue
    #149 documented, minus the concurrency."""
    from models import BlacklistedUser

    user1, created1 = await BlacklistedUser.get_or_create(user_id=777)
    user2, created2 = await BlacklistedUser.get_or_create(user_id=777)

    assert created1 is True
    assert created2 is False
    assert user1.pk == user2.pk
    assert await BlacklistedUser.filter(user_id=777).count() == 1


async def test_concurrent_get_or_create_does_not_duplicate(tortoise_db):
    """Eight simultaneous get_or_create() calls on one key yield exactly one row.

    Worth stating what this does and does not prove. Measured on Tortoise's
    SQLite backend, this does NOT reproduce the facebookembed race from issue
    #149: all eight calls resolve to one create and seven fetches, and zero
    IntegrityErrors are raised even with no fallback in place. The single
    connection behind an asyncio.Lock plus aiosqlite's speed means the
    SELECT-then-INSERT pair does not interleave in practice here.

    So this is a coarse smoke test, not the real guard. The deterministic one is
    below. Kept because it is the shape the cogs actually call, and a future
    change to Tortoise's connection handling (a pool, a different backend)
    could start making it interleave.
    """
    import asyncio

    from models import BlacklistedUser

    results = await asyncio.gather(
        *(BlacklistedUser.get_or_create(user_id=4242) for _ in range(8))
    )

    assert await BlacklistedUser.filter(user_id=4242).count() == 1
    assert all(row is not None for row, _ in results)
    assert sum(1 for _, created in results if created) == 1


async def test_integrity_error_fallback_recovers_the_row(tortoise_db):
    """The try/except IntegrityError fallback in embedfixcog, pinboard and r9k
    must actually work when the race it guards does occur.

    Rather than hoping the scheduler interleaves, this forces the exact losing
    sequence by hand: both callers observe no row, then both insert. The second
    insert violates the primary key, which is what the cogs catch. Without a
    unique constraint on the key this would silently create a duplicate instead
    of raising, so this also pins that the constraint exists.

    Delete the fallback in those cogs and this test still passes; its job is to
    prove the fallback is correct, and to document why the pattern is there so
    it does not get tidied away as redundant.
    """
    from models import BlacklistedUser
    from tortoise.exceptions import IntegrityError

    key = 5150

    # Both callers look, both miss. This is the state the race produces.
    assert await BlacklistedUser.get_or_none(user_id=key) is None
    assert await BlacklistedUser.get_or_none(user_id=key) is None

    winner = await BlacklistedUser.create(user_id=key, reason="first writer")

    with pytest.raises(IntegrityError):
        await BlacklistedUser.create(user_id=key, reason="second writer")

    # The loser's fallback path: re-read instead of propagating the error.
    recovered = await BlacklistedUser.get_or_none(user_id=key)
    assert recovered is not None
    assert recovered.pk == winner.pk
    assert recovered.reason == "first writer"
    assert await BlacklistedUser.filter(user_id=key).count() == 1
