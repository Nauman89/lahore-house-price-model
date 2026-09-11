"""Shared fixtures.

Every fixture here is synthetic. No cached Ilaan page is committed as a test fixture:
the repository is public and Ilaan grants no licence to redistribute its listings
(decisions D-14, D-23), so the tests reproduce the *shape* of its pages — a React Server
Component payload, JSON-LD, the soft-404 template — with invented values.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from lhp.scrape.fetch import FetchConfig, Fetcher


class Server:
    """A local HTTP server whose responses tests can rewrite between requests."""

    def __init__(self) -> None:
        self.routes: dict[str, tuple[int, bytes] | Callable[[], tuple[int, bytes]]] = {}
        self.hits: list[str] = []
        self.robots = b"User-agent: *\nAllow: /\n"

    def respond(self, path: str) -> tuple[int, bytes]:
        """Return the configured response for a path."""
        if path.startswith("/robots.txt"):
            if self.robots is not None:
                return 200, self.robots
            return self.routes.get("/robots.txt", (404, b"not found"))
        self.hits.append(path)
        route = self.routes.get(path.split("?")[0], (200, b"<html>default</html>"))
        return route() if callable(route) else route

    @property
    def hit_count(self) -> int:
        """Requests served, excluding robots.txt."""
        return len(self.hits)


@pytest.fixture
def server() -> Iterator[Server]:
    """Run a local HTTP server for the duration of a test."""
    state = Server()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def do_GET(self) -> None:  # noqa: N802
            status, body = state.respond(self.path)
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    state.base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield state
    httpd.shutdown()


@pytest.fixture
def config(tmp_path: Path) -> FetchConfig:
    """A FetchConfig with delays short enough for tests."""
    return FetchConfig(
        user_agent="lhp-tests/0.1",
        cache_dir=tmp_path / "cache",
        log_path=tmp_path / "requests.jsonl",
        min_delay=0.001,
        max_delay=0.002,
        backoff_base=0.001,
        max_retries=2,
    )


@pytest.fixture
def fetcher(config: FetchConfig) -> Fetcher:
    """A Fetcher on a throwaway cache."""
    return Fetcher(config)


def read_log(config: FetchConfig) -> list[dict]:
    """Return the audit log as a list of rows."""
    if not config.log_path.exists():
        return []
    return [
        json.loads(line)
        for line in config.log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def rsc_page(prop: dict, *, chunks: int = 3, geo: tuple[float, float] | None = None) -> str:
    """Build a page shaped like Ilaan's, with the record split across RSC push calls.

    Splitting matters: the payload arrives in fragments and the parser has to reassemble
    them before the record is even findable. A single-chunk fixture would not exercise that.
    """
    payload = json.dumps({"propertyId": str(prop.get("id", "1")), "initialProperty": prop})
    size = max(len(payload) // chunks, 1)
    pushes = "".join(
        f"<script>self.__next_f.push([1,{json.dumps(payload[i : i + size])}])</script>"
        for i in range(0, len(payload), size)
    )
    ld = {"@context": "https://schema.org", "@type": "RealEstateListing", "name": prop.get("title")}
    if geo:
        ld["geo"] = {"@type": "GeoCoordinates", "latitude": geo[0], "longitude": geo[1]}
    return (
        f"<html><head><title>{prop.get('title', 'Listing')}</title>"
        f'<script type="application/ld+json">{json.dumps(ld)}</script>'
        f"</head><body>{pushes}</body></html>"
    )


SOFT_404 = (
    "<html><head><title>Property Not Found | Ilaan.com</title></head>"
    "<body>The page you are looking for does not exist.</body></html>"
)


def listing(**overrides: object) -> dict:
    """A complete synthetic listing record, overridable per test."""
    base = {
        "id": "600001",
        "title": "10 Marla House for Sale in Example Block, Example Town, Lahore",
        "price": 25000000,
        "area": 10.0,
        "areaUnit": "marla",
        "bedrooms": 4,
        "bathrooms": 3,
        "address": "Example Block, Example Town, Lahore",
        "city": "Lahore",
        "locality": "Example Town",
        "province": "Punjab",
        "latitude": 31.5,
        "longitude": 74.35,
        "type": "House",
        "status": "ForSale",
        "condition": "New",
        "yearBuilt": 2026,
        "isSold": False,
        "views": 12,
        "amenities": [],
        "gallery": ["a.jpg", "b.jpg"],
        "createdAt": "$D2024-05-01T10:00:00.000Z",
        "agent": {"name": "Someone", "phone": "0300-0000000"},
        "agentName": "Someone",
        "agentPhone": "0300-0000000",
        "agentWhatsApp": "0300-0000000",
    }
    base.update(overrides)
    return base
