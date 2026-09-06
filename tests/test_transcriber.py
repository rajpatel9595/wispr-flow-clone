"""Transcriber post-processing — pure logic, no mlx/model."""
from flow.config import Config
from flow.transcriber import DEFAULT_PARAKEET, _ParakeetBackend, digits, foreign_script


class TestForeignScript:
    def test_cyrillic_is_foreign(self):
        assert foreign_script("Привет, как дела")

    def test_greek_is_foreign(self):
        assert foreign_script("Καλημέρα σας")

    def test_english_is_not(self):
        assert not foreign_script("hello there, how are you")

    def test_accented_latin_is_not(self):
        assert not foreign_script("café naïve Straße résumé")

    def test_mostly_latin_with_a_stray_symbol_is_not(self):
        assert not foreign_script("send it to Дима by five")

    def test_empty_and_punctuation_only_are_not(self):
        assert not foreign_script("")
        assert not foreign_script("... 42 !")


class TestParakeetClean:
    """v3 auto-detected the wrong language on quiet English; never paste that."""

    def test_drops_non_latin_output_for_english(self, capsys):
        assert _ParakeetBackend().clean("Привет как дела") == ""
        assert "auto-detected another language" in capsys.readouterr().out

    def test_keeps_english_and_converts_numbers(self):
        assert _ParakeetBackend().clean("step three") == "step 3"


class TestDefaults:
    def test_default_model_is_english_only_v2(self):
        assert DEFAULT_PARAKEET.endswith("-v2")
        assert Config().parakeet_model == DEFAULT_PARAKEET


class TestDigits:
    def test_compound_tens(self):
        assert digits("twenty two years old") == "22 years old"

    def test_bare_number_word_left_in_prose(self):
        assert digits("no one knows") == "no one knows"
