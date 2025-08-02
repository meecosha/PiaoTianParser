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
RULES_PATH = "../rules.md"
GLOSSARY_PATH = "../glossary.json"
CHAPTER_DIR = "../piaotian_chapters"
OUTPUT_DIR = "../final_chapters"
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

def replace_with_glossary(text, glossary):
    for hanzi, eng in sorted(glossary.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = re.escape(hanzi)
        text = re.sub(pattern, f"**{eng}**", text)
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

    system_prompt = "You are a professional xianxia translator. Follow all formatting and terminology instructions."
    user_prompt = f"""
IMPORTANT:
When translating, you must leave certain terms untranslated in Hanzi, such as names, realms, techniques, sects, and artifacts.
However, you must treat these Hanzi terms as grammatically correct English nouns in the sentence.

This means:

### 1. Use Correct Articles ("a", "an", "the")

- Use "a" or "an" when introducing an indefinite item:
  - ✅ He drew **a 修罗剑**.
  - ✅ She unleashed **an 炎阳爆** technique.

- Use "the" when the term is specific, previously mentioned, or known in context:
  - ✅ He activated **the 镇魂石**.

### 2. Use Singular and Plural Correctly

- If the Hanzi noun refers to a plural idea, do not change the Hanzi. Adjust the sentence structure instead:
Pluralize Hanzi directly like this
  - ✅ 镇魂石s

### 3. Use Correct Subject-Verb Agreement

- Treat Hanzi nouns as singular or plural as appropriate:
  - ✅ **凌太虚** is powerful.
  - ✅ The **修罗剑** was glowing in the dark.

### 4. Use Possessive Form When Needed

- ✅ He entered **凌霄阁’s** inner court.
- ✅ She borrowed **梦无涯’s** artifact.

### 5. Think of Hanzi as English Nouns

Use the surrounding sentence as if the Hanzi were an English word:
- ✅ He held **the 修罗剑** tightly.
- ✅ They trained in **a 神游境** technique.

### Common Mistakes to Avoid

- ❌ He drew 修罗剑.  
  ✅ He drew **the 修罗剑**.

- ❌ She joined 鬼王谷.  
  ✅ She joined **the 鬼王谷**.

- ❌ He picked up 镇魂石 from the ground.  
  ✅ He picked up **a 镇魂石** from the ground.

- ❌ Many 万花宫 came.  
  ✅ Many **disciples from 万花宫** came.
  
3. At the end of the translation, list new untranslated terms with proposed English translations in this format:

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

Translate the chapter below:

Translation rules:
{rules}

Chapter:
{chapter_text}
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

    final_text = replace_with_glossary(translation, glossary)
    print("\n=== Final Translated Output ===\n")
    print(final_text)
    print("\n=== End of Output ===\n")
    save_file(output_path, final_text)
    print(f"🎉 Chapter saved to: {output_path}")

if __name__ == "__main__":
    main()