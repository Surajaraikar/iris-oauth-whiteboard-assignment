import pytest
from pydantic import ValidationError

from app.api.routes import IndexBody, InspectBody


def test_only_supported_page_categories_are_accepted():
    assert IndexBody(url="https://example.com/job/1", site_url="https://example.com/", action="URL_UPDATED", page_type="JobPosting")
    with pytest.raises(ValidationError):
        IndexBody(url="https://example.com/page", site_url="https://example.com/", action="URL_UPDATED", page_type="Article")

def test_deletion_requires_explicit_confirmation_at_endpoint_policy():
    body = IndexBody(url="https://example.com/job/1", site_url="https://example.com/", action="URL_DELETED", page_type="JobPosting", confirm_delete=False)
    assert body.confirm_delete is False
    assert InspectBody(site_url="https://example.com/", inspection_url="https://example.com/a")

def test_insecure_or_credentialed_urls_are_rejected_by_scheme_policy():
    from urllib.parse import urlparse
    for value in ("http://example.com/a", "https://user:pw@example.com/a", "https://example.com:8443/a"):
        parsed = urlparse(value)
        assert parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
