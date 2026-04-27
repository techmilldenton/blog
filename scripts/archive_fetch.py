#!/usr/bin/env python3
"""
archive_fetch.py — Rebuild techmill.co from the Wayback Machine for Pages CMS.

Queries the CDX API to discover all captured URLs, fetches the most recent
snapshot of each, converts WordPress HTML to Jekyll-compatible Markdown, and
writes a .pages.yml configuration for Pages CMS.

Usage:
    python3 scripts/archive_fetch.py
    python3 scripts/archive_fetch.py --dry-run
    python3 scripts/archive_fetch.py --limit 10 --download-media

Requirements:
    pip install -r requirements.txt
"""

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup

try:
    import html2text as _html2text
    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False
    print("Warning: html2text not installed — using plaintext fallback.")
    print("  Run: pip install html2text\n")

SITE_DOMAIN = "techmill.co"
CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK_BASE = "https://web.archive.org/web"
REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO_ROOT / "_posts"
PAGES_DIR = REPO_ROOT / "_pages"
MEDIA_DIR = REPO_ROOT / "media"
REQUEST_DELAY = 1.5  # seconds between Wayback requests (be polite)

# URL patterns that identify a blog post (date-based WP or sub-path under content dirs)
POST_PARENT_DIRS = {"blog", "education", "events", "news", "projects"}
POST_URL_RE = re.compile(r"/\d{4}/\d{2}/\d{2}/")  # classic WP date pattern

# URLs to skip entirely (functional/system pages, not content)
SKIP_URL_RE = re.compile(
    r"(/wp-(?!content/uploads)|/feed/|/xmlrpc|/wp-login|"
    r"\?(?!p=)|/tag/|/category/|/page/\d|/author/|"
    r"/comments/|\.xml$|\.rss$|/trackback/|"
    r"/cdn-cgi/|/donation-|/cart/|/checkout/|/my-account/|"
    r"/privacy-policy/|/terms-|/sitemap)"
)


def classify_url(original_url):
    """Return 'post', 'page', or 'skip'."""
    path = urlparse(original_url).path.strip("/")
    if not path:
        return "page"  # homepage

    parts = path.split("/")

    # Classic WordPress date-based posts
    if POST_URL_RE.search(original_url):
        return "post"

    # Sub-pages under known content parent directories  (e.g. /blog/my-post/)
    if len(parts) >= 2 and parts[0] in POST_PARENT_DIRS:
        return "post"

    return "page"


# ---------------------------------------------------------------------------
# CDX / Wayback helpers
# ---------------------------------------------------------------------------

