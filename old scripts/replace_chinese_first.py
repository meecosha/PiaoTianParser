import re
import json
from pathlib import Path

# === Paths ===
GLOSSARY_PATH = "../glossary.json"  # Your glossary file
INPUT_FILE = "../piaotian_chapters/ch0215.txt"  # Raw Chinese chapter file
OUTPUT_FILE = "../annotated_ch0215.md"  # Annotated result

# === Load Files ===
with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
    glossary = json.load(f)

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    text = f.read()

# === Annotate Function ===
def inject_glossary_annotations(text, glossary):
    for hanzi, translation in sorted(glossary.items(), key=lambda x: len(x[0]), reverse=True):
        # Skip if already followed by a parenthesis (镇魂石 (Soul-Calming Stone))
        pattern = re.escape(hanzi) + r"(?!\s*\()"
        replacement = f"{hanzi} ({translation})"
        text = re.sub(pattern, replacement, text)
    return text

# === Process and Save ===
annotated_text = inject_glossary_annotations(text, glossary)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(annotated_text)

print(f"✅ Annotated file saved to {OUTPUT_FILE}")
