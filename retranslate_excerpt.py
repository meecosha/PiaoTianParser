import argparse
import os
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI  # type: ignore
except ImportError:
    OpenAI = None  # fallback; user must install openai

FINAL_CHAPTERS_DIR = Path("final_chapters")
RAW_CHINESE_DIR = Path("piaotian_chapters")

P_LINE_RE = re.compile(r'^@P(\d+):\s*(.*)$')
TRANSLATION_BLOCK_RE = re.compile(r'=== TRANSLATION START ===\s*([\s\S]*?)=== TRANSLATION END ===', re.MULTILINE)
RETRANS_BLOCK_RE = re.compile(r'=== RETRANSLATION START ===\s*([\s\S]*?)\s*=== RETRANSLATION END ===', re.MULTILINE)
BLANK_SPLIT_RE = re.compile(r"\n\s*\n")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def extract_translation_section(full_text: str) -> str:
    m = TRANSLATION_BLOCK_RE.search(full_text)
    return m.group(1).strip() if m else full_text

def parse_p_paragraphs(translation_section: str) -> List[Tuple[int, str]]:
    out = []
    for line in translation_section.splitlines():
        m = P_LINE_RE.match(line.strip())
        if m:
            out.append((int(m.group(1)), m.group(2).strip()))
    return out

def split_raw_chinese(raw: str) -> List[str]:
    raw = raw.replace('\r\n', '\n').strip()
    paras = [p.strip() for p in BLANK_SPLIT_RE.split(raw) if p.strip()]
    if len(paras) == 1 and '\n' in paras[0] and len(paras[0]) > 1500:
        paras = [ln.strip() for ln in paras[0].split('\n') if ln.strip()]
    return paras

def normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

def locate_excerpt_in_chapter(paragraphs: List[Tuple[int, str]], excerpt: str, fuzzy: bool=False) -> Optional[List[int]]:
    phrase = normalise(excerpt)
    if not phrase:
        return None
    # First: exact single-paragraph containment
    hits = [pnum for pnum, txt in paragraphs if phrase in normalise(txt)]
    if hits:
        return hits
    # Multi-paragraph span search (contiguous) – only if phrase crosses boundaries
    norm_paras = [normalise(txt) for _, txt in paragraphs]
    n = len(norm_paras)
    for i in range(n):
        acc = norm_paras[i]
        if phrase in acc:
            return [paragraphs[i][0]]
        for j in range(i+1, n):
            acc += ' ' + norm_paras[j]
            if phrase in acc:
                return [paragraphs[k][0] for k in range(i, j+1)]
    if fuzzy:
        # fallback: paragraph(s) containing largest overlap token set
        phrase_tokens = set(phrase.split())
        scored = []
        for pnum, txt in paragraphs:
            tokens = set(normalise(txt).split())
            inter = phrase_tokens & tokens
            if inter:
                scored.append((len(inter), pnum))
        if scored:
            scored.sort(reverse=True)
            best_count = scored[0][0]
            return [p for c, p in scored if c == best_count]
    return None

def find_best_chapter(excerpt: str, fuzzy: bool=False) -> List[Tuple[str, List[int]]]:
    matches = []
    phrase = normalise(excerpt)
    if not phrase:
        return matches
    for path in sorted(FINAL_CHAPTERS_DIR.glob('ch*.md')):
        full = load_text(path)
        translation_section = extract_translation_section(full)
        if phrase not in normalise(translation_section):
            continue
        p_paras = parse_p_paragraphs(translation_section)
        if not p_paras:
            continue
        p_hits = locate_excerpt_in_chapter(p_paras, excerpt, fuzzy=fuzzy) or []
        if p_hits:
            matches.append((path.name, p_hits))
    return matches

def build_retranslation_prompt(chapter_id: str, hit_pnums: List[int], translation_paras: List[Tuple[int, str]], raw_chinese_paras: List[str], context: int) -> str:
    # Guarantee at least 1 paragraph of context above/below regardless of user input
    context = max(1, context)
    pmin, pmax = min(hit_pnums), max(hit_pnums)
    pmin_ctx = max(1, pmin - context)
    pmax_ctx = min(len(raw_chinese_paras), pmax + context)
    eng_slice = []
    zh_slice = []
    trans_map = {pnum: txt for pnum, txt in translation_paras}
    for pnum in range(pmin_ctx, pmax_ctx + 1):
        eng = trans_map.get(pnum, '').strip()
        zh = raw_chinese_paras[pnum - 1] if pnum - 1 < len(raw_chinese_paras) else ''
        mark = '*' if pnum in hit_pnums else ' '
        eng_slice.append(f"@P{pnum}{mark}: {eng}")
        zh_slice.append(f"@P{pnum}{mark}: {zh}")
    system_prompt = ("You are a professional bilingual Chinese→English xianxia translator. Retranslate ONLY the starred paragraphs faithfully, concise, natural, no added lore.")
    user_prompt = f"""
SOURCE (Chinese, context):
{os.linesep.join(zh_slice)}

CURRENT TRANSLATION (English, context):
{os.linesep.join(eng_slice)}

INSTRUCTIONS:
- Retranslate ONLY paragraphs with an asterisk (*). Context (non-star) lines are provided for reference; DO NOT output them.
- Output format EXACTLY:
=== RETRANSLATION START ===
@P<id>: <new English>
@P<id>: <new English>
=== RETRANSLATION END ===
- One line per retranslated paragraph, no others.
- Do NOT include Chinese in the output (the tool will merge it locally).
- No notes, no explanations, no extra markers.
Provide only the block.
""".strip()
    return system_prompt, user_prompt

