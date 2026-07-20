"""Tests for the deterministic text->SSML translator used by native-app
text-to-speech. Pure string-transform tests — no device, no LLM, no server
needed, per docs/client-side-voice-plan.md."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from local_voice_ai.voice_modulation import text_to_ssml


class TestBasics:
    def test_empty_text_produces_empty_speak(self) -> None:
        assert text_to_ssml("") == "<speak></speak>"
        assert text_to_ssml("   ") == "<speak></speak>"

    def test_plain_sentence_gets_wrapped_and_broken(self) -> None:
        ssml = text_to_ssml("The fox ran fast.")
        assert ssml.startswith("<speak>")
        assert ssml.endswith("</speak>")
        assert "The fox ran fast" in ssml
        assert '<break time="350ms"/>' in ssml
        # Literal period is not carried through — timing comes from <break>.
        assert "fast." not in ssml

    def test_multiple_sentences_each_get_a_break(self) -> None:
        ssml = text_to_ssml("One. Two. Three.")
        assert ssml.count('<break time="350ms"/>') == 3

    def test_text_with_no_terminal_punctuation_still_included(self) -> None:
        ssml = text_to_ssml("just trailing off")
        assert "just trailing off" in ssml


class TestPauses:
    def test_comma_becomes_short_break(self) -> None:
        ssml = text_to_ssml("Wait, look at that.")
        assert 'Wait,<break time="150ms"/>' in ssml

    def test_ellipsis_becomes_long_break(self) -> None:
        ssml = text_to_ssml("And then... the dragon woke up.")
        assert '<break time="800ms"/>' in ssml
        # The ellipsis-ended clause shouldn't also get a 350ms break.
        assert ssml.count('<break time="800ms"/>') == 1

    def test_double_dash_becomes_inline_break(self) -> None:
        ssml = text_to_ssml("She stopped -- and listened.")
        assert '<break time="250ms"/>' in ssml
        assert "--" not in ssml


class TestEmphasisAndExcitement:
    def test_exclamation_wraps_in_raised_prosody(self) -> None:
        ssml = text_to_ssml("Ooh, look at that!")
        assert '<prosody pitch="+15%" rate="110%">' in ssml
        assert "look at that" in ssml

    def test_question_wraps_in_rising_prosody(self) -> None:
        ssml = text_to_ssml("What happens next?")
        assert '<prosody pitch="+10%">' in ssml

    def test_statement_gets_no_sentence_wrapper(self) -> None:
        ssml = text_to_ssml("The sun was warm.")
        assert "<prosody" not in ssml

    def test_starred_word_gets_strong_emphasis(self) -> None:
        ssml = text_to_ssml("It was a *huge* dragon.")
        assert '<emphasis level="strong">huge</emphasis>' in ssml
        assert "*" not in ssml


class TestStretchedSpelling:
    def test_stretched_word_collapsed_and_slowed(self) -> None:
        ssml = text_to_ssml("It was sooooo big.")
        assert '<prosody rate="70%">so</prosody>' in ssml
        assert "sooooo" not in ssml

    def test_stretched_word_with_suffix(self) -> None:
        ssml = text_to_ssml("It went waaaay up high.")
        assert '<prosody rate="70%">way</prosody>' in ssml

    def test_normal_double_letters_not_treated_as_stretched(self) -> None:
        # "book", "letter" etc. have at most 2 repeated letters in a row —
        # must not trigger the 3+-repeat stretch rule.
        ssml = text_to_ssml("She read a book about a letter.")
        assert "<prosody" not in ssml
        assert "book" in ssml and "letter" in ssml


class TestEscaping:
    def test_xml_special_characters_are_escaped(self) -> None:
        ssml = text_to_ssml("Tom & Jerry ran <fast>.")
        assert "&amp;" in ssml
        assert "&lt;fast&gt;" in ssml
        # Never emit unescaped raw text that would break XML parsing.
        assert "<fast>" not in ssml


class TestCombinations:
    def test_emphasis_inside_excited_sentence(self) -> None:
        ssml = text_to_ssml("That was *amazing*!")
        assert '<prosody pitch="+15%" rate="110%">' in ssml
        assert '<emphasis level="strong">amazing</emphasis>' in ssml

    def test_full_paragraph_produces_well_formed_speak_block(self) -> None:
        text = (
            "Once upon a time, there was a *tiny* mouse. "
            "She was sooooo brave! "
            "One day -- out of nowhere -- she found a map. "
            "Where did it lead...? "
        )
        ssml = text_to_ssml(text)
        assert ssml.startswith("<speak>")
        assert ssml.endswith("</speak>")
        assert ssml.count("<speak>") == 1
        assert ssml.count("</speak>") == 1


class TestWellFormedXml:
    """The real guarantee: Android's TTS engine will reject malformed SSML
    outright, so every case here is parsed with a real XML parser, not just
    string-matched — a mismatched tag would pass the string checks above but
    crash on-device."""

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "Hello.",
            "Wait, look!",
            "What...?",
            "It was *huge* and sooooo scary -- then it was fine.",
            "Tom & Jerry ran <fast> away, didn't they?",
            "*starts* and *ends* with emphasis*.",
            "...",
            "!!!",
            "No terminal punctuation at all",
        ],
    )
    def test_parses_as_valid_xml(self, text: str) -> None:
        ET.fromstring(text_to_ssml(text))
