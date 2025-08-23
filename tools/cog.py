import argparse
import ast
import os
import shutil

COG_DIR = os.path.join("app", "cogs")


def cmd_create(args: argparse.Namespace) -> int:
    """
    Creates a new cog folder under app/cogs/<name>/ with:
      - <name>.py rendered from templates/cog_template.py
      - README.md rendered from templates/readme_template.md
    """
    name = args.name
    description = args.description or f"{name} cog"

    dir_path = os.path.join(COG_DIR, name)
    file_path = os.path.join(dir_path, f"{name}.py")

    # Templates live relative to THIS file (same as your original script)
    base_dir = os.path.dirname(__file__)
    template_path = os.path.join(base_dir, "templates", "cog_template.py")
    readme_path = os.path.join(base_dir, "templates", "readme_template.md")

    if not os.path.exists(template_path):
        print("Template file not found.")
        return 1

    if os.path.exists(dir_path):
        print(f"❌ Directory {dir_path} already exists.")
        return 1

    if os.path.exists(file_path):
        print(f"❌ File {file_path} already exists.")
        return 1

    os.makedirs(dir_path, exist_ok=True)

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    rendered = template.replace("COGNAME", name).replace("COGDESCRIPTION", description)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"✅ Cog '{name}' created at {file_path}")

    with open(readme_path, "r", encoding="utf-8") as f:
        readme_template = f.read()

    readme_rendered = readme_template.replace("COGNAME", name).replace(
        "COGDESCRIPTION", description
    )

    readme_file_path = os.path.join(dir_path, "README.md")
    with open(readme_file_path, "w", encoding="utf-8") as f:
        f.write(readme_rendered)

    print(f"✅ README created at {readme_file_path}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """
    Deletes app/cogs/<name>/ recursively.
    """
    name = args.name
    dir_path = os.path.join(COG_DIR, name)

    if not os.path.exists(dir_path):
        print(f"❌ Directory {dir_path} does not exist.")
        return 1

    try:
        shutil.rmtree(dir_path)
        print(f"✅ Cog '{name}' deleted successfully.")
        return 0
    except Exception as e:
        print(f"❌ Failed to delete {dir_path}: {e}")
        return 1


# --------------------------
# report subcommand
# --------------------------
def _find_cog_class(filepath: str):
    with open(filepath, "r", encoding="utf-8") as file:
        node = ast.parse(file.read(), filename=filepath)

    for class_node in [n for n in node.body if isinstance(n, ast.ClassDef)]:
        for base in class_node.bases:
            # match FooCog, LancoCog, commands.Cog, etc.
            if isinstance(base, ast.Name) and base.id.endswith("Cog"):
                return class_node
            elif isinstance(base, ast.Attribute) and base.attr.endswith("Cog"):
                return class_node
    return None


def _extract_cog_metadata(class_node: ast.ClassDef) -> tuple[str, str]:
    """
    Try to extract name / description from keywords in class definition:
    class MyCog(commands.Cog, name="...", description="...")
    """
    name_val = ""
    desc_val = ""
    for keyword in getattr(class_node, "keywords", []) or []:
        if keyword.arg == "name":
            name_val = ast.literal_eval(keyword.value)
        elif keyword.arg == "description":
            desc_val = ast.literal_eval(keyword.value)
    return name_val, desc_val


def cmd_report(args: argparse.Namespace) -> int:
    """
    Recursively scan app/cogs for classes inheriting from *Cog and
    print a summary of cog name/description (✅/❌ when present/missing).
    """
    found_any = False
    print("\nCog Summary:")
    for root, _, files in os.walk(COG_DIR):
        for f in files:
            if not f.endswith(".py"):
                continue
            full_path = os.path.join(root, f)
            try:
                class_node = _find_cog_class(full_path)
                if class_node and isinstance(class_node, ast.ClassDef):
                    found_any = True
                    name, description = _extract_cog_metadata(class_node)
                    name_display = name or "Unnamed Cog"
                    desc_display = description or "No description"
                    name_emoji = "✅" if name else "❌"
                    desc_emoji = "✅" if description else "❌"
                    print(
                        f" - {name_display} {name_emoji} ({full_path}): {desc_display} {desc_emoji}"
                    )
            except Exception as e:
                print(f"Error processing {full_path}: {e}")
    if not found_any:
        print("No cogs found.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cog", description="Manage project cogs (create, delete, report)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Create a new cog")
    p_create.add_argument("name", help="Cog name (folder and file will use this)")
    p_create.add_argument(
        "description", nargs="?", help="Optional description (defaults to '<name> cog')"
    )
    p_create.set_defaults(func=cmd_create)

    p_delete = sub.add_parser("delete", help="Delete an existing cog")
    p_delete.add_argument("name", help="Cog name to delete (folder under app/cogs)")
    p_delete.set_defaults(func=cmd_delete)

    p_report = sub.add_parser("report", help="Report cog names & descriptions")
    p_report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
