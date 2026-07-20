"""Deterministic punctuation/symbol -> SSML translator for native-app
text-to-speech (Android `TextToSpeech`). Pure string transforms, no LLM or
device dependency — always produces valid SSML, even from plain prose that
uses none of the symbols below. The LLM is separately taught (see
`_SHARED_RULES` in characters.py) to use these symbols deliberately, but
this module is the safety net that guarantees correct output either way.

See docs/client-side-voice-plan.md for the full design rationale. Symbol
table:

    .        sentence end            -> 350ms break
    ,        short breath            -> 150ms break
    ...      dramatic pause          -> 800ms break
    --       short interruption      -> 250ms break, inline
    !        excitement              -> raised pitch/rate around the sentence
    ?        question                -> raised pitch around the sentence
    *word*   deliberate emphasis     -> <emphasis level="strong">
    sooooo   stretched spelling      -> collapsed spelling + slow prosody
             (any letter repeated 3+ times in a row)
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

_SENTENCE_SPLIT_RE = re.compile(r"(\.\.\.|[.!?])(\s+|$)")
_STRETCHED_RE = re.compile(r"\b(\w*?)(\w)\2{2,}(\w*)\b")
_EMPHASIS_RE = re.compile(r"\*(\S(?:[^*]*\S)?)\*")
_COLLAPSE_RE = re.compile(r"(\w)\1{2,}")

_BREAK_MS = {".": 350, "!": 350, "?": 350, "...": 800}


def _apply_stretch(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        normalized = _COLLAPSE_RE.sub(r"\1", m.group(0))
        return f'<prosody rate="70%">{normalized}</prosody>'

    return _STRETCHED_RE.sub(repl, text)


def _apply_emphasis(text: str) -> str:
    return _EMPHASIS_RE.sub(
        lambda m: f'<emphasis level="strong">{m.group(1)}</emphasis>', text
    )


def _apply_dash_pause(text: str) -> str:
    return text.replace("--", ' <break time="250ms"/> ')


def _process_segment(segment: str) -> str:
    """Word-level markup, applied to one sentence's (already-escaped) text."""
    segment = segment.replace(",", ',<break time="150ms"/>')
    segment = _apply_dash_pause(segment)
    segment = _apply_stretch(segment)
    segment = _apply_emphasis(segment)
    return segment


def _wrap_sentence(body: str, ending: str) -> str:
    if ending == "!":
        return f'<prosody pitch="+15%" rate="110%">{body}</prosody>'
    if ending == "?":
        return f'<prosody pitch="+10%">{body}</prosody>'
    return body


def text_to_ssml(text: str) -> str:
    """Translate agent reply text into SSML for Android TextToSpeech.

    The literal terminal punctuation (.!?) is not included in the output —
    its pause is expressed as an explicit <break> instead, so timing is
    precise rather than stacking an engine's own punctuation-driven pause
    on top of ours.
    """
    text = text.strip()
    if not text:
        return "<speak></speak>"

    parts: list[str] = []
    pos = 0
    for m in _SENTENCE_SPLIT_RE.finditer(text):
        ending = m.group(1)
        sentence = text[pos : m.start()].strip()
        pos = m.end()
        if not sentence:
            continue
        sentence = _process_segment(escape(sentence))
        wrapped = _wrap_sentence(sentence, ending)
        parts.append(f'{wrapped}<break time="{_BREAK_MS[ending]}ms"/>')

    remainder = text[pos:].strip()
    if remainder:
        parts.append(_process_segment(escape(remainder)))

    return "<speak>" + " ".join(parts) + "</speak>"
