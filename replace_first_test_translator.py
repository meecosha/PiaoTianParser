import json
import re
from pathlib import Path
from dotenv import load_dotenv
import os
from openai import OpenAI

# === Setup ===
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === Configuration ===
RULES_PATH = "rules.md"
GLOSSARY_PATH = "glossary.json"
CHAPTER_DIR = "piaotian_chapters"
OUTPUT_DIR = "final_chapters"
MODEL = "gpt-4o-mini-2024-07-18"

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

def get_next_chapter_number():
    existing = list(Path(OUTPUT_DIR).glob("ch*.md"))
    chapter_nums = [int(re.search(r"ch(\d+)\.md", f.name).group(1)) for f in existing if re.search(r"ch(\d+)\.md", f.name)]
    return f"{(max(chapter_nums) + 1) if chapter_nums else 1:04}"

def load_file(path):
    return Path(path).read_text(encoding="utf-8").strip()

def save_file(path, content):
    Path(path).write_text(content.strip(), encoding="utf-8")

def call_gpt(system_prompt, user_prompt):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3
    )

    print("📊 Token Usage:")
    print(f"- Prompt tokens: {response.usage.prompt_tokens}")
    print(f"- Completion tokens: {response.usage.completion_tokens}")
    print(f"- Total tokens: {response.usage.total_tokens}")

    return response.choices[0].message.content

def merge_glossary(existing, new):
    updated = False
    for hanzi, translation in new.items():
        if hanzi not in existing:
            existing[hanzi] = translation
            updated = True
    return existing, updated

def annotate_with_glossary(text, glossary):
    for hanzi, translation in sorted(glossary.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = re.escape(hanzi) + r"(?!\s*\()"
        text = re.sub(pattern, f"{hanzi} ({translation})", text)
    return text

def main():
    chapter_num = get_next_chapter_number()
    print(chapter_num)
    chapter_file = f"ch{chapter_num}.txt"
    input_path = Path(CHAPTER_DIR) / chapter_file
    output_path = Path(OUTPUT_DIR) / f"ch{chapter_num}.md"

    rules = load_file(RULES_PATH)
    glossary = json.loads(load_file(GLOSSARY_PATH))
    chapter_text = load_file(input_path)

    annotated_text = annotate_with_glossary(chapter_text, glossary)

    system_prompt = "You are a professional xianxia translator. Follow all formatting and terminology instructions."
    user_prompt = f"""
IMPORTANT:
If a Hanzi term has an English translation in parentheses after it (like 修罗剑 (Shura Sword)), use that English name in your translation. Do not invent or re-translate it.

At the end of the translation, list any newly encountered Hanzi terms (not annotated) with their proposed English equivalents in this format:

```json
{{
  "Hanzi1": "English Term 1",
  "Hanzi2": "English Term 2"
}}
```

If there are no new terms, return:
```json
{{}}
```

Translate the following chapter according to these rules.

Translation rules:
{rules}

Chapter:
{annotated_text}
"""

    print(f"🚀 Translating Chapter {chapter_num}...")

    response = call_gpt(system_prompt, user_prompt)

    match = re.search(r"```json\s*({[\s\S]+?})\s*```", response)
    if not match:
        print("❌ Failed to find glossary block in GPT output.")
        return

    translation = response[:match.start()].strip()
    new_terms = json.loads(match.group(1))

    glossary, updated = merge_glossary(glossary, new_terms)
    if updated:
        with open(GLOSSARY_PATH, "w", encoding="utf-8") as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)
        print(f"📝 Appended {len(new_terms)} new glossary terms.")
    else:
        print("✅ No new glossary terms.")

    print("\n=== Final Translated Output ===\n")
    print(response)
    print("\n=== End of Output ===\n")

    save_file(output_path, translation)
    print(f"🎉 Chapter saved to: {output_path}")

if __name__ == "__main__":
    main()