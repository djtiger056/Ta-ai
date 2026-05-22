import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.utils.text_splitter import split_text_by_sentences


def test_split_text_by_sentences_uses_spaces_for_long_english_text():
    text = "hello world this is a long message for segment sending test"

    segments = split_text_by_sentences(text, max_length=12, min_length=3)

    assert segments == [
        "hello world",
        "this is a",
        "long message",
        "for segment",
        "sending test",
    ]


def test_split_text_by_sentences_preserves_sentence_punctuation():
    text = "第一句。第二句！Third sentence?"

    segments = split_text_by_sentences(text, max_length=50, min_length=1)

    assert segments == ["第一句。", "第二句！", "Third sentence?"]
