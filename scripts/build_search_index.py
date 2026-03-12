from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "news"
SEARCH_INDEX = ROOT / "data" / "search" / "index.json"
STATIC_INDEX = ROOT / "static" / "data" / "search" / "index.json"


def slugify(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    return "".join(cleaned).strip("-") or "post"


def load_items() -> list[dict]:
    items: list[dict] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            items.extend(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            print(f"[warn] skip invalid json: {path}")
    return items


def to_search_doc(item: dict) -> dict:
    slug = slugify(item.get("id") or item.get("title", "post"))
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "summary": item.get("summary"),
        "source_name": item.get("source_name"),
        "tags": item.get("tags", []),
        "section": "GitHub 热榜" if item.get("type") == "github_trending" else "AI 资讯",
        "language": item.get("language"),
        "stars": item.get("stars"),
        "stars_today": item.get("stars_today"),
        "published_at": item.get("published_at"),
        "permalink": f"/posts/{slug}/",
    }


def main() -> None:
    docs = [to_search_doc(item) for item in load_items()]
    SEARCH_INDEX.parent.mkdir(parents=True, exist_ok=True)
    STATIC_INDEX.parent.mkdir(parents=True, exist_ok=True)
    SEARCH_INDEX.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    STATIC_INDEX.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated search index with {len(docs)} entries")


if __name__ == "__main__":
    main()