load_dotenv()
def call_openai(system_prompt: str, user_prompt: str, model: str = "gpt-5-mini-2025-08-07") -> Tuple[str, Dict[str, Any]]:
    if OpenAI is None:
        raise RuntimeError("openai package not installed. pip install openai")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
    )
    usage = {
        "prompt_tokens": getattr(resp.usage, 'prompt_tokens', None),
        "completion_tokens": getattr(resp.usage, 'completion_tokens', None),
        "total_tokens": getattr(resp.usage, 'total_tokens', None),
    }
    content = resp.choices[0].message.content
    return content, usage

def main():
    parser = argparse.ArgumentParser(description="Retranslate excerpt. Usage: python retranslate_excerpt.py your phrase here")
    parser.add_argument('excerpt', nargs='*', help='Excerpt phrase (no quotes needed).')
    parser.add_argument('--model', default='gpt-5-mini-2025-08-07', help='Override model name (ignored if --gpt5 used).')
    parser.add_argument('--gpt5', action='store_true', help='Use gpt-5-2025-08-07 model (overrides --model).')
    parser.add_argument('--context', type=int, default=1)
    parser.add_argument('--chapter', help='Force chapter id like ch0600')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--fuzzy', action='store_true', help='Enable token-overlap fallback if exact phrase not found.')
    args = parser.parse_args()

    # Decide model (flag overrides explicit --model)
    model_name = 'gpt-5-2025-08-07' if args.gpt5 else args.model

    excerpt = ' '.join(args.excerpt).strip()
    if not excerpt:
        print("No excerpt provided.")
        return

    if args.chapter:
        chap_file = FINAL_CHAPTERS_DIR / f"{args.chapter}.md"
        if not chap_file.exists():
            print(f"Chapter not found: {chap_file}")
            return
        translation_section = extract_translation_section(load_text(chap_file))
        t_paras = parse_p_paragraphs(translation_section)
        hit_pnums = locate_excerpt_in_chapter(t_paras, excerpt, fuzzy=args.fuzzy) or []
        if not hit_pnums:
            print("Excerpt not found in specified chapter.")
            return
        matches = [(chap_file.name, hit_pnums)]
    else:
        matches = find_best_chapter(excerpt, fuzzy=args.fuzzy)

    if not matches:
        print("No chapter match found.")
        return

    if len(matches) > 1:
        print("Multiple chapter matches:")
        for i, (fname, pnums) in enumerate(matches, 1):
            print(f"  [{i}] {fname} paragraphs {pnums}")
        choice = input("Select index (default 1): ").strip() or '1'
        try:
            sel = int(choice) - 1
            chapter_name, hit_pnums = matches[sel]
        except Exception:
            chapter_name, hit_pnums = matches[0]
    else:
        chapter_name, hit_pnums = matches[0]

    print(f"Using chapter {chapter_name}, paragraphs {hit_pnums} (model: {model_name})")
    chapter_path = FINAL_CHAPTERS_DIR / chapter_name
    translation_paras = parse_p_paragraphs(extract_translation_section(load_text(chapter_path)))

    chapter_id = chapter_name.split('.')[0]
    raw_path = RAW_CHINESE_DIR / f"{chapter_id}.txt"
    if not raw_path.exists():
        print(f"Missing raw Chinese file: {raw_path}")
        return
    raw_paragraphs = split_raw_chinese(load_text(raw_path))

    system_prompt, user_prompt = build_retranslation_prompt(chapter_id, hit_pnums, translation_paras, raw_paragraphs, args.context)

    if args.dry_run:
        print("==== SYSTEM PROMPT (SENT) ====")
        print(system_prompt)
        print("\n==== USER PROMPT (SENT) ====")
        print(user_prompt)
        print(f"\n(Model: {model_name})")
        return

    print("==== SYSTEM PROMPT (SENT) ====")
    print(system_prompt)
    print("\n==== USER PROMPT (SENT) ====")
    print(user_prompt)
    print(f"\n==== CALLING MODEL (model: {model_name}) ====")
    try:
        out, usage = call_openai(system_prompt, user_prompt, model=model_name)
    except Exception as e:
        print(f"OpenAI error: {e}")
        return
    print("\n==== MODEL OUTPUT ====")
    print(out)
    print("\n==== TOKEN USAGE ====")
    print(f"prompt: {usage.get('prompt_tokens')} | completion: {usage.get('completion_tokens')} | total: {usage.get('total_tokens')}")

    m = RETRANS_BLOCK_RE.search(out)
    if not m:
        print("⚠️ Could not find retranslation block for merging Chinese text.")
        return
    block = m.group(1).strip()
    new_lines = []
    for line in block.splitlines():
        line = line.strip()
        pm = re.match(r'^@P(\d+):\s*(.*)$', line)
        if not pm:
            continue
        pnum = int(pm.group(1))
        new_en = pm.group(2)
        zh = raw_paragraphs[pnum-1] if 0 <= pnum-1 < len(raw_paragraphs) else ''
        new_lines.append(f"@P{pnum} ZH: {zh}\n@P{pnum} EN: {new_en}")
    if new_lines:
        print("\n==== MERGED CHINESE + NEW ENGLISH ====")
        print("\n\n".join(new_lines))

if __name__ == "__main__":
    main()
