import json
import random
import time
import urllib
from datetime import datetime, timezone
from os import error
from urllib.error import HTTPError,URLError
from urllib.request import urlopen

from url_provider import URLProvider


class ResponseHandler:
    def on_success(self, url: str, status: int, body: bytes, latency_ms: float) -> None:
        """
        Called for 2xx responses.
        Log the successful request.
        """
        raise NotImplementedError

    def on_client_error(self, url: str, status: int, body: bytes) -> None:
        """
        Called for 4xx responses.
        These indicate client mistakes (bad URL, unauthorized, etc.)
        Should NOT trigger retry.
        """
        raise NotImplementedError

    def on_server_error(self, url: str, status: int, attempt: int) -> None:
        """
        Called for 5xx responses.
        These indicate server problems.
        Should trigger retry with backoff.
        """
        raise NotImplementedError

    def on_timeout(self, url: str, attempt: int, timeout_sec: float) -> None:
        """
        Called when request times out.
        Should trigger retry with backoff.
        """
        raise NotImplementedError

    def on_connection_error(self, url: str, attempt: int, error: str) -> None:
        """
        Called when connection fails (DNS, refused, etc.)
        Should trigger retry with backoff (up to limit).
        """
        raise NotImplementedError

    def on_slow_response(self, url: str, latency_ms: float) -> None:
        """
        Called when response took > 500ms.
        Called IN ADDITION TO on_success if applicable.
        """
        raise NotImplementedError

    def on_retry(self, url: str, attempt: int, wait_ms: float, reason: str) -> None:
        """
        Called before each retry attempt.
        Log the retry with wait time and reason.
        """
        raise NotImplementedError

    def on_body_match(self, url: str, keyword: str) -> None:
        """
        Called when response body contains a monitored keyword.
        Called IN ADDITION TO on_success.
        """
        raise NotImplementedError

    def on_max_retries(self, url: str, attempts: int, last_error: str) -> None:
        """
        Called when max retry attempts exhausted.
        Log final failure.
        """
        raise NotImplementedError

class RobustHTTPClient:
    SLOW_THRESHOLD_MS = 500.0
    MAX_RETRIES = 3
    BASE_TIMEOUT_SEC = 5.0
    INITIAL_BACKOFF_MS = 100.0
    MAX_BACKOFF_MS = 5000.0
    BACKOFF_MULTIPLIER = 2.0
    MONITORED_KEYWORDS = ["error", "success", "data", "result"]

    def __init__(self, handler: ResponseHandler):
        self.handler = handler

    def fetch(self, url: str) -> bool:
        """
        Fetch URL with retry logic.

        Returns:
            True if eventually successful (2xx), False otherwise.

        Behavior:
        - 2xx: Success. Call on_success. If slow, also call on_slow_response.
               Check body for monitored keywords.
        - 4xx: Client error. Call on_client_error. Do NOT retry.
        - 5xx: Server error. Call on_server_error. Retry with backoff.
        - Timeout: Call on_timeout. Retry with backoff.
        - Connection error: Call on_connection_error. Retry with backoff.

        Retry uses exponential backoff:
            wait_ms = min(INITIAL_BACKOFF_MS * (BACKOFF_MULTIPLIER ** attempt), MAX_BACKOFF_MS)

        Before each retry, call on_retry.
        After max retries exhausted, call on_max_retries.
        """
        attempt=0
        while True:
            start_time = time.time()
            try:
                resp=urlopen(url)
                status=resp.getcode()
                body=resp.read()
                latency_ms=(time.time()-start_time)*1000
                latency_ms=round(latency_ms,1)

                if 199<status<300:
                    self.handler.on_success(url,status,body,latency_ms)

                    if latency_ms>self.SLOW_THRESHOLD_MS:
                        self.handler.on_slow_response(url,latency_ms)

                    try:
                        text=body.decode(error='ignore').lower()
                        for kw in self.MONITORED_KEYWORDS:
                            if kw in text:
                                self.handler.on_body_match(url,kw)
                    except Exception:
                        pass

                    return True

                elif 399<status<500:
                    self.handler.on_client_error(url,status,body)
                    return False

                elif 499<status<600:
                    self.handler.on_server_error(url,status,attempt)
                    reason="server_error"

            except HTTPError as e:
                status = e.code
                body = e.read()

                if 400 <= status < 500:
                    self.handler.on_client_error(url, status, body)
                    return False

                self.handler.on_server_error(url, status, attempt)
                reason = "server_error"

            except TimeoutError:
                self.handler.on_timeout(url, attempt, self.BASE_TIMEOUT_SEC)
                reason = "timeout"

            except URLError as e:
                if "timed out" in str(e.reason).lower():
                    self.handler.on_timeout(url, attempt, self.BASE_TIMEOUT_SEC)
                    reason = "timeout"
                else:
                    self.handler.on_connection_error(url, attempt, str(e.reason))
                    reason = "connection"

            if attempt >= self.MAX_RETRIES:
                self.handler.on_max_retries(url, attempt, reason)
                return False

            wait_ms = self.calculate_backoff(attempt)
            attempt += 1
            self.handler.on_retry(url, attempt, round(wait_ms,1), reason)
            time.sleep(wait_ms / 1000.0)


    def fetch_all(self, provider: URLProvider) -> dict:
        """
        Fetch all URLs from provider.

        Returns:
            Summary statistics dict.
        """
        while provider.remaining() > 0:
            url = provider.next_url()
            self.fetch(url)

        return self.handler.summary_output()

    def calculate_backoff(self,attempt: int) -> float:
        """
        Calculate backoff delay in milliseconds.

        Args:
            attempt: Retry attempt number (0-indexed)

        Returns:
            Delay in milliseconds

        Formula:
            base_delay = INITIAL_BACKOFF_MS * (BACKOFF_MULTIPLIER ** attempt)
            jitter = random.uniform(0, 0.1 * base_delay)
            delay = min(base_delay + jitter, MAX_BACKOFF_MS)
        """
        base_delay = self.INITIAL_BACKOFF_MS* (self.BACKOFF_MULTIPLIER ** attempt)
        jitter = random.uniform(0, 0.1 * base_delay)
        return min(base_delay + jitter, self.MAX_BACKOFF_MS)

