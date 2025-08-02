import json
import re
from pathlib import Path

# === Configuration ===
INPUT_FILE = "../test_chatper_215_with_hanzi.txt"  # Input file (contains Hanzi)
OUTPUT_FILE = "../translated_test_chatper_215_with_hanzi.md"  # Output file (with replacements)
GLOSSARY_FILE = "../glossary.json"  # JSON glossary file

# === Load Files ===
text = Path(INPUT_FILE).read_text(encoding="utf-8")
glossary = json.loads(Path(GLOSSARY_FILE).read_text(encoding="utf-8"))

# === Replace Hanzi terms with bolded English translations ===
# Sort glossary keys by length to avoid partial replacement issues
sorted_terms = sorted(glossary.items(), key=lambda x: len(x[0]), reverse=True)

for hanzi, translation in sorted_terms:
    pattern = re.escape(hanzi)
    # Use regex to ensure full word match; optional: add \b boundaries if needed
    text = re.sub(pattern, f"**{translation}**", text)

# === Write output ===
Path(OUTPUT_FILE).write_text(text, encoding="utf-8")
print(f"✅ Hanzi replaced and saved to: {OUTPUT_FILE}")
