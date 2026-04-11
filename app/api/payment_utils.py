from __future__ import annotations

import re
from urllib.parse import urlencode, unquote, urlparse


FALLBACK_FAIL_PAGE_URL = "https://romanomak.ru"


def _iter_url_candidates(*raw_values: str | None):
    for raw_value in raw_values:
        if not raw_value:
            continue

        decoded_value = unquote(raw_value).strip()
        if not decoded_value:
            continue

        for part in re.split(r"[\s,;]+", decoded_value):
            candidate = part.strip().strip("'\"")
            if candidate:
                yield candidate


def _normalize_candidate_url(candidate: str) -> str | None:
    fixed_candidate = candidate
    if fixed_candidate.startswith("https//"):
        fixed_candidate = f"https://{fixed_candidate[len('https//'):]}"
    elif fixed_candidate.startswith("http//"):
        fixed_candidate = f"http://{fixed_candidate[len('http//'):]}"
    elif fixed_candidate.startswith("//"):
        fixed_candidate = f"https:{fixed_candidate}"
    elif "://" not in fixed_candidate and "." in fixed_candidate:
        fixed_candidate = f"https://{fixed_candidate.lstrip('/')}"

    parsed = urlparse(fixed_candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    normalized_path = parsed.path or ""
    return f"{parsed.scheme}://{parsed.netloc}{normalized_path}"


def resolve_fail_page_url(*raw_values: str | None) -> str:
    for candidate in _iter_url_candidates(*raw_values):
        normalized = _normalize_candidate_url(candidate)
        if normalized:
            return normalized

    return FALLBACK_FAIL_PAGE_URL


def resolve_payment_return_url(*raw_values: str | None, status: str = "cancelled") -> str:
    site_url = resolve_fail_page_url(*raw_values)
    parsed = urlparse(site_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    query = urlencode({"status": status, "next": "/"})
    return f"{base_url}/api/payment/return?{query}"
