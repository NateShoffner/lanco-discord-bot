import importlib.util
import logging
import os
import sys
from enum import Enum

from peewee import *

# Aliased deliberately: `from peewee import *` above exports a `Model` name, so
# importing Tortoise's unaliased would shadow it and silently reparent the
# Peewee BaseModel below onto Tortoise.
from tortoise.models import Model as TortoiseModel

database_proxy = DatabaseProxy()


class DatabaseType(Enum):
    SQLITE = "sqlite"
    MYSQL = "mysql"

    @classmethod
    def from_str(cls, value: str) -> "DatabaseType":
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Unsupported database type: {value}")


class BaseModel(Model):
    class Meta:
        database = database_proxy


# --- Tortoise ORM (issue #149 cutover) ---
#
# Peewee's BaseModel/database_proxy above stay in place, unchanged, until
# every cog model has been ported off them (tracked in the migration plan).
# Until then both ORMs hold a live connection to the same database at once,
# which is safe for SQLite/MySQL (both support multiple connections to one
# database) and is the intended, temporary shape of an in-branch cutover.

TORTOISE_APP_LABEL = "models"

# App-level model modules, imported normally (they have no cog package around
# them). Cog models are found by discover_model_modules() below.
APP_MODEL_MODULES: tuple[str, ...] = ("models",)

# Model files to look for inside each cog. geoguesser keeps its Peewee models
# in dbmodels.py rather than models.py, so both names are scanned.
COG_MODEL_FILENAMES: tuple[str, ...] = ("models.py", "dbmodels.py")

logger = logging.getLogger(__name__)


def get_sqlite_path() -> str:
    return os.getenv("SQLITE_DB", "data/lancobot.db")


def _import_by_path(dotted: str, path: str):
    """Import a module from an explicit file path, cached under its real dotted
    name. Both halves are load-bearing:

    - Executing the file directly means the cog package's __init__.py never
      runs, so database init doesn't depend on every cog (and every optional
      native dependency a cog might import) loading cleanly. One cog with a
      missing dependency should fail that cog, not the whole database layer.
    - Caching under the real dotted name means the cog's own
      `from .models import X` resolves to *this* module object rather than
      importing the file a second time. Without it there are two distinct
      copies of every model class: the one registered with Tortoise, and the
      one the cog actually queries through, which has no connection bound and
      fails with "default_connection ... cannot be None".
    """
    cached = sys.modules.get(dotted)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(dotted, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[dotted] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[dotted]
        raise
    return module


def _has_tortoise_models(module) -> bool:
    """True if the module defines at least one concrete Tortoise model.

    Filters out modules that are still on Peewee, and ones whose only Model
    subclasses are abstract bases. Without this, Tortoise warns "Module ... has
    no models" for every unported cog.
    """
    for value in vars(module).values():
        if (
            isinstance(value, type)
            and issubclass(value, TortoiseModel)
            and value is not TortoiseModel
            and not value._meta.abstract
        ):
            return True
    return False


def discover_model_modules() -> list[str]:
    """Dotted names of every module holding Tortoise models.

    Cog model files are discovered by scanning app/cogs rather than being
    listed by hand, so adding a cog with models needs no registration step.
    Mirrors how main.py already auto-loads every cog from that directory.

    Order is irrelevant: this codebase has no ForeignKeys, so there is no
    model-registration ordering to get right.
    """
    modules = list(APP_MODEL_MODULES)
    cogs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cogs")
    if not os.path.isdir(cogs_dir):
        return modules

    for entry in sorted(os.scandir(cogs_dir), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        for filename in COG_MODEL_FILENAMES:
            path = os.path.join(entry.path, filename)
            if not os.path.isfile(path):
                continue
            dotted = f"cogs.{entry.name}.{filename[:-3]}"
            try:
                module = _import_by_path(dotted, path)
            except Exception as e:
                # A broken or unportable model file must not take down DB init.
                logger.warning("Skipping %s: %s: %s", dotted, type(e).__name__, e)
                continue
            if _has_tortoise_models(module):
                modules.append(dotted)
    return modules


def build_tortoise_config() -> dict:
    """Tortoise-ORM config dict for whichever DB_TYPE is configured, mirroring
    init_db()'s sqlite/mysql branch so both ORMs point at the same database."""
    db_type_str = os.getenv("DB_TYPE", "sqlite")
    db_type = DatabaseType.from_str(db_type_str)

    if db_type == DatabaseType.SQLITE:
        sqlite_path = get_sqlite_path()
        db_dir = os.path.dirname(sqlite_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        connection = {
            "engine": "tortoise.backends.sqlite",
            # Extra credentials are applied as PRAGMAs by Tortoise's sqlite
            # backend. journal_mode=WAL and foreign_keys=ON are already its
            # defaults (matching init_db()'s Peewee pragmas); busy_timeout is
            # not, so set it to mirror Peewee's timeout=5 (seconds -> ms) and
            # wait out a held write lock instead of raising "database is
            # locked" while both ORMs share the file during the cutover.
            "credentials": {"file_path": sqlite_path, "busy_timeout": 5000},
        }
    elif db_type == DatabaseType.MYSQL:
        connection = {
            "engine": "tortoise.backends.mysql",
            "credentials": {
                "host": os.getenv("MYSQL_HOST"),
                "port": int(os.getenv("MYSQL_PORT", 3306)),
                "user": os.getenv("MYSQL_USER"),
                "password": os.getenv("MYSQL_PASSWORD"),
                "database": os.getenv("MYSQL_DB"),
            },
        }
    else:
        raise ValueError(f"Unsupported database type: {db_type_str}")

    return {
        "connections": {"default": connection},
        "apps": {
            TORTOISE_APP_LABEL: {
                "models": discover_model_modules(),
                "default_connection": "default",
            }
        },
        "use_tz": False,
    }
