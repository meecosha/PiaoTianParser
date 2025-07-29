import requests
from bs4 import BeautifulSoup, NavigableString
import os

# -------- CONFIG --------
url = "https://www.piaotia.com/html/3/3224/1630073.html"
chapter_number = 16  # Change this for each chapter
output_folder = "piaotian_chapters"
# ------------------------

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/117.0.0.0 Safari/537.36",
    "Referer": "https://www.piaotia.com/html/3/3224/",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

def extract_chapter_text(soup):
    content_lines = []

    # Find the <h1> title
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else f"Chapter {chapter_number}"

    # Find the first <br> after the script tables (where text starts)
    first_br = soup.find("br")
    while first_br and not isinstance(first_br, NavigableString):
        if first_br.name == "br":
            break
        first_br = first_br.next_element

    # From that point on, walk through siblings and extract text
    current = first_br
    while current:
        if isinstance(current, NavigableString):
            line = current.strip()
            if line:
                content_lines.append(line)
        elif getattr(current, "name", None) == "br":
            content_lines.append("")  # Line break
        elif getattr(current, "name", None) == "div" and current.get("class") == ["bottomlink"]:
            break  # Stop at bottom nav
        current = current.next_element

    content = "\n".join(content_lines).strip()
    return title, content

def save_chapter(title, content, number):
    os.makedirs(output_folder, exist_ok=True)
    filename = os.path.join(output_folder, f"ch{number:04d}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(title + "\n\n" + content)
    print(f"✅ Saved: {filename}")

def main():
    response = requests.get(url, headers=headers)
    response.encoding = "gb2312"
    soup = BeautifulSoup(response.text, "html.parser")

    title, content = extract_chapter_text(soup)
    save_chapter(title, content, chapter_number)

if __name__ == "__main__":
    main()
