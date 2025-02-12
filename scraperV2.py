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

async def fetch(url):
    """
    Asynchronously fetch the content of the given URL.

    Args:
        url (str): The URL to fetch.

    Returns:
        str: The HTML content of the page if successful; otherwise, None.
    """
    try:
        async with aiohttp.ClientSession() as session:
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


async def map_url(url):
    mapped_urls = set()
    """
    Fetch the HTML content of the provided URL, parse it, and map all hyperlinks into the global mapped_urls set.

    Args:
        url (str): The base URL to parse for hyperlinks.
    """
    
    html = await fetch(url)
    if not html:
        return  # Exit if no content was retrieved
    soup = BeautifulSoup(html, "lxml")
    
    # Extract and store URLs from all anchor tags with a href attribute.
    for link in soup.find_all("a", href=True):
        # Combine the base URL with the link's href.
        print(f'{url}{link["href"]}')
        mapped_urls.add(f'{url}{link["href"]}')
        
    return mapped_urls

async def map_urls(urls):
    """
    Map all URLs from the provided base URL by scanning the page content.

    Args:
        url (str): The base URL to scan for hyperlinks.

    Returns:
        set: A set of mapped URLs from the page.
    """
    mapped_urls = set()
    tasks = [map_url(url) for url in urls]
    results = await asyncio.gather(*tasks)

    for result in results:
        for url in result:
            mapped_urls.add(url)
    return mapped_urls


async def scrape_url(url: str) -> dict:
    """
    Asynchronously scrape and semantically structure textual content from a URL.

    The function fetches the HTML content from the given URL and then parses it using Beautiful Soup
    with the "lxml" parser. It extracts and organizes key semantic elements:
      - title: The text inside the <title> tag.
      - meta: A dictionary of meta tag content (e.g., description, keywords).
      - headings: A list of texts from heading tags (<h1> through <h6>).
      - content: The main textual content from the <body> tag.

    Args:
        url (str): The URL to scrape.

    Returns:
        dict: A dictionary with keys 'title', 'meta', 'headings', and 'content'.
              Returns an empty dict if the URL could not be fetched.
    """
    html = await fetch(url)
    if not html:
        return {}

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


async def worker(queue, results):
    """
    Worker coroutine that processes URLs from an asyncio queue.

    For each URL, the worker scrapes the textual content and appends it to the global output list.
    It also prints a preview of the scraped content.

    Args:
        queue (asyncio.Queue): Queue containing URLs to process.
    """
    while not queue.empty():
        url = await queue.get()
        scraped_text = await scrape_url(url)
        results.append(scraped_text)
        queue.task_done()
    return results

async def scrapeSite(urls, num_workers=5):
    """
    Process a collection of URLs concurrently using worker coroutines.

    Args:
        urls (iterable): A collection of URLs to scrape.
        num_workers (int, optional): Number of concurrent worker tasks. Defaults to 5.
    """
    queue = asyncio.Queue()
    results = []

    # Enqueue all URLs.
    if isinstance(urls, str):
        await queue.put(urls)
    else: 
        for url in urls:
            await queue.put(url)

    # Create worker tasks.
    workers = [asyncio.create_task(worker(queue, results)) for _ in range(num_workers)]
    # Wait until all queued tasks are completed.
    await queue.join()
    # Cancel any remaining worker tasks.
    for task in workers:
        task.cancel()
        
    return results

import json
from typing import List, Dict, Any

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
    # Map URLs from each base URL concurrently.
    urls = await map_urls(BASE_URLS)

    # Scrape the content from the collected mapped URLs.
    results = await scrapeSite(urls)
    
    # Export the scraped results to a JSON Lines file.
    export_results_to_jsonl(results, "output.jsonl")
    
asyncio.run(main())

    # Run the main asynchronous routine.


    # Write the scraped output to an output file.
    

# The following argparse code is commented out, but will be implemented in the future.
# It can be used to add command-line argument parsing for custom URL, output file, recursion depth, etc.
#
# parser = argparse.ArgumentParser(description="Web Scraper")
# parser.add_argument("url", help="URL to scrape")
# parser.add_argument("output_file", help="Output file to save scraped text")
# parser.add_argument("--depth", type=int, default=3, help="Depth of recursion")
# parser.add_argument("--debug", action="store_true", help="Enable debug mode")
# args = parser.parse_args()