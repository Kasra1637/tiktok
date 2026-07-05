"""
Brand website analysis: fetches a brand's website and extracts readable text
(title, meta description, headings, body copy) using only the stdlib HTML
parser, so it can be fed to an LLM to derive brand overview, unique selling
propositions, brand voice/tone, and target audience.

Note: TikTok's official Developer API only exposes stats for videos owned by
an OAuth-authorized creator account and has no concept of "analyze this
brand's website", so there is no TikTok API involved here - this reads the
brand's own public site directly, which is the correct data source for this
feature.
"""
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15.0
MAX_RESPONSE_BYTES = 3 * 1024 * 1024  # 3MB cap on downloaded HTML
MAX_TEXT_CHARS = 8000  # cap on extracted text sent to the LLM
USER_AGENT = "Mozilla/5.0 (compatible; HookForgeBrandBot/1.0; +https://hookforge.app)"

# Tags whose contents are never meaningful "readable" copy.
_SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "iframe"}
# Block-level tags: insert a newline boundary so words from adjacent
# elements don't run together.
_BLOCK_TAGS = {
    "p", "div", "section", "article", "header", "footer", "main", "nav",
    "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "blockquote",
}


class _ReadableTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta_description = ""
        self.chunks = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            attr_dict = dict(attrs)
            name = (attr_dict.get("name") or attr_dict.get("property") or "").lower()
            if name in ("description", "og:description") and not self.meta_description:
                self.meta_description = (attr_dict.get("content") or "").strip()
        if tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag == "title":
            self._in_title = False
        if tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        if self._in_title:
            self.title += data
            return
        text = data.strip()
        if text:
            self.chunks.append(text + " ")

    def get_text(self) -> str:
        raw = "".join(self.chunks)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n", raw)
        return raw.strip()


def normalize_url(raw_url: str) -> str:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        raise ValueError("Website URL is required.")
    if not re.match(r"^https?://", raw_url, re.IGNORECASE):
        raw_url = f"https://{raw_url}"
    parsed = urlparse(raw_url)
    if not parsed.netloc or "." not in parsed.netloc:
        raise ValueError("Please provide a valid website URL, e.g. https://yourbrand.com")
    return raw_url


async def fetch_website_text(raw_url: str) -> dict:
    """
    Fetch a brand's website and extract readable text for LLM analysis.
    Returns {"url": str, "title": str, "meta_description": str, "text": str}.
    Raises ValueError for bad input, RuntimeError for network/parsing failures.
    """
    url = normalize_url(raw_url)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
        ) as client:
            async with client.stream("GET", url) as response:
                content_type = response.headers.get("content-type", "")
                if response.status_code >= 400:
                    raise RuntimeError(f"Website returned HTTP {response.status_code}.")
                if "text/html" not in content_type and content_type:
                    raise RuntimeError(f"URL did not return an HTML page (content-type: {content_type}).")

                body_bytes = b""
                async for chunk in response.aiter_bytes():
                    body_bytes += chunk
                    if len(body_bytes) > MAX_RESPONSE_BYTES:
                        break
                final_url = str(response.url)
    except httpx.TimeoutException:
        raise RuntimeError("The website took too long to respond.")
    except httpx.RequestError as e:
        raise RuntimeError(f"Could not reach that website: {e}")

    try:
        html_text = body_bytes.decode(response.encoding or "utf-8", errors="ignore")
    except LookupError:
        html_text = body_bytes.decode("utf-8", errors="ignore")

    extractor = _ReadableTextExtractor()
    try:
        extractor.feed(html_text)
    except Exception as e:
        raise RuntimeError(f"Failed to parse website content: {e}")

    text = extractor.get_text()[:MAX_TEXT_CHARS]
    if len(text) < 40:
        raise RuntimeError(
            "Could not find readable content on that page. It may require JavaScript "
            "or login to view - try linking directly to an About/Home page."
        )

    return {
        "url": final_url,
        "title": extractor.title.strip()[:200],
        "meta_description": extractor.meta_description[:500],
        "text": text,
    }
