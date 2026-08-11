# Migrations

Sequential schema changes applied by `migrate.py`.

```bash
poetry run migrate            # apply pending migrations
poetry run migrate --status   # list applied and pending migrations
```

The runner records each applied filename in the `schema_migrations` table, so a
migration runs once. The schema change and that bookkeeping row share a
transaction: if a migration raises, nothing is committed and it is retried on
the next run. (SQLite makes DDL transactional. MySQL commits implicitly on DDL,
so there the guarantee is best effort.)

Migrations run before the bot starts, ahead of the cogs that create their own
tables, so a table a migration targets may not exist yet. Operations against a
missing table are skipped rather than raising.

## Writing one

Create `NNN_short_description.py` with the next number. Files that do not match
`NNN_name.py` are ignored by the runner, so `helpers.py` and this README are
safe to keep here.

```python
"""One line describing the change, printed when the migration runs."""

from peewee import BooleanField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns("reddit_post", removed_by_reddit=BooleanField(default=False))
```

Rules:

- One `upgrade(ctx)` function per file. No work at import time, and never open
  your own connection: `ctx` owns the connection and the right migrator for the
  configured `DB_TYPE`.
- Never rename a migration file after it has shipped. The filename is the key in
  `schema_migrations`; renaming makes it look unapplied everywhere it already ran.
- Never edit a migration that has shipped. Add a new one, as 009 does for 008.
- Never import models from `app`. A migration is a snapshot of the schema at one
  point in time; a live model would silently change what an old migration does
  as the model evolves. Declare a local `Model` for new tables instead.

## Context API

Every operation is idempotent: it inspects the current schema first and logs a
skip when the change is already present. That matters because the tracking table
was added after several migrations had shipped, so a production database may
replay the whole history.

| Method | Purpose |
| --- | --- |
| `add_columns(table, **fields)` | Add each column that is missing |
| `drop_not_null(table, *columns)` | Make columns nullable |
| `rename_table(old, new)` | Rename, if `old` exists and `new` does not |
| `create_table(model)` | Create the table for a locally declared model |
| `create_index(table, name, columns, unique=False)` | Create a named index |
| `table_exists` / `column_exists` / `index_exists` | Introspection |
| `execute(sql, *params)` | Escape hatch for anything else |

`create_table` creates only the table. Declare indexes explicitly with
`create_index` so their names are stable rather than derived by Peewee.
