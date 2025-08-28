import json
import re
from pathlib import Path
from dotenv import load_dotenv
import os
from datetime import datetime, timezone
from openai import OpenAI
from cleanup_chapters import transform

# === Setup ===
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === Configuration ===
RULES_PATH = "rules.md"
GLOSSARY_PATH = "glossary.json"
CHAPTER_DIR = "piaotian_chapters"
OUTPUT_DIR = "final_chapters"
INDEXED_DIR = "indexed_chapters"
PROMPT_DIR = "prompt_to_gpt"
# MODEL = "gpt-5-2025-08-07"
MODEL = "gpt-5-mini-2025-08-07"
# MODEL = "gpt-4o-mini-2024-07-18"
# MODEL = "gpt-4.1-mini-2025-04-14"
# MODEL = "gpt-4o-2024-08-06"
# MODEL = "o4-mini-2025-04-16"

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
Path(INDEXED_DIR).mkdir(parents=True, exist_ok=True)

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
        # match hanzi not followed by another Chinese char, unless already annotated
        pattern = re.escape(hanzi) + r"(?!\s*\[)"
        text = re.sub(pattern, f"{hanzi}[{translation}]", text)
    return text

def update_chapters_index(chapters_dir, output_file=None):
    """Regenerate chapters.json from all .md files in chapters_dir adding 'updated' UTC ISO timestamp."""
    import json, os

    if output_file is None:
        output_file = os.path.join(chapters_dir, "chapters.json")

    chapters = []
    for fname in sorted(os.listdir(chapters_dir)):
        if fname.endswith(".md"):
            path = os.path.join(chapters_dir, fname)
            # extract first non-empty line for title
            title = fname
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        title = line.lstrip("#").strip()
                        break
            mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat()
            chapters.append({
                "id": fname[:-3],
                "title": title,
                "updated": mtime
            })

    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(chapters, out, ensure_ascii=False, indent=2)

    print(f"📖 Updated {output_file} with {len(chapters)} chapters (with timestamps).")

def split_into_paragraphs(text: str):
    """Split raw chapter text into paragraphs for alignment.

    Rules:
    - Split on blank lines (two or more newlines with optional whitespace)
    - If the result is only 1 very long paragraph (> 1500 chars) and contains many single newlines,
      fallback to splitting on single newlines.
    - Trim whitespace; discard empty.
    """
    raw = text.strip().replace('\r\n', '\n')
    paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    if len(paras) == 1 and len(paras[0]) > 1500 and '\n' in paras[0]:
        # Fallback: treat each line as a paragraph if original lacked blank separators
        paras = [ln.strip() for ln in paras[0].split('\n') if ln.strip()]
    return paras

# =============================================================
# Main (refactored prompt)
# =============================================================

