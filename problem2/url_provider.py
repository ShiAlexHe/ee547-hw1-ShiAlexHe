# Provided: url_provider.py

import random
from dataclasses import dataclass
from typing import Callable

@dataclass
class URLBehavior:
    """Describes expected behavior for a URL."""
    status_code: int | None      # Expected status, None if timeout
    latency_ms: float            # Response time in milliseconds
    should_retry: bool           # Whether client should retry
    body_keyword: str | None     # Keyword in response body, if any
    error_type: str | None       # "timeout", "connection", None

class URLProvider:
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self._behaviors: dict[str, URLBehavior] = {}
        self._generate_urls()

    def _generate_urls(self) -> None:
        """Generate URL set with various behaviors."""
        # URLs are httpbin.org endpoints that produce specific behaviors
        pass  # Implementation provided

    def next_url(self) -> str:
        """Get next URL to fetch."""
        ...

    def get_behavior(self, url: str) -> URLBehavior:
        """Get expected behavior for URL (for validation)."""
        ...

    def remaining(self) -> int:
        """Number of URLs remaining."""
        ...