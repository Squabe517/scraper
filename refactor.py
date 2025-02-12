from typing import List, Dict, Any

# Abstractions
class BaseHttpClient:
    def fetch(self, url: str) -> str:
        pass

class LinkExtractor:
    def extract_links(self, html: str) -> List[str]:
        pass

class ContentExtractor:
    def extract_content(self, html: str) -> Dict[str, Any]:
        pass

# Concrete Implementations
class AioHttpClient(BaseHttpClient):
    def fetch(self, url: str) -> str:
        # Implementation using aiohttp
        pass

class PlaywrightHttpClient(BaseHttpClient):
    def fetch(self, url: str) -> str:
        # Implementation using Playwright
        pass

class HtmlParser(LinkExtractor, ContentExtractor):
    def extract_links(self, html: str) -> List[str]:
        # Implementation using BeautifulSoup
        pass

    def extract_content(self, html: str) -> Dict[str, Any]:
        # Implementation using BeautifulSoup
        pass

# Coordinator
class Scraper:
    def __init__(self, http_client: BaseHttpClient, parser: HtmlParser):
        self.http_client = http_client
        self.parser = parser

    def scrape(self, url: str) -> Dict[str, Any]:
        html = self.http_client.fetch(url)
        links = self.parser.extract_links(html)
        content = self.parser.extract_content(html)
        return {'links': links, 'content': content}
