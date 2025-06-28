"""
Cog Metadata Validator and Extractor

Description:
This script recursively scans the 'cogs/' directory to:
1. Detect all cog classes inheriting from a base like 'LancoCog' or 'commands.Cog'.
2. Identify cogs that are missing a proper 'description' attribute.
3. Compile a list of all cogs with their 'name' and 'description' values.

Outputs:
- Prints a list of cogs missing descriptions.
- Prints a summary of cog names and descriptions.
"""

import ast
import os

COG_DIR = os.path.join("app", "cogs")

cog_report = []


def find_cog_classes(filepath):
    with open(filepath, "r", encoding="utf-8") as file:
        node = ast.parse(file.read(), filename=filepath)

    for class_node in [n for n in node.body if isinstance(n, ast.ClassDef)]:
        for base in class_node.bases:
            if isinstance(base, ast.Name) and base.id.endswith("Cog"):
                return class_node
            elif isinstance(base, ast.Attribute) and base.attr.endswith("Cog"):
                return class_node
    return None


def extract_cog_metadata(class_node):
    name_val = ""
    desc_val = ""
    for keyword in class_node.keywords:
        if keyword.arg == "name":
            name_val = ast.literal_eval(keyword.value)
        elif keyword.arg == "description":
            desc_val = ast.literal_eval(keyword.value)
    return name_val, desc_val


def analyze_cogs():
    for root, _, files in os.walk(COG_DIR):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                try:
                    class_node = find_cog_classes(full_path)
                    if class_node and isinstance(class_node, ast.ClassDef):
                        name, description = extract_cog_metadata(class_node)
                        cog_report.append(
                            {
                                "file": full_path,
                                "name": name,
                                "description": description,
                            }
                        )
                except Exception as e:
                    print(f"Error processing {full_path}: {e}")


def main():
    analyze_cogs()

    print("\nCog Summary:")
    for cog in cog_report:
        name = cog["name"] if cog["name"] else "Unnamed Cog"
        description = cog["description"] if cog["description"] else "No description"
        path = cog["file"]
        name_emoji = "✅" if cog["name"] else "❌"
        desc_emoji = "✅" if cog["description"] else "❌"
        print(f" - {name} {name_emoji} ({path}): {description} {desc_emoji}")
