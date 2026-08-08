"""
Baseline DB behavior tests, spanning both ORMs during the issue #149 cutover.

These exist to freeze behavior across the Peewee -> Tortoise migration so we
have something concrete to diff against:
- every cog model can be created, fetched, and deleted with its declared
  fields intact (including composite-key and explicit-PK models)
- get_or_create() is idempotent under sequential calls

Models are discovered per ORM, so a model moves from the Peewee list to the
Tortoise list the moment it is ported and added to db.TORTOISE_MODEL_MODULES.
Both parametrized suites stay green throughout; the counts shifting between
them is the migration's progress bar.

Caveat: neither harness binds to the production SqliteQueueDatabase from
app/main.py's init_db(). The write-queue race that issue #149 is actually
about only manifests through that background write thread, so these tests
intentionally do NOT attempt to reproduce it (doing so under a real queue is
timing-dependent and would be flaky in CI). They establish correctness of
ordinary CRUD, not concurrency safety; the concurrent get_or_create
regression test lands with the race-workaround reconciliation.
"""

import importlib
import importlib.util
import os
import sys
import uuid
from datetime import date, datetime

from peewee import (
    AutoField,
    BigIntegerField,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    FloatField,
    IntegerField,
    TextField,
    UUIDField,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pytest
from db import BaseModel
from tortoise import Tortoise, fields

COGS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "cogs")


