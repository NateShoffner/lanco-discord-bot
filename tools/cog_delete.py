import os
import shutil
import sys

COG_DIR = os.path.join("app", "cogs")


def main():
    if len(sys.argv) < 2:
        print("Usage: poetry run delete-cog delete <name>")
        sys.exit(1)

    name = sys.argv[1]
    dir_path = os.path.join(COG_DIR, name)

    if not os.path.exists(dir_path):
        print(f"❌ Directory {dir_path} does not exist.")
        sys.exit(1)

    try:
        shutil.rmtree(dir_path)
        print(f"✅ Cog '{name}' deleted successfully.")
    except Exception as e:
        print(f"❌ Failed to delete {dir_path}: {e}")
        sys.exit(1)
