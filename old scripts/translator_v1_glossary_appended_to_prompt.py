from openai import OpenAI
import os
from pathlib import Path
from dotenv import load_dotenv
import re

load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_next_chapter_number():
    existing = list(Path("..").glob("ch*.md"))
    chapter_nums = [int(re.search(r"ch(\d+)\.md", f.name).group(1)) for f in existing if re.search(r"ch(\d+)\.md", f.name)]
    return f"{(max(chapter_nums) + 1) if chapter_nums else 1:04}"

# File paths
RULES_PATH = "../rules.md"
GLOSSARY_PATH = "../glossary.md"
CHAPTER = get_next_chapter_number()
CHAPTER_INPUT_PATH = f"piaotian_chapters/ch{CHAPTER}.txt"
CHAPTER_OUTPUT_PATH = f"ch{CHAPTER}.md"
OBSIDIAN_PATH = f"/Users/meecosha/MEGA/Vault/Martial Peak/chapters/ch{CHAPTER}.md"


def load_file(path):
    return Path(path).read_text(encoding="utf-8").strip()

def append_to_file(path, content):
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + content.strip() + "\n")


def call_chatgpt(system_prompt, user_prompt, model="gpt-4o-mini-2024-07-18"):
    response = client.chat.completions.create(
        model=model,
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


def main():
    # Load rules, glossary, and chapter text
    rules = load_file(RULES_PATH)
    glossary = load_file(GLOSSARY_PATH)
    chapter_text = load_file(CHAPTER_INPUT_PATH)

    # Compose prompts
    system_prompt = "You are a professional xianxia translator. Follow the provided rules and glossary strictly."
    user_prompt = f"""
IMPORTANT: After translating the chapter, you must list any new specific terms that may require consistency later — including names, realms, techniques, materials, artefacts, or sects — in this format:

Chinese Hanzi — English Term

Always err on the side of caution. If there’s even a small chance something is specific or unique, add it.  
If there are no new terms, write: New Glossary Terms: None

Translation rules:
{rules}

Glossary:
{glossary}

Translate the following chapter according to the above instructions and glossary.

Chapter:
{chapter_text}
"""

    # Get translation
    translated_output = call_chatgpt(system_prompt, user_prompt)

    # Parse the output
    if "New Glossary Terms:" in translated_output:
        translation, glossary_section = translated_output.split("New Glossary Terms:", 1)
    else:
        translation = translated_output
        glossary_section = "None"

    # Save the translated chapter
    Path(CHAPTER_OUTPUT_PATH).write_text(translation.strip(), encoding="utf-8")
    Path(OBSIDIAN_PATH).write_text(translation.strip(), encoding="utf-8")

    # Append glossary if new terms found
    if "none" not in glossary_section.lower():
        existing_glossary_lines = set(load_file(GLOSSARY_PATH).splitlines())
        new_lines = [line.strip() for line in glossary_section.strip().splitlines() if line.strip()]
        unique_new_lines = [line for line in new_lines if line not in existing_glossary_lines]

        if unique_new_lines:
            append_to_file(GLOSSARY_PATH, "\n".join(unique_new_lines))
            print(f"📝 Appended {len(unique_new_lines)} new glossary terms.")
        else:
            print("✅ All glossary terms already exist. Nothing appended.")
    else:
        print("✅ No new glossary terms.")

    print(f"🎉 Chapter translated and saved to {CHAPTER_OUTPUT_PATH}")
    print("\n=== Full model response ===\n")
    print(translated_output)
    print("\n=== End of response ===\n")

    # print("\n=== SYSTEM PROMPT ===\n")
    # print(system_prompt)
    #
    # print("\n=== USER PROMPT ===\n")
    # print(user_prompt)


if __name__ == "__main__":
    main()
