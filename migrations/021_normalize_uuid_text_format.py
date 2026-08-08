"""Normalize UUID columns from bare hex to canonical dashed form.

Peewee's UUIDField wrote UUIDs as 32 hex characters with no dashes
("9b78ddb662ec4e7d946465d1b0090031"). Tortoise's UUIDField writes the canonical
36-character dashed form ("9b78ddb6-62ec-4e7d-9464-65d1b0090031").

Reading is unaffected, because uuid.UUID() accepts either spelling, which is
exactly what makes this dangerous: a ported model reads legacy rows perfectly
while every *filter* and *write* keyed on a UUID silently matches nothing. There
is no error. Measured against a copy of production before this migration:

    filter(event_id=<id read from that very table>) matched 0 of 8 rows
    save() on a legacy row updated 0 rows

So marksafe would report nobody as marked safe and then insert dashed-format
duplicates, and reminders would never be marked issued.

Only values that are exactly 32 hex characters are rewritten, so this is safe to
re-run and leaves already-normalized (or unrelated) values alone.
"""

import os
import re

from dotenv import load_dotenv
from peewee import SqliteDatabase

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))

# Every UUID-bearing column, found by scanning production for columns whose
# values are uniformly 32-char hex. Tables absent from a given database are
# skipped, so this covers deployments at different migration points.
UUID_COLUMNS = (
    ("geoguesser_locations", "id"),
    ("mark_safe_event", "id"),
    ("mark_safe_user", "event_id"),
    ("user_reminders", "id"),
    # Empty in production today, but included so a deployment that has rows in
    # them is normalized too.
    ("scheduled_posts", "id"),
    ("geoguesser_game_results", "game_id"),
    ("round_game_results", "game_id"),
)

_HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")


def _dashed(value: str) -> str:
    v = value.lower()
    return f"{v[0:8]}-{v[8:12]}-{v[12:16]}-{v[16:20]}-{v[20:32]}"


def run():
    db.connect(reuse_if_open=True)
    existing = set(db.get_tables())

    with db.atomic():
        for table, column in UUID_COLUMNS:
            if table not in existing:
                print(f"  {table}: not present, skipping")
                continue

            columns = {
                row[1] for row in db.execute_sql(f'PRAGMA table_info("{table}")')
            }
            if column not in columns:
                print(f"  {table}.{column}: column absent, skipping")
                continue

            rows = db.execute_sql(
                f'SELECT rowid, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL'
            ).fetchall()

            converted = 0
            for rowid, value in rows:
                if isinstance(value, str) and _HEX32.match(value):
                    db.execute_sql(
                        f'UPDATE "{table}" SET "{column}" = ? WHERE rowid = ?',
                        (_dashed(value), rowid),
                    )
                    converted += 1

            if converted:
                print(f"  {table}.{column}: normalized {converted} value(s)")
            else:
                print(f"  {table}.{column}: nothing to convert")