class CoolResponseHandler(ResponseHandler):
    def __init__(self, log_path: str):
        self.log_path = log_path
        self.summary={
            "total_urls": 0,
            "successful": 0,
            "failed": 0,
            "total_requests": 0,
            "retries": 0,
            "avg_latency_ms": 0.0,
            "slow_responses": 0,
            "by_status": {},
            "by_error": {
                "timeout": 0,
                "connection": 0
            }
        }
        self.total_latency=0
        self.total_number_latency=0

    def summary_output(self):
        self.summary['total_urls']=self.summary['successful']+self.summary['failed']
        self.summary['total_requests'] = self.summary['total_urls'] + self.summary['retries']
        if self.total_number_latency!=0:
            self.summary['avg_latency_ms']=round(self.total_latency / self.total_number_latency,1)

        return self.summary



    def logger(self, content: dict) -> None:
        record = {"timestamp": (
            datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )}
        for k, v in content.items():
            record[k] = v
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def on_success(self, url: str, status: int, body: bytes, latency_ms: float) -> None:
        """
        Called for 2xx responses.
        Log the successful request.
        """
        content= {'url': url, 'event':"success", 'status': status, 'latency_ms': latency_ms}
        self.logger(content)
        self.summary['successful']+=1
        self.total_latency+=latency_ms
        self.total_number_latency+=1
        status_str = str(status)
        self.summary["by_status"].setdefault(status_str, 0)
        self.summary["by_status"][status_str] += 1



    def on_client_error(self, url: str, status: int, body: bytes) -> None:
        """
        Called for 4xx responses.
        These indicate client mistakes (bad URL, unauthorized, etc.)
        Should NOT trigger retry.
        """
        content= {'url': url, 'event':"client_error", 'status': status}
        self.logger(content)
        self.summary['failed']+=1
        status_str = str(status)
        self.summary["by_status"].setdefault(status_str, 0)
        self.summary["by_status"][status_str] += 1

    def on_server_error(self, url: str, status: int, attempt: int) -> None:
        """
        Called for 5xx responses.
        These indicate server problems.
        Should trigger retry with backoff.
        """
        content = {'url': url, 'event': "server_error", 'status': status, 'attempt':attempt}
        self.logger(content)
        status_str = str(status)
        self.summary["by_status"].setdefault(status_str, 0)
        self.summary["by_status"][status_str] += 1

    def on_timeout(self, url: str, attempt: int, timeout_sec: float) -> None:
        """
        Called when request times out.
        Should trigger retry with backoff.
        """
        content = {'url': url, 'event': "timeout", 'attempt':attempt, 'timeout_sec':timeout_sec}
        self.logger(content)
        self.summary["by_error"]["timeout"] += 1

    def on_connection_error(self, url: str, attempt: int, error: str) -> None:
        """
        Called when connection fails (DNS, refused, etc.)
        Should trigger retry with backoff (up to limit).
        """
        context={'url': url, 'event': "connection_error", 'attempt':attempt, 'error':error}
        self.logger(context)
        self.summary["by_error"]["connection"] += 1

    def on_slow_response(self, url: str, latency_ms: float) -> None:
        """
        Called when response took > 500ms.
        Called IN ADDITION TO on_success if applicable.
        """
        context={'url': url, 'event': "slow_response",  'latency_ms':latency_ms}
        self.logger(context)
        self.summary['slow_responses']+=1

    def on_retry(self, url: str, attempt: int, wait_ms: float, reason: str) -> None:
        """
        Called before each retry attempt.
        Log the retry with wait time and reason.
        """
        context={'url': url, 'event': "retry",  'attempt':attempt,'wait_ms':wait_ms,'reason':reason}
        self.logger(context)
        self.summary['retries']+=1

    def on_body_match(self, url: str, keyword: str) -> None:
        """
        Called when response body contains a monitored keyword.
        Called IN ADDITION TO on_success.
        """
        context={'url':url,'event':'body_match','keyword':keyword}
        self.logger(context)

    def on_max_retries(self, url: str, attempts: int, last_error: str) -> None:
        """
        Called when max retry attempts exhausted.
        Log final failure.
        """
        context={'url':url,'event':'max_retries','attempts':attempts,'last_error':last_error}
        self.logger(context)
        self.summary['failed']+=1

# if __name__ == "__main__":
#     class DummyProvider:
#         def __init__(self, urls):
#             self.urls = list(urls)

#         def next_url(self):
#             return self.urls.pop(0)

#         def remaining(self):
#             return len(self.urls)


#     provider = DummyProvider([
#         "https://httpbin.org/status/200",
#         "https://httpbin.org/status/503",
#         "https://httpbin.org/status/404",
#         "https://httpbin.org/delay/2",
#     ])


#     handler = CoolResponseHandler("output.log")
#     client = RobustHTTPClient(handler)

#     results = client.fetch_all(provider)

#     print("Summary:")
#     for k, v in results.items():
#         print(f"{k}: {v}")
