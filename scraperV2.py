import requests
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
mapped_urls = set()
visited_urls = set()
output = []


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


async def map_urls(url):
    """
    Fetch the HTML content of the provided URL, parse it, and map all hyperlinks into the global mapped_urls set.

    Args:
        url (str): The base URL to parse for hyperlinks.
    """
    html = await fetch(url)
    if not html:
        return  # Exit if no content was retrieved
    soup = BeautifulSoup(html, "lxml")
    
    # Extract and store URLs from all anchor tags with an href attribute.
    for link in soup.find_all("a", href=True):
        # Combine the base URL with the link's href.
        mapped_urls.add(f'{url}{link["href"]}')


async def scrape_url(url):
    """
    Asynchronously scrape the textual content from a URL.

    Args:
        url (str): The URL to scrape.

    Returns:
        str: The scraped text from the page.
    """
    html = await fetch(url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    # Get all text from the page, separated by newlines and stripped of extra whitespace.
    return soup.get_text(separator="\n", strip=True)


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


async def worker(queue):
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
        print(f"Scraped {url}: {scraped_text[:100]}...\n\n")
        output.append(scraped_text)
        queue.task_done()


async def scrapeSite(urls, num_workers=5):
    """
    Process a collection of URLs concurrently using worker coroutines.

    Args:
        urls (iterable): A collection of URLs to scrape.
        num_workers (int, optional): Number of concurrent worker tasks. Defaults to 5.
    """
    queue = asyncio.Queue()

    # Enqueue all URLs.
    for url in urls:
        await queue.put(url)

    # Create worker tasks.
    workers = [asyncio.create_task(worker(queue)) for _ in range(num_workers)]
    # Wait until all queued tasks are completed.
    await queue.join()
    # Cancel any remaining worker tasks.
    for task in workers:
        task.cancel()


async def main():
    """
    Main coroutine to coordinate URL mapping and site scraping.

    - Maps additional URLs by scanning the base pages.
    - Initiates scraping of all collected URLs.
    """
    # Map URLs from each base URL concurrently.
    tasks = [map_urls(url) for url in BASE_URLS]
    await asyncio.gather(*tasks)

    # Scrape the content from the collected mapped URLs.
    await scrapeSite(mapped_urls)
    

if __name__ == "__main__":
    # Run the main asynchronous routine.
    asyncio.run(main())

    # Write the scraped output to an output file.
    with open("output.txt", "w", encoding="utf-8") as f:
        for text in output:
            f.write(f"=====================\n\n=== {text} ===\n\n======================")

# The following argparse code is commented out, but will be implemented in the future.
# It can be used to add command-line argument parsing for custom URL, output file, recursion depth, etc.
#
# parser = argparse.ArgumentParser(description="Web Scraper")
# parser.add_argument("url", help="URL to scrape")
# parser.add_argument("output_file", help="Output file to save scraped text")
# parser.add_argument("--depth", type=int, default=3, help="Depth of recursion")
# parser.add_argument("--debug", action="store_true", help="Enable debug mode")
# args = parser.parse_args()