def _import_all_models():
    """Import every cogs/*/models.py plus the shared utils.config module so
    every Peewee model in the codebase is registered as a BaseModel subclass
    before we walk the class tree.

    Each models.py is loaded directly by file path (not via
    `cogs.<name>.models`), because a dotted import runs the cog package's
    __init__.py first, which pulls in the full cog module (e.g. filefixer's
    __init__ imports cairosvg, which needs a native cairo lib that isn't
    installed on dev machines). models.py files only import from db/peewee/
    utils/other cogs' models, none of which touch optional runtime deps, so
    this sidesteps that entirely.
    """
    importlib.import_module("utils.config")
    for entry in sorted(os.scandir(COGS_DIR), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        models_path = os.path.join(entry.path, "models.py")
        if not os.path.isfile(models_path):
            continue
        module_name = f"_baseline_models_{entry.name}"
        spec = importlib.util.spec_from_file_location(module_name, models_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)


def _leaf_subclasses(cls):
    for sub in cls.__subclasses__():
        if not sub.__subclasses__():
            yield sub
        else:
            yield from _leaf_subclasses(sub)


def _all_concrete_models():
    """Every leaf subclass of the shared Peewee BaseModel. 'Leaf' excludes
    shared abstract bases like EmbedFixConfigBase that are never queried
    directly, only their per-cog subclasses are real tables.

    Shrinks as models are ported to Tortoise; the ported ones are picked up by
    TORTOISE_MODELS below instead.
    """
    _import_all_models()
    seen = {}
    for cls in _leaf_subclasses(BaseModel):
        seen[id(cls)] = cls
    return sorted(seen.values(), key=lambda c: c.__name__)


ALL_MODELS = _all_concrete_models()


_FIELD_GENERATORS = {
    BigIntegerField: lambda i: 10_000_000_000 + i,
    IntegerField: lambda i: 1000 + i,
    FloatField: lambda i: 1.5 + i,
    BooleanField: lambda i: True,
    CharField: lambda i: f"test-value-{i}",
    TextField: lambda i: f"test text {i}",
    DateTimeField: lambda i: datetime(2026, 1, 1),
    DateField: lambda i: date(2026, 1, 1),
    UUIDField: lambda i: uuid.uuid4(),
}


def _sample_kwargs(model, i):
    kwargs = {}
    for name, field in model._meta.fields.items():
        if isinstance(field, AutoField):
            continue
        for field_type, generate in _FIELD_GENERATORS.items():
            if isinstance(field, field_type):
                kwargs[name] = generate(i)
                break
        else:
            raise AssertionError(
                f"{model.__name__}.{name} is a {type(field).__name__} with no "
                "sample-value generator; add one to _FIELD_GENERATORS in "
                "tests/test_db_baseline.py"
            )
    return kwargs


def _fetch(model, obj):
    pk = model._meta.primary_key
    if hasattr(pk, "field_names"):  # CompositeKey
        clause = None
        for field_name in pk.field_names:
            term = getattr(model, field_name) == getattr(obj, field_name)
            clause = term if clause is None else (clause & term)
        return model.get(clause)
    return model.get_by_id(obj.get_id())


# Fields whose value is intentionally overwritten by custom model logic
# (e.g. a save() override) rather than being stored as-passed. Verified by
# reading each model's own code, not guessed: don't add an entry here just
# to silence a failure without checking why the field diverged first.
_COMPUTED_ON_SAVE = {
    "UserProfile": {"last_updated"},  # save() stamps utcnow(), see profile/models.py
}


@pytest.mark.parametrize("model", ALL_MODELS, ids=lambda m: m.__name__)
def test_model_crud_roundtrip(model, test_db):
    """Every cog model round-trips create -> fetch -> delete with its
    declared fields intact, including composite-key and explicit-PK models."""
    test_db.create_tables([model], safe=True)
    kwargs = _sample_kwargs(model, ALL_MODELS.index(model))
    computed = _COMPUTED_ON_SAVE.get(model.__name__, set())

    obj = model.create(**kwargs)
    for name, value in kwargs.items():
        if name in computed:
            assert (
                getattr(obj, name) is not None
            ), f"{model.__name__}.{name} is computed on save but was left unset"
            continue
        assert (
            getattr(obj, name) == value
        ), f"{model.__name__}.{name} mismatch immediately after create()"

    fetched = _fetch(model, obj)
    for name, value in kwargs.items():
        if name in computed:
            continue
        assert (
            getattr(fetched, name) == value
        ), f"{model.__name__}.{name} mismatch after fetching a fresh instance"

    fetched.delete_instance()
    assert model.select().count() == 0


def test_get_or_create_is_idempotent(test_db):
    """Sequential get_or_create() calls for the same key return the same row
    exactly once, this is the pattern used across autoreact, autoresponse,
    webpreview, dadjoke, etc. It's the same call shape as the facebookembed
    race in issue #149, minus the concurrency (see module docstring)."""
    from utils.config import GuildConfig

    test_db.create_tables([GuildConfig], safe=True)

    config1, created1 = GuildConfig.get_or_create(guild_id=555)
    config2, created2 = GuildConfig.get_or_create(guild_id=555)

    assert created1 is True
    assert created2 is False
    assert config1.id == config2.id
    assert GuildConfig.select().where(GuildConfig.guild_id == 555).count() == 1


# ---------------------------------------------------------------------------
# Tortoise side (issue #149) -- same guarantees, for models already ported.
# ---------------------------------------------------------------------------


def _tortoise_models():
    """Every model registered in the Tortoise app registry.

    Unlike the Peewee side there is no subclass walking: Tortoise requires
    models be declared up front via db.TORTOISE_MODEL_MODULES, and its registry
    already excludes abstract bases, so the registry IS the model list. Reading
    it requires an initialized Tortoise, so this runs inside the fixture rather
    than at import time (which is why the Tortoise suite is parametrized
    indirectly, via a fixture, instead of at collection time like ALL_MODELS).
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
    assert models, "no Tortoise models registered -- check TORTOISE_MODEL_MODULES"

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
    exactly once -- the Tortoise counterpart of the Peewee test above, and the
    same call shape as the facebookembed race, minus the concurrency."""
    from models import BlacklistedUser

    user1, created1 = await BlacklistedUser.get_or_create(user_id=777)
    user2, created2 = await BlacklistedUser.get_or_create(user_id=777)

    assert created1 is True
    assert created2 is False
    assert user1.pk == user2.pk
    assert await BlacklistedUser.filter(user_id=777).count() == 1
