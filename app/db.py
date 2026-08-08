import os
from enum import Enum

from peewee import *

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

# Dotted module paths carrying Tortoise models. app/models.py is the single
# registry: it re-exports every ported model, loading each cog's models.py by
# file path so DB init never depends on cog packages importing cleanly. See
# that module's docstring. Order doesn't matter: there are no ForeignKeys
# anywhere in this codebase, so there's no registration ordering to get right.
TORTOISE_MODEL_MODULES: list[str] = [
    "models",
]


def get_sqlite_path() -> str:
    return os.getenv("SQLITE_DB", "data/lancobot.db")


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
                "models": TORTOISE_MODEL_MODULES,
                "default_connection": "default",
            }
        },
        "use_tz": False,
    }
