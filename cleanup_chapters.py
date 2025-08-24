import re
import argparse
from pathlib import Path

TRANSLATION_START_RE = re.compile(r'^=== TRANSLATION START ===\s*$', re.MULTILINE)
TRANSLATION_END_RE = re.compile(r'^=== TRANSLATION END ===\s*$', re.MULTILINE)
QA_BLOCK_RE = re.compile(r'^=== QA REPORT START ===[\s\S]*?^=== QA REPORT END ===\s*', re.MULTILINE)
P_PREFIX_ONLY_RE = re.compile(r'^@P\d+:\s*', re.MULTILINE)


def strip_markers(text: str) -> str:
    text = QA_BLOCK_RE.sub('', text)
    text = TRANSLATION_START_RE.sub('', text)
    text = TRANSLATION_END_RE.sub('', text)
    return text.strip('\n') + '\n'


def remove_p_prefixes(text: str) -> str:
    """Remove @P<number>: prefixes but otherwise leave spacing and newlines untouched."""
    return P_PREFIX_ONLY_RE.sub('', text)


def transform(text: str) -> str:
    # 1. Strip markers / QA
    text = strip_markers(text)
    # 2. Remove @P prefixes
    text = remove_p_prefixes(text)
    return text


def process_file(path: Path, out_dir: Path, inplace: bool, dry_run: bool) -> bool:
    original = path.read_text(encoding='utf-8')
    cleaned = transform(original)
    if dry_run:
        preview = cleaned[:1000]
        print(f"--- {path.name} (dry run preview) ---")
        print(preview)
        if len(cleaned) > 1000:
            print('... (truncated) ...')
        print('--- end preview ---\n')
        return True
    target_path = path if inplace else (out_dir / path.name)
    if not inplace:
        out_dir.mkdir(parents=True, exist_ok=True)
    target_path.write_text(cleaned, encoding='utf-8')
    return True


def main():
    parser = argparse.ArgumentParser(description='Remove translation markers/QA and strip @P<number>: prefixes.')
    parser.add_argument('--src', default='final_chapters', help='Source directory containing chXXXX.md files.')
    parser.add_argument('--dest', default='final_chapters_clean', help='Destination directory (ignored if --inplace).')
    parser.add_argument('--inplace', action='store_true', help='Modify files in place.')
    parser.add_argument('--dry-run', action='store_true', help='Show preview of cleaned content without writing.')
    parser.add_argument('--file', help='Single file to process instead of scanning directory.')
    args = parser.parse_args()

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"File not found: {file_path}")
            return
        process_file(file_path, Path(args.dest), inplace=args.inplace, dry_run=args.dry_run)
        return

    src_dir = Path(args.src)
    if not src_dir.exists():
        print(f"Source directory not found: {src_dir}")
        return

    out_dir = Path(args.dest)
    total = 0
    changed = 0
    for f in sorted(src_dir.glob('ch*.md')):
        total += 1
        try:
            if process_file(f, out_dir, inplace=args.inplace, dry_run=args.dry_run):
                changed += 1
        except Exception as e:
            print(f"Error processing {f.name}: {e}")
    print(f"Processed {total} files. Cleaned: {changed}.")


if __name__ == '__main__':
    main()
