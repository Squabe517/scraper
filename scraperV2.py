import time
import random
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright
import aiohttp
import asyncio
import os
from playwright.async_api import async_playwright
import json
from typing import List, Dict, Any

"""
Module: Asynchronous Web Scraper

Description:
    This script performs asynchronous web scraping on a list of base URLs. It uses aiohttp for
    asynchronous HTTP requests, BeautifulSoup for HTML parsing, and Playwright for JavaScript
    rendering. The scraper collects URLs from base pages, scrapes their textual content, and saves
    the output to a file.
"""

# List of base URLs to start scraping from.
BASE_URLS = [
    "https://python.langchain.com/api_reference/core/",
    "https://python.langchain.com/api_reference/langchain/",
    "https://python.langchain.com/api_reference/text_splitters/", 
    "https://python.langchain.com/api_reference/community/",       
    "https://python.langchain.com/api_reference/experimental/"
]


# Global sets and list to store discovered URLs and scraped output.

class BaseHttpClient:
    def fetch(self, url: str) -> str:
        pass

async def fetch(session, url):
    """
    Asynchronously fetch the content of the given URL.

    Args:
        url (str): The URL to fetch.

    Returns:
        str: The HTML content of the page if successful; otherwise, None.
    """
    try:
        async with session.get(url) as response:
            return await response.text()
    except asyncio.TimeoutError:
        print(f"Timeout error while fetching {url}")
    except aiohttp.ClientResponseError as e:
        print(f"HTTP error {e.status} for {url}")
    except aiohttp.ClientError as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


class LinkExtractor:
    def __init__(self, urls):
        """Constructor (runs synchronously)"""
        self.urls = urls
        self.session = None  # Will be set up in async context

    async def __aenter__(self):
        """Executed when entering 'async with'"""
        self.session = aiohttp.ClientSession()  # Open the session
        print("Session started")
        return self  # Return instance so it can be used in 'async with'

    async def __aexit__(self, exc_type, exc, tb):
        """Executed when exiting 'async with' (cleanup)"""
        await self.session.close()  # Ensure session is closed
        print("Session closed")
        
    async def map_urls(self, urls):
        """Map URLs from the given URL"""
        mapped_urls = set()

        if isinstance(urls, str):
            urls = [urls]
        
        html_pages = await asyncio.gather(*[fetch(self.session, url) for url in urls])
        
        tasks = [
            asyncio.to_thread(self.extract_links, html, base_url)
            for html, base_url in zip(html_pages, urls) if html
        ]

        results = await asyncio.gather(*tasks)
        
        for result in results:
            mapped_urls.update(result)
        return mapped_urls
    def extract_links(self, html: str, base_url: str) -> set[str]:
        """Extract links from HTML content"""
        soup = BeautifulSoup(html, "lxml")
        links = set()
        for link in soup.find_all("a", href=True):
            links.add(urljoin(base_url, link["href"]))
        return links
    
