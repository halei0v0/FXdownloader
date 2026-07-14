"""
Tests for Selectors.filter() method edge cases.
Target file: tests/parser/test_parser_advanced.py (append to TestAdvancedSelectors class)
"""
import pytest
from scrapling import Selector, Selectors


@pytest.fixture
def page():
    html = """
    <html><body>
        <ul>
            <li class="item" data-value="10">Apple</li>
            <li class="item" data-value="5">Banana</li>
            <li class="item" data-value="20">Cherry</li>
            <li class="item disabled" data-value="0">Durian</li>
        </ul>
    </body></html>
    """
    return Selector(html, adaptive=False)


class TestSelectorsFilter:
    def test_filter_basic(self, page):
        """filter() should return only elements matching the predicate"""
        items = page.css("li.item")
        expensive = items.filter(lambda el: int(el.attrib.get("data-value", 0)) >= 10)
        assert len(expensive) == 2
        texts = expensive.getall()
        assert any("Apple" in t for t in texts)
        assert any("Cherry" in t for t in texts)

    def test_filter_returns_empty_selectors_when_no_match(self, page):
        """filter() should return an empty Selectors (not None/exception) when nothing matches"""
        items = page.css("li.item")
        result = items.filter(lambda el: int(el.attrib.get("data-value", 0)) > 9999)
        assert isinstance(result, Selectors)
        assert len(result) == 0
        assert result.first is None

    def test_filter_all_pass(self, page):
        """filter() with always-True predicate should return all elements"""
        items = page.css("li.item")
        result = items.filter(lambda el: True)
        assert len(result) == len(items)

    def test_filter_chained(self, page):
        """filter() should be chainable - apply two filters in sequence"""
        items = page.css("li.item")
        # First: value > 0, then: not disabled
        result = (
            items
            .filter(lambda el: int(el.attrib.get("data-value", 0)) > 0)
            .filter(lambda el: not el.has_class("disabled"))
        )
        assert len(result) == 3  # Apple, Banana, Cherry (Durian is disabled AND value=0)

    def test_filter_on_empty_selectors(self):
        """filter() on an already-empty Selectors should not raise"""
        empty = Selectors()
        result = empty.filter(lambda el: True)
        assert isinstance(result, Selectors)
        assert len(result) == 0
