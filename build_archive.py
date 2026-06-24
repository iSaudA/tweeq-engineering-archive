import html
import json
import re
import shutil
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "site"
ASSETS = DIST / "assets"
POSTS = DIST / "posts"
RAW = ROOT / "archive-data"
FEED_URL = "https://engineering.tweeq.sa/feed"

AUTHOR_LINKS = {
    "Yazeed AlKhalaf": "https://medium.com/@yazeedalkhalaf",
    "Atheer Alabdullatif": "https://medium.com/@atheer",
    "Abdulaziz AlMalki": "https://medium.com/@abdulaziz",
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TweeqEngineeringArchive/1.0 (+local preservation)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read()


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def text_from_html(markup: str) -> str:
    clean = re.sub(r"<(script|style).*?</\1>", "", markup, flags=re.I | re.S)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def first_image(markup: str) -> str:
    match = re.search(r'<img[^>]+src="([^"]+)"', markup, flags=re.I)
    return html.unescape(match.group(1)) if match else ""


def read_feed():
    RAW.mkdir(exist_ok=True)
    xml_bytes = fetch(FEED_URL)
    (RAW / "engineering.tweeq.sa.feed.xml").write_bytes(xml_bytes)
    root = ET.fromstring(xml_bytes)
    ns = {
        "content": "http://purl.org/rss/1.0/modules/content/",
        "dc": "http://purl.org/dc/elements/1.1/",
        "atom": "http://www.w3.org/2005/Atom",
    }
    posts = []
    for item in root.findall("./channel/item"):
        title = item.findtext("title", default="")
        content = item.findtext("content:encoded", default="", namespaces=ns)
        pub_date = parsedate_to_datetime(item.findtext("pubDate", default=""))
        author = item.findtext("dc:creator", default="", namespaces=ns)
        categories = [cat.text or "" for cat in item.findall("category")]
        original_url = item.findtext("link", default="").split("?")[0]
        guid = item.findtext("guid", default="")
        post_id = guid.rstrip("/").split("/")[-1]
        display_date = f"{pub_date.strftime('%b')} {pub_date.day}, {pub_date.year}"
        posts.append(
            {
                "title": title,
                "slug": slugify(title),
                "author": author,
                "author_url": AUTHOR_LINKS.get(author, "https://engineering.tweeq.sa"),
                "date": pub_date.strftime("%Y-%m-%d"),
                "display_date": display_date,
                "categories": categories,
                "original_url": original_url,
                "post_id": post_id,
                "content": content,
                "excerpt": text_from_html(content)[:220].rsplit(" ", 1)[0] + "...",
                "hero": first_image(content),
            }
        )
    return posts


def localize_assets(posts):
    ASSETS.mkdir(parents=True, exist_ok=True)
    image_map = {}
    image_pattern = re.compile(r'<img([^>]+?)src="([^"]+)"([^>]*)>', flags=re.I)

    for post in posts:
        def replace(match):
            before, url, after = match.groups()
            clean_url = html.unescape(url)
            if "medium.com/_/stat" in clean_url:
                return ""
            if clean_url not in image_map:
                parsed = urllib.parse.urlparse(clean_url)
                suffix = Path(parsed.path).suffix
                if not suffix or len(suffix) > 6:
                    suffix = ".jpg"
                name = f"{post['slug']}-{len(image_map) + 1}{suffix}"
                target = ASSETS / name
                try:
                    target.write_bytes(fetch(clean_url))
                    image_map[clean_url] = f"assets/{name}"
                except Exception:
                    image_map[clean_url] = clean_url
            src = image_map[clean_url]
            return f'<img{before}src="../{src}"{after} loading="lazy">'

        post["content"] = image_pattern.sub(replace, post["content"])
        if post["hero"] in image_map:
            post["hero"] = image_map[post["hero"]]

    (RAW / "posts.json").write_text(json.dumps(posts, indent=2, ensure_ascii=False), encoding="utf-8")
    return posts


def page_shell(title, body, description="Tweeq Engineering archive"):
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}">
  <link rel="stylesheet" href="../styles.css">