class ContentExtractor:
    def __init__(self, urls):
        """Constructor (runs synchronously)"""
        self.urls = urls
        self.session = None  # Will be set up in async context

    async def __aenter__(self):
        """Executed when entering 'async with'"""
        self.session = aiohttp.ClientSession()  # Open the session
        print("Session started")
        return self  # Return instance so it can be used in 'async with'

    async def __aexit__(self, exc_type, exc, tb):
        """Executed when exiting 'async with' (cleanup)"""
        await self.session.close()  # Ensure session is closed
        print("Session closed")
        
    async def scrape_urls(self, urls):
        """Scrape URLs from the given URL"""
        scraped_content = set()

        if isinstance(urls, str):
            urls = [urls]
        
        html_pages = await asyncio.gather(*[fetch(self.session, url) for url in urls])
        
        tasks = [
            asyncio.to_thread(self._scrape_url, html)
            for html, base_url in zip(html_pages, urls) if html
        ]

        results = await asyncio.gather(*tasks)
        
        for result in results:
            scraped_content.update(result)
        return scraped_content
    
        
    def _scrape_url(self, html: str) -> dict:
        """Scrape content from HTML"""
        soup = BeautifulSoup(html, "lxml")
        result = {}

        # Extract the page title.
        result["title"] = soup.title.string.strip() if soup.title and soup.title.string else ""

        # Extract meta tags into a dictionary.
        meta_tags = {}
        for meta in soup.find_all("meta"):
            # Check for both 'name' and 'property' attributes.
            key = meta.get("name") or meta.get("property")
            if key:
                content = meta.get("content", "").strip()
                meta_tags[key] = content
        result["meta"] = meta_tags

        # Extract headings (h1 through h6) into a list.
        headings = []
        for level in range(1, 7):
            for header in soup.find_all(f"h{level}"):
                text = header.get_text(strip=True)
                if text:
                    headings.append(text)
        result["headings"] = headings

        # Extract the main textual content from the <body> (fallback to entire document if <body> is absent).
        body = soup.body
        if body:
            result["content"] = body.get_text(separator="\n", strip=True)
        else:
            result["content"] = soup.get_text(separator="\n", strip=True)

        return result


async def fetch_with_playwright(url):
    """
    Fetch HTML content using Playwright to render JavaScript.

    This function launches a headless Chromium browser, navigates to the URL, waits until
    network activity ceases (ensuring JavaScript has loaded), and then returns the page content.

    Args:
        url (str): The URL to fetch using Playwright.

    Returns:
        str: The HTML content of the page, or an error message if Playwright fails.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")  # Wait until network is idle
            content = await page.content()
            await browser.close()
            return content
    except Exception as e:
        return f"Playwright failed: {e}"

async def check_static_dynamic(url):
    """
    Compare raw HTML with JavaScript-rendered HTML to determine if a page is dynamic.

    A heuristic is used: if the JS-rendered content is significantly larger than the raw content,
    the page is likely dynamic (i.e., modified by JavaScript).

    Args:
        url (str): The URL to check.

    Prints:
        A message indicating whether the page is dynamic or static.
    """
    raw_html = await fetch(url)
    js_html = await fetch_with_playwright(url)

    if len(js_html) > len(raw_html) + 500:  # Heuristic: JS-rendered pages are much larger
        print(f"{url} is DYNAMIC (JavaScript modifies content)")
    else:
        print(f"{url} is STATIC (No JavaScript modification)")

def export_results_to_jsonl(results: List[Dict[str, Any]], output_file_path: str = "output.jsonl") -> None:
    """
    Exports a list of result dictionaries to a JSON Lines file with semantic structure.

    Each result is expected to have keys such as 'title', 'content', and 'metadata'.
    A unique chunk_id is added for each result.

    Args:
        results (List[Dict[str, Any]]): A list of dictionaries containing result data.
        output_file_path (str): The path of the output JSON Lines file.

    Returns:
        None
    """
    structured_results = []
    for idx, result in enumerate(results):
        structured_chunk = {
            "chunk_id": idx,                     # Unique identifier for this chunk
            "title": result.get("title", ""),    # Title or heading, if available
            "content": result.get("content", ""),# Main textual content
            "metadata": result.get("metadata", {}) # Additional semantic metadata
        }
        structured_results.append(structured_chunk)

    # Write each structured chunk as a separate JSON object per line.
    with open(output_file_path, "w", encoding="utf-8") as file:
        for chunk in structured_results:
            file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

async def main():
    """
    Main coroutine to coordinate URL mapping and site scraping.

    - Maps additional URLs by scanning the base pages.
    - Initiates scraping of all collected URLs.
    """
    
    async with LinkExtractor(BASE_URLS) as extractor:
        urls = await extractor.map_urls(BASE_URLS)
        
    async with ContentExtractor(urls) as extractor:
        results = await extractor.scrape_urls(urls)
    
    
asyncio.run(main())
