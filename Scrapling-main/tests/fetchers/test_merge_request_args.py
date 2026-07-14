"""Tests for _merge_request_args to ensure browser-only kwargs are excluded.

Regression tests for https://github.com/D4Vinci/Scrapling/issues/247
"""

import pytest

from scrapling.engines.static import FetcherClient


class TestMergeRequestArgsSkipsBrowserParams:
    """Verify that browser-only keyword arguments are stripped before
    the request dict is forwarded to curl_cffi's Session.request()."""

    def _build_args(self, **extra_kwargs):
        """Helper: instantiate a FetcherClient and call _merge_request_args."""
        client = FetcherClient()
        return client._merge_request_args(url="https://example.com", **extra_kwargs)

    def test_block_ads_excluded(self):
        """block_ads is a browser-engine param and must not leak into the
        HTTP request dict (fixes #247)."""
        args = self._build_args(block_ads=True)
        assert "block_ads" not in args

    def test_google_search_excluded(self):
        """google_search is a browser-engine param and should be stripped."""
        args = self._build_args(google_search=True)
        assert "google_search" not in args

    def test_extra_headers_excluded(self):
        """extra_headers is a browser-engine param and should be stripped."""
        args = self._build_args(extra_headers={"X-Custom": "val"})
        assert "extra_headers" not in args

    def test_url_present(self):
        """The url must always be present in the output dict."""
        args = self._build_args()
        assert args["url"] == "https://example.com"

    def test_valid_kwargs_passed_through(self):
        """Arbitrary curl_cffi-compatible kwargs should survive."""
        args = self._build_args(cookies={"session": "abc"})
        assert args.get("cookies") == {"session": "abc"}
