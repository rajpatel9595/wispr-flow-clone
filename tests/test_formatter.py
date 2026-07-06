from flow.formatter import _basic, apply_commands, format_text


def test_basic_removes_fillers_and_punctuates():
    assert _basic("um so this is uh a test") == "So this is a test."


def test_basic_capitalizes_and_keeps_existing_punctuation():
    assert _basic("hello world!") == "Hello world!"


def test_empty_passthrough():
    assert format_text("") == ""


def test_unknown_mode_falls_back_to_basic():
    assert format_text("hello there", mode="nonsense") == "Hello there."


def test_casual_tone_no_trailing_period_no_forced_cap():
    assert format_text("sounds good see you then", tone="casual") == "sounds good see you then"


def test_code_tone_verbatim():
    assert format_text("git commit dash m fix", tone="code") == "git commit dash m fix"


def test_spoken_punctuation_commands():
    assert apply_commands("hello comma world period") == "hello, world."


def test_new_line_and_paragraph():
    out = apply_commands("first item new line second item new paragraph done")
    assert out == "first item\nsecond item\n\ndone"


def test_scratch_that_discards_earlier_text():
    assert apply_commands("send it tomorrow scratch that send it today") == "send it today"


def test_scratch_that_everything():
    assert format_text("never mind scratch that") == ""
