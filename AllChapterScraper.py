import requests
from bs4 import BeautifulSoup, NavigableString
import os
import time

base_url = "https://www.piaotia.com"
toc_url = "https://www.piaotia.com/html/3/3224/"
output_folder = "piaotian_chapters"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/117.0.0.0 Safari/537.36",
    "Referer": toc_url,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Step 1: Scrape all chapter links from the ToC
def get_all_chapter_links():
    response = requests.get(toc_url, headers=headers)
    response.encoding = "gbk"  # Site uses Chinese encoding
    soup = BeautifulSoup(response.text, "html.parser")

    links = []
    for li in soup.select("ul li a"):
        href = li.get("href")
        title = li.get_text(strip=True)
        if href and href.endswith(".html"):
            full_url = base_url + "/html/3/3224/" + href
            links.append((title, full_url))
    print(f"✅ Found {len(links)} chapter links.")
    return links

# Step 2: Extract chapter text from its HTML page
def extract_chapter_text(soup, chapter_number):
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else f"Chapter {chapter_number}"

    content_lines = []
    first_br = soup.find("br")
    while first_br and not isinstance(first_br, NavigableString):
        if first_br.name == "br":
            break
        first_br = first_br.next_element

    current = first_br
    while current:
        if isinstance(current, NavigableString):
            line = current.strip()
            if line:
                content_lines.append(line)
        elif getattr(current, "name", None) == "br":
            content_lines.append("")
        elif getattr(current, "name", None) == "div" and current.get("class") == ["bottomlink"]:
            break
        current = current.next_element

    content = "\n".join(content_lines).strip()
    return title, content

# Step 3: Save chapter to .txt file
def save_chapter(title, content, number):
    os.makedirs(output_folder, exist_ok=True)
    filename = os.path.join(output_folder, f"ch{number:04d}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(title + "\n\n" + content)
    print(f"✅ Saved: {filename}")

# Step 4: Download a chapter by URL
def process_chapter(index, url):
    try:
        response = requests.get(url, headers=headers)
        response.encoding = "gb2312"  # Works with both gb2312 and gbk
        soup = BeautifulSoup(response.text, "html.parser")
        title, content = extract_chapter_text(soup, index)
        save_chapter(title, content, index)
    except Exception as e:
        print(f"❌ Failed to process chapter {index}: {url}\nReason: {e}")

# Main routine
def main():
    links = get_all_chapter_links()
    start_ch = 201
    end_ch = 500
    test_links = links[start_ch - 1:end_ch]  # Adjusting for 0-based indexing

    for i, (title, url) in enumerate(test_links, start=start_ch):
        process_chapter(i, url)
        time.sleep(1)  # polite delay between requests

if __name__ == "__main__":
    main()
