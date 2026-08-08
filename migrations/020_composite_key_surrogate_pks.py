"""Replace composite primary keys with a surrogate `id` plus a unique index.

Tortoise ORM (issue #149) cannot express a multi-column primary key, so every
table Peewee declared with a CompositeKey needs a single-column key instead.
SQLite cannot add or change a primary key in place, so each affected table is
rebuilt: create the new shape, copy the rows, drop the original, rename.

Why this runs BEFORE the models are ported, rather than alongside: a Tortoise
model declaring `id` against a table that has no `id` column does NOT fail.
Tortoise quotes every column it selects, and SQLite resolves a double-quoted
identifier matching no column to a string literal instead of raising, so such a
model reads happily while assigning every row the literal string "id" as its
primary key. The corruption only surfaces on write. Rebuilding first means the
models are never pointed at a table that can't support them.

Column definitions are read from the live table at runtime rather than
hardcoded, because the databases in play have drifted from each other and from
the models; whatever is actually there is what gets carried across.

Idempotent: a table that already has an `id` column is skipped, so this is safe
to re-run.
"""

import os

from dotenv import load_dotenv
from peewee import SqliteDatabase

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))

# table -> columns whose combination was the old composite primary key, and
# which therefore gets a UNIQUE index to preserve that guarantee.
COMPOSITE_KEYS = {
    "ai_prompt_config": ("guild_id", "name"),
    "birthday_user": ("guild_id", "user_id"),
    "mark_safe_user": ("user_id", "guild_id", "event_id"),
    "pettax_user": ("user_id", "guild_id"),
    "pinboard_posts": ("pin_owner_id", "message_id"),
    "user_profile_links": ("user_id", "service"),
    "user_profiles": ("user_id", "name"),
    "reddit_feed_config": ("channel_id", "subreddit"),
    "reddit_post": ("post_id", "message_id"),
    "rss_feed_config": ("channel_id", "url"),
}

# custom_commands is rebuilt too, but deliberately gets NO unique index.
# Its live table has no primary key and no indexes at all -- the composite key
# its model declared was never actually enforced. Restoring that guarantee is a
# real behaviour change and is being handled as its own change, not smuggled in
# here. It costs nothing to defer: adding it later is a plain CREATE UNIQUE
# INDEX, which needs no second rebuild.
NO_UNIQUE_INDEX = {"custom_commands"}

TABLES = tuple(COMPOSITE_KEYS) + tuple(NO_UNIQUE_INDEX)


def _columns(table):
    """(name, type, notnull, default) for each column, in declaration order."""
    return [
        (row[1], row[2], row[3], row[4])
        for row in db.execute_sql(f'PRAGMA table_info("{table}")').fetchall()
    ]


def _column_sql(name, coltype, notnull, default):
    sql = f'"{name}" {coltype or "BLOB"}'
    if notnull:
        sql += " NOT NULL"
    if default is not None:
        sql += f" DEFAULT {default}"
    return sql


def _rebuild(table):
    columns = _columns(table)
    names = [c[0] for c in columns]

    if "id" in names:
        print(f"  {table}: already has an id column, skipping")
        return

    before = db.execute_sql(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]

    tmp = f"{table}__migrating"
    col_defs = ",\n    ".join(_column_sql(*c) for c in columns)
    quoted = ", ".join(f'"{n}"' for n in names)

    db.execute_sql(f'DROP TABLE IF EXISTS "{tmp}"')
    db.execute_sql(
        f'CREATE TABLE "{tmp}" (\n'
        f'    "id" INTEGER PRIMARY KEY AUTOINCREMENT,\n'
        f"    {col_defs}\n"
        f")"
    )
    db.execute_sql(f'INSERT INTO "{tmp}" ({quoted}) SELECT {quoted} FROM "{table}"')

    after = db.execute_sql(f'SELECT COUNT(*) FROM "{tmp}"').fetchone()[0]
    if after != before:
        raise RuntimeError(
            f"{table}: copied {after} rows but the original had {before}; aborting"
        )

    db.execute_sql(f'DROP TABLE "{table}"')
    db.execute_sql(f'ALTER TABLE "{tmp}" RENAME TO "{table}"')

    key = COMPOSITE_KEYS.get(table)
    if key:
        cols = ", ".join(f'"{c}"' for c in key)
        index = f"{table}_{'_'.join(key)}_uniq"
        db.execute_sql(f'CREATE UNIQUE INDEX "{index}" ON "{table}" ({cols})')
        print(f"  {table}: rebuilt with surrogate id, {after} rows, unique{key}")
    else:
        print(f"  {table}: rebuilt with surrogate id, {after} rows, no unique index")


def run():
    db.connect(reuse_if_open=True)
    existing = set(db.get_tables())

    # One transaction: either every table is rebuilt or the database is
    # untouched. A half-migrated schema would leave some models readable and
    # others silently broken.
    with db.atomic():
        for table in TABLES:
            if table not in existing:
                print(f"  {table}: not present, skipping")
                continue
            _rebuild(table)

    db.execute_sql("VACUUM")
