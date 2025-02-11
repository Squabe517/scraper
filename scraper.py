import requests
import time
import random
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

# Set to track visited URLs
visited_urls = set()

def fetch_text(url, debug=False):
    """Fetch text from a webpage (static or JavaScript-rendered)."""
    headers = {"User-Agent": "Mozilla/5.0"}

    if debug:
        print(f"🔄 Fetching: {url}")

    try:
        # Try static request first
        response = requests.get(url, headers=headers, timeout=5)
        if response.ok:
            if "<script" not in response.text.lower():
                if debug:
                    print(f"✅ [Static] Successfully fetched: {url}")
                soup = BeautifulSoup(response.text, "lxml")
                return soup.get_text(separator="\n", strip=True)
            else:
                if debug:
                    print(f"⚠️ [Static] JavaScript detected, switching to Playwright: {url}")
    except requests.RequestException as e:
        if debug:
            print(f"❌ [Static] Failed: {url} | Error: {e}")

    # Use Playwright if JavaScript rendering is needed
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=10000)
            text = page.locator("body").inner_text()
            browser.close()
            if debug:
                print(f"✅ [JS] Successfully fetched: {url}")
            return text
    except Exception as e:
        if debug:
            print(f"❌ [JS] Failed: {url} | Error: {e}")
        return ""

def scrape_to_file(url, output_file, base_url, depth=3, debug=False):
    """Recursively scrape a website, following internal links up to a set depth."""
    if url in visited_urls or depth == 0:
        return  # Stop if URL is already visited or depth limit is reached

    visited_urls.add(url)
    print(f"\n🌐 Scraping: {url} (Depth: {depth})")

    # Fetch and save page text
    text = fetch_text(url, debug)
    if text:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"\n\n=== {url} ===\n\n{text}")

    # Extract and follow links
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, "lxml")
        links = soup.find_all("a", href=True)

        if debug:
            print(f"🔗 Found {len(links)} links on {url}")

        for link in links:
            full_url = urljoin(base_url, link["href"])
            parsed_url = urlparse(full_url)

            # Ensure we stay within the base domain
            if parsed_url.netloc == urlparse(base_url).netloc and full_url not in visited_urls:
                time.sleep(random.uniform(1, 3))  # Respectful crawling
                scrape_to_file(full_url, output_file, base_url, depth-1, debug)
    except requests.RequestException as e:
        if debug:
            print(f"❌ [Links] Failed to extract links from {url} | Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recursive Web Scraper with Debugging")
    parser.add_argument("start_url", help="The URL to start scraping from")
    parser.add_argument("output_file", help="File to save scraped text")
    parser.add_argument("--depth", type=int, default=2, help="Depth of recursive scraping")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode for verbose output")

    args = parser.parse_args()

    print(f"🚀 Starting scraper with depth {args.depth} {'(Debug mode ON)' if args.debug else ''}")
    scrape_to_file(args.start_url, args.output_file, args.start_url, args.depth, args.debug)

    print(f"✅ Scraping completed. Check {args.output_file}")
