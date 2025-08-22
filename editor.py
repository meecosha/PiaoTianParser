# editor_pass.py
import json
import re
from pathlib import Path
from dotenv import load_dotenv
import os
from openai import OpenAI
import difflib

# === Setup ===
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === Configuration (mirrors your translator script and adds FINAL dir) ===
RULES_PATH = "rules.md"
GLOSSARY_PATH = "glossary.json"
RAW_DIR = "piaotian_chapters"          # chXXXX.txt (raw Chinese)
ANNOTATED_DIR = "annotated_chapters"
TRANSLATED_DIR = "final_chapters"      # chXXXX.md (draft English from pass #1)
FINAL_DIR = "final_edited_chapters"     # chXXXX.md (corrected English after editorial pass)
PROMPT_DIR = "prompt_to_gpt"           # store the exact prompt used for auditing
# MODEL = "gpt-5-2025-08-07"
MODEL = "gpt-5-mini-2025-08-07"
# MODEL = "gpt-4o-mini-2024-07-18"
# MODEL = "gpt-4.1-mini-2025-04-14"
# MODEL = "gpt-4o-2024-08-06"
# MODEL = "o4-mini-2025-04-16"

Path(FINAL_DIR).mkdir(parents=True, exist_ok=True)
Path(PROMPT_DIR).mkdir(parents=True, exist_ok=True)

# Optionally mirror to Obsidian (adjust as needed)
# OBSIDIAN_FINAL_DIR = "/Users/meecosha/MEGA/Vault/Martial Peak/final_chapters"
# Path(OBSIDIAN_FINAL_DIR).mkdir(parents=True, exist_ok=True)

# === Helpers (reused / aligned with your first script) ===
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
        # temperature=0.2,  # lower for fidelity edits
    )

    print("📊 Token Usage:")
    print(f"- Prompt tokens: {response.usage.prompt_tokens}")
    print(f"- Completion tokens: {response.usage.completion_tokens}")
    print(f"- Total tokens: {response.usage.total_tokens}")

    return response.choices[0].message.content

def annotate_with_glossary(text, glossary):
    """
    Same behavior as your translator: wraps Hanzi with [English] where known.
    This helps the editor consistently enforce fixed terms without re-inventing them.
    """
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

def scan_latest_chapter_num():
    """
    Find the highest chNNNN present in TRANSLATED_DIR (draft translations).
    """
    candidates = list(Path(TRANSLATED_DIR).glob("ch*.md"))
    nums = [
        int(m.group(1))
        for p in candidates
        if (m := re.search(r"ch(\d+)\.md$", p.name))
    ]
    return f"{max(nums):04}" if nums else None

def extract_codeblock_or_text(s: str) -> str:
    """
    If the model returns a fenced block, extract it; otherwise return raw.
    Editor is instructed to output *only* the corrected English chapter,
    but this is a safeguard.
    """
    m = re.search(r"```(?:markdown|md)?\s*([\s\S]+?)\s*```", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s.strip()

def print_diff(a: str, b: str, *, context=2, max_lines=200):
    a_lines = a.splitlines()
    b_lines = b.splitlines()
    diff = list(difflib.unified_diff(a_lines, b_lines, fromfile="draft", tofile="final", lineterm="", n=context))
    if diff:
        print("🧾 Unified diff (truncated):")
        if len(diff) > max_lines:
            head = diff[:max_lines//2]
            tail = diff[-max_lines//2:]
            for line in head: print(line)
            print("... (diff truncated) ...")
            for line in tail: print(line)
        else:
            for line in diff: print(line)
    else:
        print("✅ No textual changes (identical output).")

# === Main ===
def main():
    # --- Choose chapter ---
    # Option 1: set explicitly
    # chapter_num = "0598"
    # Option 2: auto-pick the latest draft in TRANSLATED_DIR
    chapter_num = scan_latest_chapter_num()
    if not chapter_num:
        raise SystemExit("No draft chapters found in final_chapters/. Nothing to edit.")

    print(f"🧪 Editorial pass for chapter ch{chapter_num}")

    raw_path = Path(RAW_DIR) / f"ch{chapter_num}.txt"
    draft_path = Path(TRANSLATED_DIR) / f"ch{chapter_num}.md"
    final_path = Path(FINAL_DIR) / f"ch{chapter_num}.md"
    prompt_path = Path(PROMPT_DIR) / f"editor_prompt_ch{chapter_num}.txt"
    # obsidian_output_path = Path(OBSIDIAN_FINAL_DIR) / f"ch{chapter_num}.md"

    if not raw_path.exists():
        raise FileNotFoundError(f"Missing raw chapter: {raw_path}")
    if not draft_path.exists():
        raise FileNotFoundError(f"Missing draft translation: {draft_path}")

    rules = load_file(RULES_PATH)
    glossary = json.loads(load_file(GLOSSARY_PATH))
    raw_chinese = load_file(raw_path)
    draft_english = load_file(draft_path)

    # Annotate Chinese with fixed glossary to lock in terms like 修罗剑[Shura Sword] etc.
    annotated_chinese = annotate_with_glossary(raw_chinese, glossary)

    # --- Editor system & user prompts ---
    system_prompt = """You are a bilingual xianxia fiction editor."""

    user_prompt = f"""You will receive the raw chinese text and the draft of the first translation. Check the translation. Your main job is to find ANY inconsistencies in logic, context, character dialoge or actions and fix them in the final output. Fix the mistakes and output only the final fixed version of the translation

    RAW (Chinese with annotations):
    {annotated_chinese}

    DRAFT (English):
    {draft_english}
    """

    print("\n=== EDITOR PROMPT (preview) ===\n")
    preview = user_prompt
    print(preview)
    print("\n=== END PROMPT PREVIEW ===\n")

    print(f"🛠️ Editing ch{chapter_num}...")
    response = call_gpt(system_prompt, user_prompt)

    corrected = extract_codeblock_or_text(response)

    # Save prompt and outputs
    save_file(prompt_path, user_prompt)
    save_file(final_path, corrected)
    # save_file(obsidian_output_path, corrected)

    print_diff(draft_english, corrected)

    # Update index for the FINAL dir (for your site/UI)
    update_chapters_index(FINAL_DIR, os.path.join(FINAL_DIR, "chapters.json"))

    print(f"🎉 Final chapter saved to: {final_path}")
    # print(f"🧭 Also mirrored to Obsidian: {obsidian_output_path}")

if __name__ == "__main__":
    main()
