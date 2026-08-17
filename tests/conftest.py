import os
import sys

# Set before any app import triggers DB init. BOT_ENV=test also stops main's
# loader falling back to a developer's .env, which would replace the in-memory
# database below with the real one and pull in live credentials.
os.environ.setdefault("BOT_ENV", "test")
os.environ.setdefault("DB_TYPE", "sqlite")
os.environ.setdefault("SQLITE_DB", ":memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
