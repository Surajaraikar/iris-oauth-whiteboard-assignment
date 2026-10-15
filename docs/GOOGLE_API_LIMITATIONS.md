# Google API limitations

- Search Console API `sites.list` discovers properties the current Google user can access.
- URL Inspection is read-only and reports the indexed version. It is not a live test and does not submit an indexing request.
- Indexing API is limited to JobPosting pages and livestream pages with BroadcastEvent nested in VideoObject. General-purpose URLs are not eligible.
- URL_UPDATED and URL_DELETED send crawl/index notifications. A successful response is not evidence of indexing/removal.
- Google requires Indexing API enablement and quota/approval. The user must have appropriate Search Console ownership/permission.
- The implementation accepts the declared page category from the operator and does not fetch the URL to inspect structured data. Google remains authoritative and can reject ineligible pages.
- API quotas, permissions, OAuth verification and token policies depend on the Google Cloud project and user account.

See [official Indexing API guidance](https://developers.google.com/search/apis/indexing-api/v3/quickstart), [URL Inspection](https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect), and [OAuth token behavior](https://developers.google.com/identity/protocols/oauth2).
