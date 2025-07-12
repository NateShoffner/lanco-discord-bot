import os
import sys

COG_DIR = os.path.join("app", "cogs")


def main():
    if len(sys.argv) < 2:
        print("Usage: poetry run create-cog <name> [description]")
        sys.exit(1)

    name = sys.argv[1]
    description = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else f"{name} cog"

    dir_path = os.path.join(COG_DIR, name)
    file_path = os.path.join(dir_path, f"{name}.py")
    template_path = os.path.join(
        os.path.dirname(__file__), "templates", "cog_template.py"
    )
    readme_path = os.path.join(
        os.path.dirname(__file__), "templates", "readme_template.md"
    )

    if not os.path.exists(template_path):
        print("Template file not found.")
        sys.exit(1)

    if os.path.exists(dir_path):
        print(f"❌ Directory {dir_path} already exists.")
        sys.exit(1)

    if os.path.exists(file_path):
        print(f"❌ File {file_path} already exists.")
        sys.exit(1)

    os.makedirs(dir_path)

    with open(template_path, "r") as f:
        template = f.read()

    rendered = template.replace("COGNAME", name).replace("COGDESCRIPTION", description)

    with open(file_path, "w") as f:
        f.write(rendered)

    print(f"✅ Cog '{name}' created at {file_path}")

    with open(readme_path, "r") as f:
        readme_template = f.read()

    readme_rendered = readme_template.replace("COGNAME", name).replace(
        "COGDESCRIPTION", description
    )

    readme_file_path = os.path.join(dir_path, "README.md")
    with open(readme_file_path, "w") as f:
        f.write(readme_rendered)

    print(f"✅ README created at {readme_file_path}")
