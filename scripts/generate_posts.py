from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "news"
POSTS_DIR = ROOT / "content" / "posts"
CACHE_DIR = ROOT / "cache"
TRANSLATE_CACHE_FILE = CACHE_DIR / "translate_cache.json"

LATIN_RE = re.compile(r"[A-Za-z]")


def slugify(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    return "".join(cleaned).strip("-") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def load_items() -> list[dict]:
    items: list[dict] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            items.extend(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            print(f"[warn] skip invalid json: {path}")
    return items


def toml_literal(value: object) -> str:
    if value is None:
        return '""'
    return json.dumps(value, ensure_ascii=False)


def cleanup_generated_posts() -> None:
    for pattern in ("*-ai-*.md", "*-gh-*.md"):
        for path in POSTS_DIR.glob(pattern):
            path.unlink(missing_ok=True)


def load_translate_cache() -> dict[str, str]:
    if TRANSLATE_CACHE_FILE.exists():
        try:
            return json.loads(TRANSLATE_CACHE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_translate_cache(cache: dict[str, str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    TRANSLATE_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def translate_to_zh(text: str, cache: dict[str, str]) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if not LATIN_RE.search(text):
        return text
    if text in cache:
        return cache[text]

    url = f"https://api.mymemory.translated.net/get?q={quote(text)}&langpair=en|zh-CN"
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    try:
        with urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        translated = ((payload.get("responseData") or {}).get("translatedText") or "").strip()
        if translated:
            cache[text] = translated
            return translated
    except Exception:
        pass

    return text


def localize_item(item: dict, cache: dict[str, str]) -> dict:
    localized = dict(item)
    item_type = localized.get("type")

    if item_type == "github_trending":
        owner = localized.get("repo_owner", "")
        repo = localized.get("repo_name", "")
        full_name = f"{owner}/{repo}".strip("/")
        desc_en = localized.get("description") or localized.get("summary") or ""
        desc_zh = translate_to_zh(desc_en, cache)

        localized["title"] = f"GitHub 热榜：{full_name}" if full_name else "GitHub 热榜项目"
        localized["summary"] = f"{full_name}：{desc_zh}" if full_name else desc_zh
        localized["content"] = (
            f"仓库：{full_name}\n"
            f"简介：{desc_zh}\n"
            f"主要语言：{localized.get('language') or '未知'}\n"
            f"累计 Star：{localized.get('stars', '未知')}\n"
            f"Fork：{localized.get('forks', '未知')}\n"
            f"今日新增 Star：{localized.get('stars_today', '未知')}"
        )
        localized["lang"] = "zh-CN"
        return localized

    title_zh = translate_to_zh(localized.get("title", ""), cache)
    summary_zh = translate_to_zh(localized.get("summary", ""), cache)
    content_zh = translate_to_zh(localized.get("content") or summary_zh, cache)

    localized["title"] = title_zh or localized.get("title", "")
    localized["summary"] = summary_zh or localized.get("summary", "")
    localized["content"] = content_zh or localized.get("content") or localized.get("summary", "")
    localized["lang"] = "zh-CN"
    return localized


def render_front_matter(item: dict, slug: str) -> str:
    tags = json.dumps(item.get("tags", []), ensure_ascii=False)
    category = "GitHub热榜" if item.get("type") == "github_trending" else "AI资讯"
    extra = ""
    if item.get("type") == "github_trending":
        extra = f"""
repoOwner = {toml_literal(item.get('repo_owner', ''))}
repoName = {toml_literal(item.get('repo_name', ''))}
language = {toml_literal(item.get('language'))}
stars = {toml_literal(item.get('stars'))}
forks = {toml_literal(item.get('forks'))}
starsToday = {toml_literal(item.get('stars_today'))}
period = {toml_literal(item.get('period', 'daily'))}
builtBy = {toml_literal(item.get('built_by', []))}"""
    return f"""+++
title = {json.dumps(item['title'], ensure_ascii=False)}
date = {json.dumps(item.get('published_at') or datetime.now(timezone.utc).isoformat())}
draft = false
slug = {json.dumps(slug, ensure_ascii=False)}
type = "posts"
layout = "post"
newsType = {json.dumps(item.get('type', 'ai_news'))}
summary = {json.dumps(item.get('summary', ''), ensure_ascii=False)}
description = {json.dumps(item.get('summary', ''), ensure_ascii=False)}
sourceName = {json.dumps(item.get('source_name', 'Unknown'), ensure_ascii=False)}
sourceUrl = {json.dumps(item.get('source_url', ''), ensure_ascii=False)}
author = {json.dumps(item.get('author', ''), ensure_ascii=False)}
tags = {tags}
categories = [{json.dumps(category, ensure_ascii=False)}]
externalId = {json.dumps(item.get('id', ''), ensure_ascii=False)}
{extra}
+++
"""


def render_markdown(item: dict) -> str:
    slug = slugify(item.get("id") or item.get("title", "post"))
    body_lines = [item.get("content") or item.get("summary") or "暂无正文", ""]
    if item.get("source_url"):
        body_lines.extend([f"原始链接：{item['source_url']}", ""])
    if item.get("tags"):
        body_lines.extend([f"标签：{', '.join(item['tags'])}", ""])
    return render_front_matter(item, slug) + "\n".join(body_lines)


def main() -> None:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_generated_posts()
    cache = load_translate_cache()
    items = [localize_item(item, cache) for item in load_items()]
    save_translate_cache(cache)

    for item in items:
        slug = slugify(item.get("id") or item.get("title", "post"))
        target = POSTS_DIR / f"{slug}.md"
        target.write_text(render_markdown(item), encoding="utf-8")
    print(f"generated {len(items)} markdown posts in {POSTS_DIR}")


if __name__ == "__main__":
    main()
