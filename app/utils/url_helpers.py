from urllib.parse import urljoin, urlparse

from flask import request


def is_safe_redirect_url(target):
    if not target:
        return False

    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return (
        test_url.scheme in ("http", "https")
        and ref_url.netloc == test_url.netloc
    )
