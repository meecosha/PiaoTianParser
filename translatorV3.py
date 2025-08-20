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
PROMPT_DIR = "prompt_to_gpt"
# MODEL = "gpt-5-2025-08-07"
# MODEL = "gpt-5-mini-2025-08-07"
# MODEL = "gpt-4o-mini-2024-07-18"
MODEL = "gpt-4.1-mini-2025-04-14"
# MODEL = "gpt-4o-2024-08-06"
# MODEL = "o4-mini-2025-04-16"

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
        # temperature=0.3
    )

    print("📊 Token Usage:")
    print(f"- Prompt tokens: {response.usage.prompt_tokens}")
    print(f"- Completion tokens: {response.usage.completion_tokens}")
    print(f"- Total tokens: {response.usage.total_tokens}")

    return response.choices[0].message.content

def merge_glossary(existing: dict, candidates: dict, *, overwrite: bool = False):
    """
    Merge `candidates` into `existing`.

    Returns:
        merged (dict): the updated glossary
        added_count (int): number of brand-new keys inserted
        updated_count (int): number of existing keys whose value was changed (only if overwrite=True)
        added_keys (list[str]): keys that were newly added
        updated_keys (list[str]): keys that were updated (only if overwrite=True)
        skipped_keys (list[str]): keys present in candidates but not applied (already existed and overwrite=False)
    """
    added_keys = []
    updated_keys = []
    skipped_keys = []

    for k, v in candidates.items():
        if k in existing:
            if overwrite and existing[k] != v:
                existing[k] = v
                updated_keys.append(k)
            else:
                skipped_keys.append(k)
        else:
            existing[k] = v
            added_keys.append(k)

    return existing, len(added_keys), len(updated_keys), added_keys, updated_keys, skipped_keys


