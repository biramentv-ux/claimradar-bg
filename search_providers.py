import os
import re
import urllib.parse
import urllib.request
from html import unescape
from typing import Dict, List

import requests

SOURCE_WHITELIST = [
    "nsi.bg",
    "bnb.bg",
    "nssi.bg",
    "nra.bg",
    "cik.bg",
    "parliament.bg",
    "dv.parliament.bg",
    "minfin.bg",
    "gov.bg",
    "ec.europa.eu",
    "factcheck.bg",
    "bta.bg",
    "bnr.bg",
]

SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "auto").lower().strip()
SEARCH_STRICT_WHITELIST = os.getenv("SEARCH_STRICT_WHITELIST", "1").lower() not in {"0", "false", "no"}
SEARCH_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT", "8"))

BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")


def active_search_config() -> Dict[str, object]:
    return {
        "provider": SEARCH_PROVIDER,
        "strict_whitelist": SEARCH_STRICT_WHITELIST,
        "whitelist": SOURCE_WHITELIST,
        "available_api_providers": {
            "brave": bool(BRAVE_SEARCH_API_KEY),
            "bing": bool(BING_SEARCH_API_KEY),
            "tavily": bool(TAVILY_API_KEY),
            "serpapi": bool(SERPAPI_API_KEY),
            "google_cse": bool(GOOGLE_SEARCH_API_KEY and GOOGLE_CSE_ID),
            "duckduckgo": True,
        },
    }


def clean_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url: str) -> str:
    url = unescape(url or "")
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if "uddg" in params and params["uddg"]:
        return params["uddg"][0]
    return url


def url_domain(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def is_allowed_url(url: str) -> bool:
    if not SEARCH_STRICT_WHITELIST:
        return True
    host = url_domain(url)
    return any(host == domain or host.endswith("." + domain) for domain in SOURCE_WHITELIST)


def normalize_results(results: List[Dict[str, str]], limit: int) -> List[Dict[str, str]]:
    out = []
    seen = set()
    for item in results:
        url = normalize_url(item.get("url", ""))
        title = clean_html(item.get("title", ""))[:180]
        snippet = clean_html(item.get("snippet", ""))[:360]
        if not url.startswith("http") or not title:
            continue
        if url in seen:
            continue
        if not is_allowed_url(url):
            continue
        seen.add(url)
        out.append({"title": title, "url": url, "snippet": snippet})
        if len(out) >= limit:
            break
    return out


def search_duckduckgo(query: str, limit: int = 3) -> List[Dict[str, str]]:
    search_url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0 ClaimRadarBG/Search/2.3"})
    try:
        html = urllib.request.urlopen(request, timeout=SEARCH_TIMEOUT).read().decode("utf-8", errors="ignore")
    except Exception:
        return []
    results = []
    pattern = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?(?:<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>)', re.S)
    for match in pattern.finditer(html):
        results.append({
            "url": normalize_url(match.group(1)),
            "title": match.group(2),
            "snippet": match.group(3) or match.group(4) or "",
        })
    return normalize_results(results, limit)


def search_brave(query: str, limit: int = 3) -> List[Dict[str, str]]:
    if not BRAVE_SEARCH_API_KEY:
        return []
    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"X-Subscription-Token": BRAVE_SEARCH_API_KEY, "Accept": "application/json"},
        params={"q": query, "count": min(max(limit, 1), 10), "search_lang": "bg"},
        timeout=SEARCH_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    results = [{"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")} for r in data.get("web", {}).get("results", [])]
    return normalize_results(results, limit)


def search_bing(query: str, limit: int = 3) -> List[Dict[str, str]]:
    if not BING_SEARCH_API_KEY:
        return []
    response = requests.get(
        "https://api.bing.microsoft.com/v7.0/search",
        headers={"Ocp-Apim-Subscription-Key": BING_SEARCH_API_KEY},
        params={"q": query, "count": min(max(limit, 1), 10), "mkt": "bg-BG"},
        timeout=SEARCH_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    results = [{"title": r.get("name", ""), "url": r.get("url", ""), "snippet": r.get("snippet", "")} for r in data.get("webPages", {}).get("value", [])]
    return normalize_results(results, limit)


def search_tavily(query: str, limit: int = 3) -> List[Dict[str, str]]:
    if not TAVILY_API_KEY:
        return []
    response = requests.post(
        "https://api.tavily.com/search",
        json={"api_key": TAVILY_API_KEY, "query": query, "max_results": min(max(limit, 1), 10), "include_answer": False, "search_depth": "basic"},
        timeout=SEARCH_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    results = [{"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")} for r in data.get("results", [])]
    return normalize_results(results, limit)


def search_serpapi(query: str, limit: int = 3) -> List[Dict[str, str]]:
    if not SERPAPI_API_KEY:
        return []
    response = requests.get(
        "https://serpapi.com/search.json",
        params={"engine": "google", "q": query, "api_key": SERPAPI_API_KEY, "hl": "bg", "num": min(max(limit, 1), 10)},
        timeout=SEARCH_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    results = [{"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("snippet", "")} for r in data.get("organic_results", [])]
    return normalize_results(results, limit)


def search_google_cse(query: str, limit: int = 3) -> List[Dict[str, str]]:
    if not (GOOGLE_SEARCH_API_KEY and GOOGLE_CSE_ID):
        return []
    response = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"key": GOOGLE_SEARCH_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "num": min(max(limit, 1), 10), "lr": "lang_bg"},
        timeout=SEARCH_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    results = [{"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("snippet", "")} for r in data.get("items", [])]
    return normalize_results(results, limit)


def provider_order() -> List[str]:
    if SEARCH_PROVIDER and SEARCH_PROVIDER != "auto":
        return [SEARCH_PROVIDER, "duckduckgo"] if SEARCH_PROVIDER != "duckduckgo" else ["duckduckgo"]
    order = []
    if BRAVE_SEARCH_API_KEY:
        order.append("brave")
    if BING_SEARCH_API_KEY:
        order.append("bing")
    if TAVILY_API_KEY:
        order.append("tavily")
    if SERPAPI_API_KEY:
        order.append("serpapi")
    if GOOGLE_SEARCH_API_KEY and GOOGLE_CSE_ID:
        order.append("google_cse")
    order.append("duckduckgo")
    return order


def enhanced_search_web(query: str, limit: int = 3) -> List[Dict[str, str]]:
    providers = {
        "brave": search_brave,
        "bing": search_bing,
        "tavily": search_tavily,
        "serpapi": search_serpapi,
        "google": search_google_cse,
        "google_cse": search_google_cse,
        "duckduckgo": search_duckduckgo,
    }
    errors = []
    for provider in provider_order():
        fn = providers.get(provider)
        if not fn:
            continue
        try:
            results = fn(query, limit=limit)
            if results:
                return results[:limit]
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
            continue
    return []
