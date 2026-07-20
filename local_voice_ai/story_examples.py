"""Reference children's stories the agent draws on for tone/style, so a
small local LLM doesn't default to flat, repetitive storytelling. See
story_examples.md (repo root) for the format and how to add your own —
bind-mounted into the container (see docker-compose.yml) so edits take
effect on the next session, no rebuild needed.
"""

from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass
from pathlib import Path

_PATH = Path(os.getenv("STORY_EXAMPLES_PATH", "/app/story_examples.md"))
_CATEGORY_RE = re.compile(r"^### (.+)$", re.MULTILINE)
_STORY_RE = re.compile(r"^## (.+?)(?:\s*\[(\w+)\])?\s*$", re.MULTILINE)


@dataclass
class StoryExample:
    category: str
    title: str
    language: str  # "en" | "te" | "mr"
    body: str


def load_story_examples() -> list[StoryExample]:
    if not _PATH.is_file():
        return []
    text = _PATH.read_text()

    category_starts = [(m.start(), m.group(1).strip()) for m in _CATEGORY_RE.finditer(text)]
    if not category_starts:
        return []

    def category_for(pos: int) -> str:
        current = category_starts[0][1]
        for start, name in category_starts:
            if start > pos:
                break
            current = name
        return current

    stories: list[StoryExample] = []
    story_matches = list(_STORY_RE.finditer(text))
    for i, m in enumerate(story_matches):
        title = m.group(1).strip()
        language = (m.group(2) or "en").lower()
        start = m.end()
        end = story_matches[i + 1].start() if i + 1 < len(story_matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        stories.append(
            StoryExample(category=category_for(m.start()), title=title, language=language, body=body)
        )
    return stories


def sample_story_examples(language: str = "en", max_categories: int = 4) -> list[StoryExample]:
    """One example per category (preferring the session's language, falling
    back to English), so the agent can offer a representative pick from
    every category without the prompt growing without bound as more stories
    are added. Category order is randomized each call for variety."""
    stories = load_story_examples()
    if not stories:
        return []

    by_category: dict[str, list[StoryExample]] = {}
    for story in stories:
        by_category.setdefault(story.category, []).append(story)

    categories = list(by_category)
    random.shuffle(categories)

    picked: list[StoryExample] = []
    for category in categories[:max_categories]:
        candidates = by_category[category]
        in_language = [s for s in candidates if s.language == language]
        pool = in_language or candidates
        picked.append(random.choice(pool))
    return picked
