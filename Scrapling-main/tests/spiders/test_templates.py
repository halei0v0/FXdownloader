"""Tests for `CrawlSpider` and `CrawlRule`."""

import pickle

import pytest

from scrapling.engines.toolbelt.custom import Response
from scrapling.spiders.links import LinkExtractor
from scrapling.spiders.request import Request
from scrapling.spiders.templates import CrawlRule, CrawlSpider
from scrapling.core._types import Any, AsyncGenerator, Dict, Union


HTML = """
<html><body>
  <a href="/posts/1">post 1</a>
  <a href="/posts/2">post 2</a>
  <a href="/page/2/">next page</a>
  <a href="/about">about</a>
</body></html>
"""


def _make_response(url: str = "https://example.com/") -> Response:
    """Build a Response with a Request attached so `response.follow()` works."""
    resp = Response(
        url=url,
        content=HTML,
        status=200,
        reason="OK",
        cookies={},
        headers={},
        request_headers={},
    )
    resp.request = Request(url)
    return resp


class _TestSpider(CrawlSpider):
    name = "test"
    start_urls = ["https://example.com/"]

    async def parse_post(self, response: Response) -> AsyncGenerator[Union[Dict[str, Any], Request, None], None]:
        yield {"post": response.url}

    async def parse_page(self, response: Response) -> AsyncGenerator[Union[Dict[str, Any], Request, None], None]:
        yield {"page": response.url}


async def _collect(agen: AsyncGenerator) -> list:
    return [item async for item in agen]


class TestCrawlSpider:
    @pytest.mark.asyncio
    async def test_empty_rules_yields_nothing(self):
        class S(CrawlSpider):
            name = "s"
            start_urls = ["https://example.com/"]

        spider = S()
        out = await _collect(spider.parse(_make_response()))
        assert out == []

    @pytest.mark.asyncio
    async def test_single_rule_yields_matching_links(self):
        class S(CrawlSpider):
            name = "s"
            start_urls = ["https://example.com/"]

            def rules(self):
                return [CrawlRule(LinkExtractor(allow=r"/posts/"))]

        spider = S()
        out = await _collect(spider.parse(_make_response()))
        urls = [r.url for r in out]
        assert urls == ["https://example.com/posts/1", "https://example.com/posts/2"]

    @pytest.mark.asyncio
    async def test_multiple_rules_all_applied(self):
        class S(CrawlSpider):
            name = "s"
            start_urls = ["https://example.com/"]

            def rules(self):
                return [
                    CrawlRule(LinkExtractor(allow=r"/posts/")),
                    CrawlRule(LinkExtractor(allow=r"/page/")),
                ]

        spider = S()
        out = await _collect(spider.parse(_make_response()))
        urls = [r.url for r in out]
        assert "https://example.com/posts/1" in urls
        assert "https://example.com/posts/2" in urls
        assert "https://example.com/page/2/" in urls

    @pytest.mark.asyncio
    async def test_rule_with_callback_bound_method(self):
        spider = _TestSpider()
        # rules() defaults to []; override at instance level
        spider.rules = lambda: [  # type: ignore[method-assign]
            CrawlRule(LinkExtractor(allow=r"/posts/"), callback=spider.parse_post)
        ]
        out = await _collect(spider.parse(_make_response()))
        assert all(r.callback == spider.parse_post for r in out)

    @pytest.mark.asyncio
    async def test_rule_with_no_callback_leaves_request_callback_none(self):
        # When CrawlRule.callback is None, response.follow() inherits the original
        # request's callback. The original request was created with callback=None,
        # so the resulting request's callback should also be None (engine then
        # falls back to spider.parse).
        class S(CrawlSpider):
            name = "s"
            start_urls = ["https://example.com/"]

            def rules(self):
                return [CrawlRule(LinkExtractor(allow=r"/posts/"))]

        spider = S()
        out = await _collect(spider.parse(_make_response()))
        assert all(r.callback is None for r in out)

    @pytest.mark.asyncio
    async def test_process_request_invoked(self):
        spider = _TestSpider()

        def add_priority(req: Request, response: Response) -> Request:
            req.priority = 99
            return req

        spider.rules = lambda: [  # type: ignore[method-assign]
            CrawlRule(LinkExtractor(allow=r"/posts/"), process_request=add_priority)
        ]
        out = await _collect(spider.parse(_make_response()))
        assert all(r.priority == 99 for r in out)

    @pytest.mark.asyncio
    async def test_process_request_can_replace_request(self):
        spider = _TestSpider()
        replacement = Request("https://replaced.example.com/")

        def replace(req: Request, response: Response) -> Request:
            return replacement

        spider.rules = lambda: [  # type: ignore[method-assign]
            CrawlRule(LinkExtractor(allow=r"/posts/"), process_request=replace)
        ]
        out = await _collect(spider.parse(_make_response()))
        assert all(r is replacement for r in out)

    @pytest.mark.asyncio
    async def test_user_can_compose_super_parse(self):
        """Override parse() to add custom yields plus call super().parse() for rules."""

        class S(CrawlSpider):
            name = "s"
            start_urls = ["https://example.com/"]

            def rules(self):
                return [CrawlRule(LinkExtractor(allow=r"/posts/"))]

            async def parse(self, response):
                yield {"custom": "item"}
                async for req in super().parse(response):
                    yield req

        spider = S()
        out = await _collect(spider.parse(_make_response()))
        assert out[0] == {"custom": "item"}
        assert all(isinstance(x, Request) for x in out[1:])
        assert len(out) == 3  # 1 dict + 2 requests

    @pytest.mark.asyncio
    async def test_referer_set_on_followed_requests(self):
        # `response.follow()` sets the referer header; verify it survives the rule path.
        class S(CrawlSpider):
            name = "s"
            start_urls = ["https://example.com/"]

            def rules(self):
                return [CrawlRule(LinkExtractor(allow=r"/posts/"))]

        spider = S()
        out = await _collect(spider.parse(_make_response()))
        for req in out:
            assert req._session_kwargs["headers"]["referer"] == "https://example.com/"


class TestCrawlSpiderPickle:
    """Verify Request produced by CrawlSpider survives pickle round-trip with bound-method callbacks."""

    @pytest.mark.asyncio
    async def test_pickle_request_with_bound_method_callback(self):
        spider = _TestSpider()
        spider.rules = lambda: [  # type: ignore[method-assign]
            CrawlRule(LinkExtractor(allow=r"/posts/"), callback=spider.parse_post)
        ]
        out = await _collect(spider.parse(_make_response()))
        req = out[0]

        # __getstate__ should convert the bound method into a name-string
        state = req.__getstate__()
        assert state["callback"] is None
        assert state["_callback_name"] == "parse_post"

        # Round-trip via pickle (bound methods aren't directly picklable; the
        # state machinery handles the conversion)
        pickled = pickle.dumps(req)
        restored = pickle.loads(pickled)
        assert restored._callback_name == "parse_post"

        # Then _restore_callback on a fresh spider instance brings the method back
        fresh_spider = _TestSpider()
        restored._restore_callback(fresh_spider)
        assert restored.callback == fresh_spider.parse_post


class TestCrawlRule:
    def test_default_callback_is_none(self):
        rule = CrawlRule(LinkExtractor())
        assert rule.callback is None
        assert rule.priority is None
        assert rule.process_request is None

    def test_callback_accepts_callable(self):
        spider = _TestSpider()
        rule = CrawlRule(LinkExtractor(), callback=spider.parse_post)
        assert rule.callback == spider.parse_post
