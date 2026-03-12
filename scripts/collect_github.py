from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "news"
CACHE_DIR = ROOT / "cache" / "feeds"

ARTICLE_PATTERN = re.compile(r"<article[^>]*class=\"[^\"]*Box-row[^\"]*\"[^>]*>(.*?)</article>", re.S)
REPO_PATTERN = re.compile(r'<h2[^>]*>.*?<a[^>]*href="/(?P<repo>[^"]+)"', re.S)
DESC_PATTERN = re.compile(r"<p[^>]*>(?P<text>.*?)</p>", re.S)
LANG_PATTERN = re.compile(r'<span[^>]*itemprop="programmingLanguage"[^>]*>(?P<value>.*?)</span>', re.S)
STAR_TODAY_PATTERN = re.compile(r"(?P<value>[\d,]+)\s+stars?\s+today", re.I)
BUILT_BY_PATTERN = re.compile(r'alt="@(?P<author>[^"]+)"')
COUNT_LINK_PATTERN = re.compile(r'href="/(?P<repo>[^\"]+?)/(?P<kind>stargazers|forks)"[^>]*>(?P<value>.*?)</a>', re.S)
TAG_PATTERN = re.compile(r"<[^>]+>")
SPACE_PATTERN = re.compile(r"\s+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def clean_html(value: str) -> str:
    text = unescape(TAG_PATTERN.sub(" ", value))
    return SPACE_PATTERN.sub(" ", text).strip()


def parse_count(raw: str) -> int | None:
    text = clean_html(raw).replace(",", "")
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def build_summary(language: str | None, stars_today: int | None, stars: int | None, forks: int | None, description: str) -> str:
    parts: list[str] = []
    if language:
        parts.append(f"语言：{language}")
    if stars_today is not None:
        parts.append(f"今日新增 {stars_today} Star")
    if stars is not None:
        parts.append(f"累计 {stars} Star")
    if forks is not None:
        parts.append(f"{forks} Fork")
    if description:
        parts.append(description)
    return "；".join(parts) or "GitHub Trending 热门项目。"


def parse_article(block: str, since: str) -> dict[str, Any] | None:
    repo_match = REPO_PATTERN.search(block)
    if not repo_match:
        return None

    repo_name = clean_html(repo_match.group("repo"))
    if "/" not in repo_name:
        return None

    owner, repository = repo_name.split("/", 1)
    repo_url = f"https://github.com/{repo_name}"

    desc_match = DESC_PATTERN.search(block)
    description = clean_html(desc_match.group("text")) if desc_match else ""

    language_match = LANG_PATTERN.search(block)
    language = clean_html(language_match.group("value")) if language_match else None

    counts: dict[str, int | None] = {"stargazers": None, "forks": None}
    for match in COUNT_LINK_PATTERN.finditer(block):
        if clean_html(match.group("repo")) != repo_name:
            continue
        counts[match.group("kind")] = parse_count(match.group("value"))

    today_match = STAR_TODAY_PATTERN.search(clean_html(block))
    stars_today = int(today_match.group("value").replace(",", "")) if today_match else None
    built_by = sorted(set(BUILT_BY_PATTERN.findall(block)))

    tags = ["GitHub", "Trending"]
    if language:
        tags.append(language)

    summary = build_summary(language, stars_today, counts["stargazers"], counts["forks"], description)
    content_lines = [
        summary,
        "",
        f"仓库：{repo_name}",
        f"周期：{since}",
    ]
    if description:
        content_lines.append(f"简介：{description}")
    if language:
        content_lines.append(f"主要语言：{language}")
    if counts["stargazers"] is not None:
        content_lines.append(f"累计 Star：{counts['stargazers']}")
    if counts["forks"] is not None:
        content_lines.append(f"Fork：{counts['forks']}")
    if stars_today is not None:
        content_lines.append(f"今日新增 Star：{stars_today}")
    if built_by:
        content_lines.append(f"贡献者：{', '.join(built_by[:6])}")

    now = utc_now()
    return {
        "id": f"{datetime.now().strftime('%Y-%m-%d')}-gh-{digest(repo_name, since)[:12]}",
        "type": "github_trending",
        "title": repo_name,
        "summary": summary,
        "content": "\n".join(content_lines),
        "source_name": "GitHub Trending",
        "source_url": repo_url,
        "author": owner,
        "tags": tags,
        "published_at": now,
        "collected_at": now,
        "lang": "en",
        "hash": digest(repo_url, since, summary),
        "repo_owner": owner,
        "repo_name": repository,
        "language": language,
        "stars": counts["stargazers"],
        "forks": counts["forks"],
        "stars_today": stars_today,
        "built_by": built_by,
        "period": since,
        "description": description,
    }


def fetch_trending(since: str = "daily") -> list[dict[str, Any]]:
    query = urlencode({"since": since})
    request = Request(
        f"https://github.com/trending?{query}",
        headers={"User-Agent": "cola-news-bot/0.2"},
    )
    with urlopen(request, timeout=20) as response:
        html = response.read().decode("utf-8", errors="ignore")

    items: list[dict[str, Any]] = []
    for block in ARTICLE_PATTERN.findall(html):
        item = parse_article(block, since)
        if item is not None:
            items.append(item)
    return items[:20]


def save_json(target: Path, payload: list[dict[str, Any]]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect GitHub trending repositories.")
    parser.add_argument("--output", default=str(DATA_DIR / "github_trending.json"))
    parser.add_argument("--since", choices=["daily", "weekly", "monthly"], default="daily")
    args = parser.parse_args()

    items = fetch_trending(args.since)
    output_path = Path(args.output)
    save_json(output_path, items)
    save_json(CACHE_DIR / f"github_trending_{args.since}.json", items)
    print(f"saved {len(items)} GitHub trending items to {output_path}")


if __name__ == "__main__":
    main()
