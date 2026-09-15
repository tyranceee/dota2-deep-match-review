#!/usr/bin/env python3
"""Build the public Dota review index in upload-time order."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


def parse_value(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",")]
    return value.strip("\"'")


def read_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    match = re.search(r"\n---\n", text[4:])
    if not match:
        raise ValueError(f"{path}: unfinished YAML frontmatter")
    end = match.start() + 4
    metadata = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{path}: invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = parse_value(value)
    return metadata, text[end + 5 :]


def extract_summary(body: str) -> str:
    match = re.search(r"^# 一句话结论\s*$\n+(.+?)(?:\n\s*\n|\n# )", body, re.M)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def build_index(content_dir: Path) -> list[dict]:
    records = []
    seen_ids = set()
    required = ("match_id", "title", "hero", "result", "duration", "patch", "published_at")
    for path in sorted(content_dir.glob("*.md")):
        metadata, body = read_frontmatter(path)
        missing = [key for key in required if key not in metadata]
        if missing:
            raise ValueError(f"{path}: missing fields: {', '.join(missing)}")
        match_id = str(metadata["match_id"])
        if match_id in seen_ids:
            raise ValueError(f"duplicate match_id: {match_id}")
        seen_ids.add(match_id)
        published_at = str(metadata["published_at"])
        datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        tags = metadata.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        records.append(
            {
                "match_id": match_id,
                "title": str(metadata["title"]),
                "hero": str(metadata["hero"]),
                "result": str(metadata["result"]),
                "played_at": str(metadata.get("played_at", "")),
                "duration": str(metadata["duration"]),
                "patch": str(metadata["patch"]),
                "published_at": published_at,
                "tags": tags,
                "summary": extract_summary(body),
                "url": f"/dota/reviews/{match_id}/",
            }
        )
    return sorted(records, key=lambda item: item["published_at"], reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = build_index(args.content_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} reviews to {args.output}")


if __name__ == "__main__":
    main()