</head>
<body>
{body}
</body>
</html>
"""


def build_site(posts):
    POSTS.mkdir(parents=True)
    ASSETS.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(ROOT / "styles.css", DIST / "styles.css")
    shutil.copyfile(ROOT / "script.js", DIST / "script.js")

    index_cards = []
    for idx, post in enumerate(posts):
        hero = f'<img src="{html.escape(post["hero"])}" alt="" loading="lazy">' if post["hero"] else ""
        tags = "".join(f"<span>{html.escape(tag)}</span>" for tag in post["categories"])
        index_cards.append(
            f"""<article class="post-card" style="--delay:{idx * 80}ms">
  <a class="media" href="posts/{post['slug']}.html">{hero}</a>
  <div class="card-body">
    <div class="meta"><a href="{post['author_url']}">{html.escape(post['author'])}</a><span>{post['display_date']}</span></div>
    <h2><a href="posts/{post['slug']}.html">{html.escape(post['title'])}</a></h2>
    <p>{html.escape(post['excerpt'])}</p>
    <div class="tags">{tags}</div>
  </div>
</article>"""
        )

    index_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tweeq Engineering Archive</title>
  <meta name="description" content="A preserved local archive of the Tweeq Engineering Medium publication.">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-hero">
    <nav>
      <a class="brand" href="./">Tweeq Engineering</a>
      <a href="https://engineering.tweeq.sa/feed">RSS Source</a>
    </nav>
    <div class="hero-grid">
      <div>
        <p class="eyebrow">Preserved engineering notes</p>
        <h1>Tweeq Engineering Archive</h1>
        <p class="lede">A local, static mirror of the Tweeq Tech Blog with original post structure, images, author names, article links, and Medium profile links preserved.</p>
      </div>
      <div class="signal-panel" aria-label="Archive summary">
        <span>{len(posts)}</span>
        <p>posts archived from Medium RSS on {datetime.now(timezone.utc).strftime('%Y-%m-%d')} UTC</p>
      </div>
    </div>
  </header>
  <main class="archive-grid">
    {''.join(index_cards)}
  </main>
  <footer>
    <p>Original publication: <a href="https://engineering.tweeq.sa/">engineering.tweeq.sa</a>. This archive keeps outbound links intact for attribution and further reading.</p>
  </footer>
  <script src="script.js"></script>
</body>
</html>
"""
    (DIST / "index.html").write_text(index_html, encoding="utf-8")

    for post in posts:
        tags = "".join(f"<span>{html.escape(tag)}</span>" for tag in post["categories"])
        body = f"""<header class="article-top">
  <nav>
    <a class="brand" href="../index.html">Tweeq Engineering</a>
    <a href="{post['original_url']}">Original Medium Post</a>
  </nav>
  <div class="article-heading">
    <p class="eyebrow">{post['display_date']}</p>
    <h1>{html.escape(post['title'])}</h1>
    <p class="byline">By <a href="{post['author_url']}">{html.escape(post['author'])}</a></p>
    <div class="tags">{tags}</div>
  </div>
</header>
<main class="article-wrap">
  <article class="article-content">
    {post['content']}
  </article>
</main>
<footer>
  <p>Archived from <a href="{post['original_url']}">{html.escape(post['original_url'])}</a>.</p>
</footer>"""
        (POSTS / f"{post['slug']}.html").write_text(
            page_shell(f"{post['title']} - Tweeq Engineering Archive", body, post["excerpt"]),
            encoding="utf-8",
        )


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    posts = read_feed()
    posts = localize_assets(posts)
    build_site(posts)
    print(f"Archived {len(posts)} posts into {DIST}")


if __name__ == "__main__":
    main()