def main():
    # chapter_num = get_next_chapter_number()
    chapter_num = "0653"
    print(chapter_num)
    chapter_file = f"ch{chapter_num}.txt"
    input_path = Path(CHAPTER_DIR) / chapter_file
    output_path = Path(OUTPUT_DIR) / f"ch{chapter_num}.md"
    prompt_path = Path(PROMPT_DIR) / f"prompt_ch{chapter_num}.txt"
    indexed_path = Path(INDEXED_DIR) / f"ch{chapter_num}_indexed.md"
    obsidian_output_path = f"/Users/meecosha/MEGA/Vault/Martial Peak/1 to review/ch{chapter_num}.md"

    rules = load_file(RULES_PATH)
    glossary = json.loads(load_file(GLOSSARY_PATH))
    chapter_text = load_file(input_path)

    # Annotated Chinese first, then split into paragraphs for alignment.
    annotated_text = annotate_with_glossary(chapter_text, glossary)
    paragraphs = split_into_paragraphs(annotated_text)

    # Build indexed source string
    indexed_source_lines = []
    for idx, para in enumerate(paragraphs, start=1):
        # Collapse internal excessive whitespace; keep single spaces
        cleaned = re.sub(r"\s+", " ", para).strip()
        indexed_source_lines.append(f"@P{idx}: {cleaned}")
    indexed_source = "\n".join(indexed_source_lines)
    save_file(indexed_path, indexed_source)



    system_prompt = (
        "Professional Chinese→English xianxia translator. Priorities: fidelity, natural English, glossary adherence via inline annotations, zero omissions/additions. Do NOT invent details. Follow output contract exactly."
    )

    # (Token savings) — Do NOT embed entire glossary; rely on inline Hanzi[English] annotations only.

    user_prompt = f"""
SECTION 0: RESOURCES
RULES:
{rules}

SOURCE CHAPTER (paragraph indexed, existing glossary terms already annotated as Hanzi[English]):
{indexed_source}

TASKS (execute strictly in order):

Task 1: Translation
Produce ONE English paragraph for every source paragraph @P{{n}}. Do not merge, split, omit, or reorder. Leave a blank line between paragraphs.
Translate according to the RULES above. The whole chapter should be consistent in tone and style, like it's written in the RULES.
Use the glossary terms already embedded in the source as a guide, hint, recommendation to translate the terms consistently. There should be no Hanzi or square brackets remaining in your English translated output, even if they are written twice. Whatever is in parentheses, like gender in [Zhong Miaoke (female)] or type of artifact like in [Small Water-Nang (medicine)] is a glossary HINT, not something to be copied verbatim. If the glossary is completely unsuitable, use a better English term that fits the context.
Format exactly:
=== TRANSLATION START ===
@P1: ## Chapter # — Title of the Chapter

@P2: <English>

@P3: <English>
...
=== TRANSLATION END ===

Task 2: Fidelity Self-Check
If the translation is the best possible translation for the raw Chinese text, if every paragraph is faithful (no omission/addition/mistranslation/pronoun error/role error/subject-object reversal/term misuse/"lord or lady or sir" mistakes/herself or himself mistakes/"her or his" mistakes), output.
=== QA REPORT START ===\nOK\n=== QA REPORT END ===
Else, correct the translation and list the issues you corrected in the block like this:
=== QA REPORT START ===
@P7: issue_type=omission | Missing phrase "原文片段"
@P12: issue_type=pronoun | he → she (她)
...
=== QA REPORT END ===

Task 3: New Glossary Terms
Identify NEW proper nouns / sects / artifacts / beasts / techniques present in raw Hanzi that are NOT already annotated (i.e., do NOT appear as Hanzi[English]) and NOT obvious generic terms. Keys must be ≥2 Hanzi (unless a consistent mononym). Provide English; append (male) or (female) ONLY for people. Format:
=== GLOSSARY START ===
{{"新术语": "New Term"}}
=== GLOSSARY END ===
If none:
=== GLOSSARY START ===
{{}}
=== GLOSSARY END ===
Constraints:
- Do NOT repeat any Hanzi that appeared with [English] annotation.
- No guesses, no inferred variants, no Latin keys, no duplicates.

Order (strict):
1. Translation block
2. QA report block
3. Glossary block
4. Sentinel line: END-OF-OUTPUT

Global Prohibitions:
- No markdown fences ```
- No extra sections or commentary.
- Every @P index must appear exactly once in translation block.

END.
"""

    print("\n=== FINAL PROMPT SENT TO GPT (preview) ===\n")
    print(user_prompt)
    print("\n=== END PROMPT PREVIEW ===\n")

    print(f"🚀 Translating Chapter {chapter_num}...")
    response = call_gpt(system_prompt, user_prompt)

    text = response

    print("\n=== Raw Model Output (truncated) ===\n")
    print(text)
    print("\n=== End Raw Output ===\n")

    # ---------------- Extraction Phase ----------------
    # 1. Extract glossary JSON between markers first (we need to locate it to split translation).
    glossary_match = re.search(r"=== GLOSSARY START ===\s*({[\s\S]*?})\s*=== GLOSSARY END ===", text)
    reason = None
    if glossary_match:
        reason = "marker-based glossary block"
        raw_glossary_block = glossary_match.group(1)
    else:
        # Fallback to legacy fenced code parsing
        fenced = re.search(r"```json\s*({[\s\S]+?})\s*```", text, flags=re.IGNORECASE) or \
                 re.search(r"```\s*({[\s\S]+?})\s*```", text)
        if fenced:
            reason = "legacy fenced glossary block"
            raw_glossary_block = fenced.group(1)
        else:
            # Last resort: trailing JSON object
            trailing = re.search(r"({[\s\S]+})\s*$", text)
            if trailing:
                reason = "trailing JSON fallback"
                raw_glossary_block = trailing.group(1)
            else:
                print("❌ Could not locate a JSON glossary block.")
                return

    # Translation portion is everything before glossary start marker (preferred)
    if glossary_match:
        translation_section = text[:glossary_match.start()].strip()
    else:
        translation_section = text[:text.find(raw_glossary_block)].strip()

    # Parse glossary JSON
    try:
        new_terms = json.loads(raw_glossary_block)
    except json.JSONDecodeError as e:
        print("❌ Glossary JSON block could not be parsed:", e)
        print("Block preview:\n", raw_glossary_block[:500])
        return

    print(f"ℹ️ Glossary block found via: {reason}. Keys received: {len(new_terms)}")

    # Filter Hanzi keys ≥2 chars
    filtered_terms = {
        k: v for k, v in new_terms.items()
        if len(re.findall(r"[\u4e00-\u9fff]", k)) >= 2 and not k in glossary
    }
    if len(filtered_terms) != len(new_terms):
        skipped = [k for k in new_terms.keys() if k not in filtered_terms]
        if skipped:
            print(f"ℹ️ Filtered out existing or short/non-Hanzi keys: {skipped[:10]}{' …' if len(skipped) > 10 else ''}")

    glossary, added_count, updated_count, added_keys, updated_keys, skipped_keys = merge_glossary(
        glossary,
        filtered_terms,
        overwrite=False
    )

    if added_count or updated_count:
        with open(GLOSSARY_PATH, "w", encoding="utf-8") as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)
        msg = f"📝 Appended {added_count} new glossary term{'s' if added_count != 1 else ''}."
        if updated_count:
            msg += f" Updated {updated_count} entr{'ies' if updated_count != 1 else 'y'}."
        print(msg)
        if added_keys:
            print(f"   ➕ Added: {added_keys[:10]}{' …' if len(added_keys) > 10 else ''}")
    else:
        print("✅ No new glossary terms.")

    # Save translation (exclude QA & glossary sections for now – we keep everything before glossary)
    save_file(output_path, translation_section)



    save_file(prompt_path, user_prompt)

    cleaned = transform(translation_section)
    save_file(obsidian_output_path, cleaned)

    # Update index
    obsidian_chapters_dir = "/Users/meecosha/MEGA/Vault/Martial Peak/chapters"
    update_chapters_index(obsidian_chapters_dir, os.path.join(obsidian_chapters_dir, "chapters.json"))

    print(f"🎉 Chapter saved to: {output_path} and to Obsidian")


if __name__ == "__main__":
    main()