def cdx_find_pages(domain):
    """Return a list of {timestamp, original} dicts for all HTML pages."""
    print(f"Querying CDX API for {domain}/* ...")
    params = {
        "url": f"{domain}/*",
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "urlkey",          # one result per unique URL
        "from": "20170101",
        "limit": "500",
    }
    resp = requests.get(CDX_API, params=params, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    if len(raw) < 2:
        return []

    header, rows = raw[0], raw[1:]
    return [dict(zip(header, r)) for r in rows]


def cdx_latest_snapshot(url):
    """Return the timestamp string of the most recent 200 snapshot for url."""
    params = {
        "url": url,
        "output": "json",
        "fl": "timestamp",
        "filter": "statuscode:200",
        "from": "20170101",
        "limit": "10",
    }
    resp = requests.get(CDX_API, params=params, timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    if len(raw) < 2:
        return None
    # CDX returns ascending order; last = most recent
    return raw[-1][0]


def wayback_url(timestamp, original_url):
    """Build an archive.org access URL."""
    if not original_url.startswith("http"):
        original_url = f"https://{SITE_DOMAIN}{original_url}"
    return f"{WAYBACK_BASE}/{timestamp}/{original_url}"


def fetch_url(url, session, delay=REQUEST_DELAY, binary=False):
    """Fetch a URL with polite rate limiting."""
    time.sleep(delay)
    resp = session.get(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    return resp.content if binary else resp.text


# ---------------------------------------------------------------------------
# HTML cleaning and extraction
# ---------------------------------------------------------------------------

def clean_wayback_artifacts(soup):
    """Remove Wayback Machine injected toolbar and scripts."""
    for sel in [
        "#wm-ipp-base", "#wm-ipp", "#donato",
        "script[src*='archive.org']",
        "link[href*='archive.org']",
        "style[type='text/css'][id^='wm']",
    ]:
        for el in soup.select(sel):
            el.decompose()


def rewrite_wayback_links(text):
    """Strip Wayback Machine prefix from internal URLs, leaving relative paths."""
    # https://web.archive.org/web/20190721110345/https://techmill.co/foo/
    # https://web.archive.org/web/20190721110345im_/https://...  (image modifier)
    return re.sub(
        r"https://web\.archive\.org/web/\d+[a-z_]*/https?://" + re.escape(SITE_DOMAIN),
        "",
        text,
    )


def html_to_markdown(html_fragment):
    """Convert an HTML string to Markdown."""
    if HAS_HTML2TEXT:
        h = _html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.body_width = 0          # no line wrapping
        h.wrap_links = False
        h.protect_links = True
        result = h.handle(html_fragment)
    else:
        result = BeautifulSoup(html_fragment, "html.parser").get_text(separator="\n")

    # Clean up Wayback URLs left in markdown
    return rewrite_wayback_links(result).strip()


def extract_meta(soup, prop):
    el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
    return el.get("content", "").strip() if el else None


def extract_page_data(soup, original_url, timestamp):
    """Extract structured data from a WordPress page's BeautifulSoup tree."""
    data = {}

    # Title — try structured selectors first, then og:title, then <title>
    h1 = (
        soup.find("h1", class_=re.compile(r"entry-title|post-title|page-title", re.I))
        or soup.find("h1")
    )
    if h1:
        data["title"] = h1.get_text(" ", strip=True)
    else:
        og = extract_meta(soup, "og:title")
        title_tag = soup.find("title")
        raw = og or (title_tag.get_text().strip() if title_tag else "Untitled")
        # Strip " – TechMill" or " | TechMill" suffix
        data["title"] = re.split(r"\s[–|—|\|]\s", raw)[0].strip()

    # Date
    time_el = (
        soup.find("time", class_=re.compile(r"entry-date|published|post-date", re.I))
        or soup.find("time", attrs={"datetime": True})
    )
    article_time = extract_meta(soup, "article:published_time")
    if time_el:
        data["date"] = time_el.get("datetime", time_el.get_text()).strip()
    elif article_time:
        data["date"] = article_time
    else:
        data["date"] = None

    # Author — prefer a dedicated author link, fall back to byline text
    author_link = soup.find("a", rel="author") or soup.find("span", class_=re.compile(r"\bauthor\b", re.I))
    if author_link:
        data["author"] = author_link.get_text(" ", strip=True)
    else:
        byline_el = soup.find(class_=re.compile(r"\bbyline\b|\bpost-author\b|\bentry-author\b", re.I))
        if byline_el:
            link = byline_el.find("a") or byline_el
            raw = link.get_text(" ", strip=True)
            # Strip anything after "  " (e.g. "David Brunow  Leave a comment")
            data["author"] = re.split(r"\s{2,}", raw)[0].strip()

    # Excerpt / description
    og_desc = extract_meta(soup, "og:description") or extract_meta(soup, "description")
    if og_desc:
        data["summary"] = og_desc

    # Categories & tags
    cats = [a.get_text(strip=True) for a in soup.select(".cat-links a, .category a, .entry-categories a")]
    if cats:
        data["categories"] = cats

    tags = [a.get_text(strip=True) for a in soup.select(".tags-links a, .tag a, .entry-tags a")]
    if tags:
        data["tags"] = tags

    # Main body content — try specific WP content divs first, then broaden
    content_el = (
        soup.find("div", class_=re.compile(r"entry-content|post-content|article-content|page-content", re.I))
        or soup.find("div", class_=re.compile(r"main-content|content-area|site-main", re.I))
        or soup.find("article")
        or soup.find("main")
        or soup.find("div", id=re.compile(r"^content$|^main$|^primary$|^page-content$", re.I))
        or soup.find("div", class_=re.compile(r"^content$", re.I))
        # Last resort: largest div with substantial text
        or max(
            (d for d in soup.find_all("div") if len(d.get_text(strip=True)) > 200),
            key=lambda d: len(d.get_text(strip=True)),
            default=None,
        )
    )

    if content_el:
        # Remove elements that aren't body copy
        for unwanted in content_el.select(
            "nav, aside, .sharedaddy, #comments, .comments-area, "
            ".post-navigation, .entry-meta, .entry-footer, "
            ".widget, .sidebar, header, footer, "
            ".wp-caption-text + script, script, style"
        ):
            unwanted.decompose()

        # Remove duplicate title headings
        title_text = data.get("title", "")
        for heading in content_el.find_all(["h1", "h2"]):
            if heading.get_text(strip=True).lower() == title_text.lower():
                heading.decompose()

        # Remove WordPress post-metadata lines ("By Author  Leave a comment  Category")
        for el in content_el.select(".post-meta, .entry-header .byline, .entry-header .posted-on"):
            el.decompose()

        md = html_to_markdown(str(content_el))

        # Strip leading lines that are pure WordPress metadata artifacts
        # e.g. "By Author  __[Leave a comment](...) __[Category](...)"
        lines = md.splitlines()
        clean_lines = []
        skip_leading_meta = True
        for line in lines:
            stripped = line.strip()
            if skip_leading_meta:
                # Skip blank lines and lines that look like WP metadata
                if not stripped:
                    continue
                if re.match(r"^(By |Posted by |#+ )", stripped) and re.search(r"\[Leave a comment\]|\[Blog\]|\[Category\]", stripped):
                    continue
                skip_leading_meta = False
            clean_lines.append(line)

        data["body"] = "\n".join(clean_lines).strip()
    else:
        data["body"] = ""

    return data


# ---------------------------------------------------------------------------
# Image downloading
# ---------------------------------------------------------------------------

def download_image(img_url, session, timestamp):
    """Download an image from the Wayback Machine and save to media/.

    Returns the local relative path (e.g. /media/image.jpg) or None on error.
    """
    # Construct archive image URL
    if "web.archive.org" not in img_url:
        img_url = wayback_url(timestamp + "im_", img_url)

    try:
        data = fetch_url(img_url, session, binary=True)
    except Exception as e:
        print(f"    Image download failed: {img_url} — {e}")
        return None

    # Derive filename
    parsed = urlparse(img_url)
    original_path = parsed.path.split("/")[-1]
    name = unquote(original_path) or hashlib.md5(img_url.encode()).hexdigest()

    # Strip any Wayback modifier suffix that crept into the filename
    name = re.sub(r"^[a-z_]+_/", "", name)

    ext = Path(name).suffix.lower()
    if not ext:
        mime = mimetypes.guess_type(img_url)[0] or "image/jpeg"
        ext = "." + mime.split("/")[-1]
        name += ext

    dest = MEDIA_DIR / name
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    if not dest.exists():
        dest.write_bytes(data)
        print(f"    Saved image: media/{name}")

    return f"/media/{name}"


# ---------------------------------------------------------------------------
# File output helpers
# ---------------------------------------------------------------------------

def normalize_date(raw, fallback_ts=None):
    """Return a YYYY-MM-DD string from various input formats."""
    if not raw:
        if fallback_ts and len(fallback_ts) >= 8:
            ts = fallback_ts
            return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        return "2019-01-01"

    # ISO 8601 with time
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        pass

    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(raw))
    return m.group(1) if m else "2019-01-01"


def slugify(text):
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def yaml_str(value):
    """Safely wrap a value in double-quoted YAML."""
    if not value:
        return '""'
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()
    return f'"{escaped}"'


def write_markdown(data, filepath):
    """Write a Jekyll Markdown file with YAML frontmatter."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    lines = ["---"]
    lines.append(f"layout: {data.get('layout', 'post')}")
    lines.append(f"title: {yaml_str(data.get('title', 'Untitled'))}")

    if data.get("date"):
        lines.append(f"date: {data['date']}")
    if data.get("author"):
        lines.append(f"author: {yaml_str(data['author'])}")
    if data.get("summary"):
        lines.append(f"summary: {yaml_str(data['summary'][:200])}")
    if data.get("categories"):
        lines.append(f"categories: {json.dumps(data['categories'])}")
    if data.get("tags"):
        lines.append(f"tags: {json.dumps(data['tags'])}")
    if data.get("permalink"):
        lines.append(f"permalink: {data['permalink']}")

    lines.append("---")
    lines.append("")
    lines.append(data.get("body", ""))

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# Pages CMS and Jekyll config generation
# ---------------------------------------------------------------------------

PAGES_YML = """\
# Pages CMS configuration
# https://pagescms.org/docs/configuration/

media:
  input: media
  output: /media
  categories: [image]

content:
  - name: posts
    label: Posts
    type: collection
    path: _posts
    filename: "{date}-{fields.slug}"
    view:
      fields: [title, date, author]
    fields:
      - { name: layout, type: string, hidden: true, default: post }
      - { name: title,  label: Title,  type: string, required: true }
      - { name: date,   label: Date,   type: date,   required: true }
      - { name: author, label: Author, type: string }
      - { name: summary, label: Summary, type: text }
      - name: categories
        label: Categories
        type: select
        multiple: true
        options:
          values: [community, education, environment, events, news, projects]
      - name: tags
        label: Tags
        type: select
        multiple: true
        creatable: true
        options:
          values: []
      - name: body
        label: Body
        type: rich-text

  - name: pages
    label: Pages
    type: collection
    path: _pages
    filename: "{fields.slug}"
    view:
      fields: [title, permalink]
    fields:
      - { name: layout,    type: string, hidden: true, default: page }
      - { name: title,     label: Title,     type: string, required: true }
      - { name: permalink, label: Permalink, type: string }
      - name: body
        label: Body
        type: rich-text
"""

JEKYLL_CONFIG = """\
title: TechMill
description: >-
  TechMill is a technology-focused community organization based in
  Denton, Texas.
url: https://techmill.co
baseurl: ""

# Build settings
markdown: kramdown
highlighter: rouge
permalink: /:year/:month/:day/:title/

# Collections
collections:
  pages:
    output: true
    permalink: /:name/

# Front matter defaults
defaults:
  - scope: { path: "", type: posts }
    values: { layout: post }
  - scope: { path: "", type: pages }
    values: { layout: page }

# Exclude from build output
exclude:
  - scripts/
  - "*.py"
  - requirements.txt
  - Gemfile
  - Gemfile.lock
  - vendor/
  - node_modules/
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Rebuild techmill.co from the Wayback Machine for Pages CMS"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Discover and list pages without writing any files",
    )
    parser.add_argument(
        "--limit", type=int, default=0, metavar="N",
        help="Process at most N pages (0 = all)",
    )
    parser.add_argument(
        "--download-media", action="store_true",
        help="Download images referenced in posts and save to media/",
    )
    parser.add_argument(
        "--timestamp", default="",
        help="Override archive timestamp for the homepage (e.g. 20190721110345)",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({
        "User-Agent": "TechmillArchiveRebuild/1.0 (rebuilding site from archive; contact: techmill.co)"
    })

    # ------------------------------------------------------------------
    # Step 1: Discover all captured pages via CDX
    # ------------------------------------------------------------------
    print("=" * 60)
    print("Step 1: Discovering pages via CDX API")
    print("=" * 60)

    try:
        entries = cdx_find_pages(SITE_DOMAIN)
    except Exception as e:
        print(f"CDX query failed: {e}")
        print("Falling back to homepage-only crawl.")
        ts = args.timestamp or "20190721110345"
        entries = [{"timestamp": ts, "original": f"https://{SITE_DOMAIN}/"}]

    if not entries:
        print("No pages found in CDX. Checking homepage only.")
        ts = args.timestamp or "20190721110345"
        entries = [{"timestamp": ts, "original": f"https://{SITE_DOMAIN}/"}]

    # Filter out non-content URLs
    filtered = []
    for e in entries:
        url = e["original"]
        if SKIP_URL_RE.search(url):
            continue
        if classify_url(url) == "skip":
            continue
        filtered.append(e)

    print(f"Discovered {len(filtered)} content URLs (filtered from {len(entries)} total)")

    if args.limit:
        filtered = filtered[:args.limit]
        print(f"Limited to {args.limit} URLs")

    if args.dry_run:
        print("\nDry run — pages that would be fetched:")
        for e in filtered:
            kind = classify_url(e["original"]).upper()
            print(f"  [{kind}] {e['original']}  (snapshot: {e['timestamp']})")
        print("\nWould write: .pages.yml, _config.yml")
        return

    # ------------------------------------------------------------------
    # Step 2: Fetch and convert each page
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Step 2: Fetching and converting pages")
    print("=" * 60)

    stats = {"posts": 0, "pages": 0, "skipped": 0, "errors": 0}
    seen_slugs = set()

    for entry in filtered:
        original_url = entry["original"]
        timestamp = entry.get("timestamp", "20190721110345")
        kind = classify_url(original_url).upper()
        is_post = kind == "POST"

        archive_url = wayback_url(timestamp, original_url)
        print(f"\n[{kind}] {original_url}")

        try:
            html = fetch_url(archive_url, session)
        except requests.HTTPError as e:
            print(f"  HTTP {e.response.status_code} — skipping")
            stats["errors"] += 1
            continue
        except Exception as e:
            print(f"  Fetch error: {e} — skipping")
            stats["errors"] += 1
            continue

        soup = BeautifulSoup(html, "html.parser")
        clean_wayback_artifacts(soup)

        data = extract_page_data(soup, original_url, timestamp)
        data["date"] = normalize_date(data.get("date"), timestamp)

        # Optionally download images
        if args.download_media:
            for img in soup.select("img[src]"):
                src = img.get("src", "")
                if not src or "data:" in src:
                    continue
                local = download_image(src, session, timestamp)
                if local:
                    img["src"] = local
            # Re-extract body with updated img src values
            content_el = (
                soup.find("div", class_=re.compile(r"entry-content|post-content", re.I))
                or soup.find("article") or soup.find("main")
            )
            if content_el:
                data["body"] = html_to_markdown(str(content_el))

        # Determine output path
        if is_post:
            data["layout"] = "post"
            slug = slugify(data["title"])
            # Avoid duplicate slugs
            unique_slug = slug
            counter = 2
            while unique_slug in seen_slugs:
                unique_slug = f"{slug}-{counter}"
                counter += 1
            seen_slugs.add(unique_slug)
            filename = f"{data['date']}-{unique_slug}.md"
            filepath = POSTS_DIR / filename
            stats["posts"] += 1
        else:
            data["layout"] = "page"
            url_path = urlparse(original_url).path.strip("/")
            if not url_path:
                url_path = "home"
            data.setdefault("permalink", f"/{url_path}/")
            slug = slugify(url_path.replace("/", "-") or data["title"])
            unique_slug = slug
            counter = 2
            while unique_slug in seen_slugs:
                unique_slug = f"{slug}-{counter}"
                counter += 1
            seen_slugs.add(unique_slug)
            filename = f"{unique_slug}.md"
            filepath = PAGES_DIR / filename
            stats["pages"] += 1

        written = write_markdown(data, filepath)
        print(f"  -> {written.relative_to(REPO_ROOT)}")

    # ------------------------------------------------------------------
    # Step 3: Write config files
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Step 3: Writing configuration files")
    print("=" * 60)

    pages_yml = REPO_ROOT / ".pages.yml"
    pages_yml.write_text(PAGES_YML, encoding="utf-8")
    print("Wrote: .pages.yml")

    config_yml = REPO_ROOT / "_config.yml"
    if not config_yml.exists():
        config_yml.write_text(JEKYLL_CONFIG, encoding="utf-8")
        print("Wrote: _config.yml")
    else:
        print("Skipped: _config.yml (already exists — review manually)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Posts written : {stats['posts']}")
    print(f"  Pages written : {stats['pages']}")
    print(f"  Errors        : {stats['errors']}")

    print("""
Next steps:
  1. Review content in _posts/ and _pages/
  2. Add missing images to media/ (or rerun with --download-media)
  3. git add -A && git commit -m "Rebuild site from Wayback Machine archive"
  4. Push to GitHub and connect at https://app.pagescms.org
""")


if __name__ == "__main__":
    main()
