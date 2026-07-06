from flow.formatter import _basic, format_text


def test_basic_removes_fillers_and_punctuates():
    assert _basic("um so this is uh a test") == "So this is a test."


def test_basic_capitalizes_and_keeps_existing_punctuation():
    assert _basic("hello world!") == "Hello world!"


def test_empty_passthrough():
    assert format_text("") == ""


def test_unknown_mode_falls_back_to_basic():
    assert format_text("hello there", mode="nonsense") == "Hello there."