def annotate_with_glossary(text, glossary):
    for hanzi, translation in sorted(glossary.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = re.escape(hanzi) + r"(?!\s*\()"
        text = re.sub(pattern, f"{hanzi}[{translation}]", text)
    return text

def update_chapters_index(chapters_dir, output_file=None):
    """Regenerate chapters.json from all .md files in chapters_dir."""
    import json, os

    if output_file is None:
        output_file = os.path.join(chapters_dir, "chapters.json")

    chapters = []
    for fname in sorted(os.listdir(chapters_dir)):
        if fname.endswith(".md"):
            path = os.path.join(chapters_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                # take the first non-empty line
                for line in f:
                    line = line.strip()
                    if line:
                        title = line.lstrip("#").strip()
                        break
                else:
                    title = fname
            chapters.append({"id": fname[:-3], "title": title})

    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(chapters, out, ensure_ascii=False, indent=2)

    print(f"📖 Updated {output_file} with {len(chapters)} chapters.")


def main():
    # chapter_num = get_next_chapter_number()
    chapter_num = "0009"
    print(chapter_num)
    chapter_file = f"ch{chapter_num}.txt"
    input_path = Path(CHAPTER_DIR) / chapter_file
    output_path = Path(OUTPUT_DIR) / f"ch{chapter_num}.md"
    prompt_path = Path(PROMPT_DIR) / f"prompt_ch{chapter_num}.txt"
    obsidian_output_path = f"/Users/meecosha/MEGA/Vault/Martial Peak/chapters/ch{chapter_num}.md"

    rules = load_file(RULES_PATH)
    glossary = json.loads(load_file(GLOSSARY_PATH))
    chapter_text = load_file(input_path)

    annotated_text = annotate_with_glossary(chapter_text, glossary)

    system_prompt = "You are a professional xianxia translator. Follow all formatting and terminology instructions."
    user_prompt = f"""
IMPORTANT:
If a Hanzi term has an English translation in square brackets after it (like 修罗剑[Shura Sword]), use that English translation in your translation. Don't include the square brackets in the final translated output.

After translating, you MUST perform a fact-checking and fidelity review by comparing your translation against the original Chinese text to ensure:
- All pronouns match the correct gender and refer to the right person.
- All names and titles are correct according t  o the glossary and the original text.
- Relationships (e.g., brother, cousin, master,     disciple) are accurately preserved.
- No meaning has been omitted, altered, or added.
- Contextually ambiguous terms (e.g., 大汉, 向家族, etc.) are interpreted correctly based on the scene.

Correct any issues found during this review before producing your final translation.

At the very end of your response, you MUST return only the new glossary terms (all names of characters, sects and places, animals, beasts, plants, techniques, skills, artifacts) that are present verbatim in the provided Chinese chapter text. Only include terms where the key is in Hanzi (Chinese characters) and appears exactly in the provided chapter. Do NOT add, infer, guess, or recall terms from memory, even if you are certain they exist elsewhere in the novel. Do not create alternate versions of known glossary entries — use only the exact form from the text. Do NOT include any entries without Chinese characters. If it's a character's name, include their gender in the glossary, but not in the translation. 
The glossary must be in this format:

```json
{{
  "示例一": "Example Translation One",
  "示例二": "Example Translation Two",
  "姓名": "Name (male)",
  "姓名": "Name (female)"
}}

If there are no new terms from this chapter, output exactly:

```json
{{}}
``` 

Do not include any explanation, comments, titles, or extra text before or after the JSON block. The block must be parsable by code as-is.

Translate the following chapter to english according to the rules below.
{rules}

Chapter:
{annotated_text}
"""

    print("\n=== FINAL PROMPT SENT TO GPT ===\n")
    print(user_prompt)
    print("\n=== END OF PROMPT ===\n")

    print(f"🚀 Translating Chapter {chapter_num}...")
    response = call_gpt(system_prompt, user_prompt)

    # --- Robust glossary block extraction ---
    text = response

    print("\n=== Final Translated Output ===\n")
    print(response)
    print("\n=== End of Output ===\n")

    # 1) Prefer ```json fenced
    m = re.search(r"```json\s*({[\s\S]+?})\s*```", text, flags=re.IGNORECASE)
    reason = "matched ```json fenced block"
    # 2) Fallback: any fenced code block containing a top-level JSON object
    if not m:
        m = re.search(r"```\s*({[\s\S]+?})\s*```", text)
        reason = "matched generic ``` fenced block"
    # 3) Fallback: last JSON-ish object in the message
    if not m:
        # Greedy to grab the last {...} chunk
        m = re.search(r"({[\s\S]+})\s*$", text)
        reason = "matched trailing {…} block (fallback)"

    if not m:
        print("❌ Could not locate a JSON glossary block. Showing tail of response for debugging:\n",
              text[-800:])
        return

    translation = text[:m.start()].strip()
    raw_glossary_block = m.group(1)

    try:
        new_terms = json.loads(raw_glossary_block)
    except json.JSONDecodeError as e:
        print("❌ Glossary JSON block could not be parsed:", e)
        print("Block preview:\n", raw_glossary_block[:500])
        return

    print(f"ℹ️ Glossary block found via: {reason}. Keys received: {len(new_terms)}")

    # ✅ Keep only terms whose KEY has 2+ Hanzi (Chinese characters)
    filtered_terms = {
        k: v for k, v in new_terms.items()
        if len(re.findall(r"[\u4e00-\u9fff]", k)) >= 2
    }
    if len(filtered_terms) != len(new_terms):
        skipped = [k for k in new_terms.keys() if k not in filtered_terms]
        print(f"ℹ️ Filtered out {len(skipped)} non-2+Hanzi keys: {skipped[:10]}{' …' if len(skipped) > 10 else ''}")

    # Merge (make sure your merge_glossary returns the 6-tuple as discussed)
    glossary, added_count, updated_count, added_keys, updated_keys, skipped_keys = merge_glossary(
        glossary,
        filtered_terms,
        overwrite=False
    )

    # Persist and report
    if added_count or updated_count:
        with open(GLOSSARY_PATH, "w", encoding="utf-8") as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)
        msg = f"📝 Appended {added_count} new glossary term{'s' if added_count != 1 else ''}."
        if updated_count:
            msg += f" Updated {updated_count} existing entr{'ies' if updated_count != 1 else 'y'}."
        print(msg)
        if added_keys:
            print(f"   ➕ Added keys: {added_keys[:10]}{' …' if len(added_keys) > 10 else ''}")
        if skipped_keys:
            print(f"   ↩️ Skipped (already existed): {skipped_keys[:10]}{' …' if len(skipped_keys) > 10 else ''}")
    else:
        print("✅ No new glossary terms.")

    save_file(output_path, translation)
    save_file(obsidian_output_path, translation)
    save_file(prompt_path, user_prompt)

    # After saving the chapter, update the website index
    obsidian_chapters_dir = "/Users/meecosha/MEGA/Vault/Martial Peak/chapters"
    update_chapters_index(obsidian_chapters_dir, os.path.join(obsidian_chapters_dir, "chapters.json"))

    print(f"🎉 Chapter saved to: {output_path} and to Obsidian")


if __name__ == "__main__":
    main()

