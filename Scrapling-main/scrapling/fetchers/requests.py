from scrapling.core._types import Any, Awaitable, Unpack
from scrapling.engines._browsers._types import DataRequestParams, GetRequestParams
from scrapling.engines.static import (
    FetcherSession,
    FetcherClient as _FetcherClient,
    AsyncFetcherClient as _AsyncFetcherClient,
)
from scrapling.engines.toolbelt.custom import BaseFetcher, Response

__all__ = ["Fetcher", "AsyncFetcher", "FetcherSession"]


__FetcherClientInstance__ = _FetcherClient()
__AsyncFetcherClientInstance__ = _AsyncFetcherClient()


def _merge_selector_config(cls: type[BaseFetcher], kwargs: Any) -> Any:
    """Merge class-level parser arguments into per-request ``selector_config``.

    Values from ``Fetcher.configure(...)`` act as the base; any explicit
    ``selector_config`` passed on the call overrides them.
    """
    selector_config = kwargs.get("selector_config") or {}
    kwargs["selector_config"] = {**cls._generate_parser_arguments(), **selector_config}
    return kwargs


class Fetcher(BaseFetcher):
    """A basic `Fetcher` class type that can only do basic GET, POST, PUT, and DELETE HTTP requests based on `curl_cffi`."""

    @classmethod
    def get(cls, url: str, **kwargs: Unpack[GetRequestParams]) -> Response:
        return __FetcherClientInstance__.get(url, **_merge_selector_config(cls, kwargs))

    @classmethod
    def post(cls, url: str, **kwargs: Unpack[DataRequestParams]) -> Response:
        return __FetcherClientInstance__.post(url, **_merge_selector_config(cls, kwargs))

    @classmethod
    def put(cls, url: str, **kwargs: Unpack[DataRequestParams]) -> Response:
        return __FetcherClientInstance__.put(url, **_merge_selector_config(cls, kwargs))

    @classmethod
    def delete(cls, url: str, **kwargs: Unpack[DataRequestParams]) -> Response:
        return __FetcherClientInstance__.delete(url, **_merge_selector_config(cls, kwargs))


class AsyncFetcher(BaseFetcher):
    """A basic `Fetcher` class type that can only do basic GET, POST, PUT, and DELETE HTTP requests based on `curl_cffi`."""

    @classmethod
    def get(cls, url: str, **kwargs: Unpack[GetRequestParams]) -> Awaitable[Response]:
        return __AsyncFetcherClientInstance__.get(url, **_merge_selector_config(cls, kwargs))

    @classmethod
    def post(cls, url: str, **kwargs: Unpack[DataRequestParams]) -> Awaitable[Response]:
        return __AsyncFetcherClientInstance__.post(url, **_merge_selector_config(cls, kwargs))

    @classmethod
    def put(cls, url: str, **kwargs: Unpack[DataRequestParams]) -> Awaitable[Response]:
        return __AsyncFetcherClientInstance__.put(url, **_merge_selector_config(cls, kwargs))

    @classmethod
    def delete(cls, url: str, **kwargs: Unpack[DataRequestParams]) -> Awaitable[Response]:
        return __AsyncFetcherClientInstance__.delete(url, **_merge_selector_config(cls, kwargs))
