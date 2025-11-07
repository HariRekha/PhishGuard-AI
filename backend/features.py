import re
import math
from collections import Counter
import tldextract
import string
from typing import Dict
from urllib.parse import urlparse
from config import SUSPICIOUS_TOKENS

IP_REGEX = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
SPECIAL_CHARS = set(string.punctuation)

def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    entropy = 0.0
    length = len(s)
    for v in counts.values():
        p = v / length
        entropy -= p * math.log2(p)
    return entropy

def has_ip_in_host(host: str) -> bool:
    if not host:
        return False
    host = host.strip("[]")
    if IP_REGEX.match(host):
        return True
    if ":" in host and any(c.isalpha() or c.isdigit() for c in host):
        return True
    return False

def count_tokens_in_string(s: str, tokens=None) -> int:
    if not s:
        return 0
    if tokens is None:
        tokens = SUSPICIOUS_TOKENS
    s_low = s.lower()
    count = 0
    for t in tokens:
        if not t:
            continue
        count += s_low.count(t.lower())
    return count

def extract_features(url: str) -> Dict[str, float]:
    url = (url or "").strip()
    features = {}
    parsed = urlparse(url if url else "")
    scheme = parsed.scheme or ""
    netloc = parsed.netloc or parsed.path
    path = parsed.path or ""
    query = parsed.query or ""
    fragment = parsed.fragment or ""
    te = tldextract.extract(url)
    subdomain = te.subdomain or ""
    domain = te.domain or ""
    suffix = te.suffix or ""
    host = netloc
    if ":" in host:
        host = host.split(":")[0]
    url_length = len(url)
    hostname_length = len(host)
    count_dots = url.count(".")
    count_hyphens = url.count("-")
    count_underscores = url.count("_")
    count_digits = sum(c.isdigit() for c in url)
    count_subdirs = path.count("/")
    count_query_params = query.count("&") + 1 if query else 0
    has_at = "@" in url
    has_double_slash_in_path = "//" in path and not url.startswith("//")
    suspicious_token_count = count_tokens_in_string(url)
    ratio_digits_to_length = count_digits / url_length if url_length else 0.0
    num_special = sum(1 for c in url if c in SPECIAL_CHARS)
    ratio_special_to_length = num_special / url_length if url_length else 0.0
    entropy = shannon_entropy(url)
    ip_in_host = has_ip_in_host(host)
    domain_age_days = -1

    # New: numeric summaries instead of raw strings for high-cardinality fields
    subdomain_length = len(subdomain)
    subdomain_depth = len([p for p in subdomain.split(".") if p]) if subdomain else 0
    domain_length = len(domain)

    features.update({
        "url_length": url_length,
        "hostname_length": hostname_length,
        "count_dots": count_dots,
        "count_hyphens": count_hyphens,
        "count_underscores": count_underscores,
        "count_digits": count_digits,
        "count_subdirs": count_subdirs,
        "count_query_params": count_query_params,
        "has_at_symbol": int(has_at),
        "has_double_slash_in_path": int(has_double_slash_in_path),
        "suspicious_token_count": suspicious_token_count,
        "tld": suffix,                       # keep as small categorical
        "character_entropy": entropy,
        "ratio_digits_to_length": ratio_digits_to_length,
        "ratio_special_chars_to_length": ratio_special_to_length,
        "has_ip_in_host": int(ip_in_host),
        "domain_age_days": domain_age_days,
        "scheme": scheme.lower(),            # small categorical
        "subdomain_length": subdomain_length,
        "subdomain_depth": subdomain_depth,
        "domain_length": domain_length,
        # removed: raw 'subdomain' and 'domain' strings to avoid high cardinality
    })
    return features

def features_schema() -> Dict[str, str]:
    return {
        "url_length": "Total length of the URL string",
        "hostname_length": "Length of the hostname (netloc)",
        "count_dots": "Number of '.' characters in the URL",
        "count_hyphens": "Number of '-' characters in the URL",
        "count_underscores": "Number of '_' characters in the URL",
        "count_digits": "Total digit characters in the URL",
        "count_subdirs": "Number of '/' path segments",
        "count_query_params": "Count of query parameters (heuristic)",
        "has_at_symbol": "Presence of '@' symbol (common in phishing obfuscation)",
        "has_double_slash_in_path": "Presence of '//' later in path",
        "suspicious_token_count": "Count of suspicious tokens like 'login','secure'",
        "tld": "Top-level domain (suffix)",
        "character_entropy": "Shannon entropy of the URL string",
        "ratio_digits_to_length": "Digits / URL length",
        "ratio_special_chars_to_length": "Special char count / URL length",
        "has_ip_in_host": "Whether hostname is an IP address literal",
        "domain_age_days": "Placeholder for domain age (days) if available; -1 = unknown",
        "scheme": "URL scheme (http/https)",
        "subdomain_length": "Length of the subdomain string",
        "subdomain_depth": "Number of labels in subdomain (e.g., a.b -> 2)",
        "domain_length": "Length of the registered domain name"
    }
