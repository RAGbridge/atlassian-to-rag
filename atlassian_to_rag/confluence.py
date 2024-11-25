from datetime import timedelta
from typing import Any, Dict, List, Optional

from atlassian import Confluence

from .core.cache import CacheManager, cached
from .core.monitoring import Metrics
from .core.rate_limiting import RateLimiter


class ConfluenceExtractor:
    def __init__(self, url: str, username: str, api_token: str, cache_manager: Optional[CacheManager] = None, rate_limiter: Optional[RateLimiter] = None, metrics: Optional[Metrics] = None):
        self.confluence = Confluence(url=url, username=username, password=api_token, cloud=True)
        self.base_url = url
        self.cache_manager = cache_manager
        self.rate_limiter = rate_limiter
        self.metrics = metrics

    @cached("space_content", expire=timedelta(hours=1))
    def get_space_content(self, space_key: str) -> List[Dict]:
        pages = []
        start = 0
        limit = 100

        while True:
            results = self.confluence.get_all_pages_from_space(space=space_key, start=start, limit=limit, expand="body.storage,version")

            if not results:
                break

            for page in results:
                pages.append(
                    {
                        "id": page["id"],
                        "title": page["title"],
                        "content": page["body"]["storage"]["value"],
                        "url": f"{self.base_url}/wiki/spaces/{space_key}/pages/{page['id']}",
                        "version": page["version"]["number"],
                        "last_modified": page["version"]["when"],
                    }
                )

            start += limit

        return pages

    @cached("single_page", expire=timedelta(minutes=30))
    def get_single_page(self, page_id: str) -> Dict:
        page = self.confluence.get_page_by_id(page_id=page_id, expand="body.storage,version")

        return {
            "id": page["id"],
            "title": page["title"],
            "content": page["body"]["storage"]["value"],
            "url": f"{self.base_url}/wiki/pages/{page['id']}",
            "version": page["version"]["number"],
            "last_modified": page["version"]["when"],
        }

    def get_attachments(self, page_id: str) -> List[Dict]:
        attachments = self.confluence.get_attachments_from_content(page_id)
        return [
            {
                "id": att["id"],
                "title": att["title"],
                "filename": att["title"],
                "mediaType": att.get("metadata", {}).get("mediaType", ""),
                "size": att.get("extensions", {}).get("fileSize", 0),
                "url": f"{self.base_url}/wiki/download/attachments/{page_id}/{att['title']}",
            }
            for att in attachments.get("results", [])
        ]

    def get_comments(self, page_id: str) -> List[Dict]:
        comments = self.confluence.get_page_comments(page_id)
        return [{"id": comment["id"], "author": comment["author"]["displayName"], "created": comment["created"], "content": comment["body"]["storage"]["value"]} for comment in comments]
