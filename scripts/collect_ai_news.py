from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "news"
CACHE_DIR = ROOT / "cache" / "feeds"
LOG_DIR = ROOT / "logs"


@dataclass
class FeedSource:
    name: str
    url: str
    tag: str


DEFAULT_SOURCES = [
    FeedSource("OpenAI Blog", "https://openai.com/blog/rss.xml", "OpenAI"),
    FeedSource("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "HuggingFace"),
    FeedSource("Google DeepMind Blog", "https://deepmind.google/blog/rss.xml", "DeepMind"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint(*parts: str) -> str:
    raw = "|".join(part.strip() for part in parts if part)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").split())


def parse_rss(source: FeedSource) -> Iterable[dict]:
    request = Request(
        source.url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = response.read()
    root = ET.fromstring(payload)
    for item in root.findall(".//item")[:12]:
        title = normalize_text(item.findtext("title"))
        link = normalize_text(item.findtext("link"))
        summary = normalize_text(item.findtext("description"))
        if not title or not link:
            continue
        slug = fingerprint(link, title)[:12]
        published_at = normalize_text(item.findtext("pubDate")) or utc_now()
        yield {
            "id": f"{datetime.now().strftime('%Y-%m-%d')}-ai-{slug}",
            "type": "ai_news",
            "title": title,
            "summary": summary,
            "content": summary,
            "source_name": source.name,
            "source_url": link,
            "author": source.name,
            "tags": [source.tag],
            "published_at": published_at,
            "collected_at": utc_now(),
            "lang": "zh-CN",
            "hash": fingerprint(link, title, summary),
        }


def dedupe(items: Iterable[dict]) -> list[dict]:
    unique: dict[str, dict] = {}
    for item in items:
        key = item["hash"]
        unique[key] = item
    return sorted(unique.values(), key=lambda entry: entry["published_at"], reverse=True)


def save_json(target: Path, payload: list[dict]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect AI news from configured RSS feeds.")
    parser.add_argument("--output", default=str(DATA_DIR / "ai_news.json"))
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    collected: list[dict] = []
    for source in DEFAULT_SOURCES:
        try:
            items = list(parse_rss(source))
            collected.extend(items)
            save_json(CACHE_DIR / f"{source.tag.lower()}.json", items)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] failed to collect {source.name}: {exc}")

    output_path = Path(args.output)
    save_json(output_path, dedupe(collected))
    print(f"saved {len(collected)} raw AI items to {output_path}")


if __name__ == "__main__":
    main()
