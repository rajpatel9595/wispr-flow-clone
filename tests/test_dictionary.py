import flow.dictionary as dictionary


def test_default_created(tmp_path, monkeypatch):
    monkeypatch.setattr(dictionary, "DICT_PATH", tmp_path / "d.json")
    d = dictionary.load()
    assert "words" in d and (tmp_path / "d.json").exists()


def test_initial_prompt_biases_words():
    assert "Raj" in dictionary.initial_prompt({"words": ["Raj", "uv"]})
    assert dictionary.initial_prompt({"words": []}) is None


def test_replacements_case_insensitive():
    d = {"words": [], "replacements": {"wisper": "Wispr"}, "snippets": {}}
    assert dictionary.apply("I love Wisper flow", d) == "I love Wispr flow"


def test_snippet_expansion():
    d = {"words": [], "replacements": {}, "snippets": {"my email": "a@b.com"}}
    assert dictionary.apply("reach me at insert my email.", d) == "reach me at a@b.com"


def test_tone_rules():
    from flow.context import tone_for

    assert tone_for("Slack") == "casual"
    assert tone_for("iTerm2") == "code"
    assert tone_for("Safari") == "default"
