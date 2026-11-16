import json
import os
import tempfile
import unittest

from overdrive.osk import app, keys, words


class Plan(unittest.TestCase):
    def test_plain_text_is_keys_with_shift_where_needed(self):
        self.assertEqual(keys.plan("aA1!"), [("key", 30, False), ("key", 30, True), ("key", 2, False), ("key", 2, True)])
        self.assertEqual(keys.plan(" \n"), [("key", 57, False), ("key", 28, False)])

    def test_what_the_layout_lacks_is_pasted_in_one_piece(self):
        self.assertEqual(keys.plan("caffè 😀👍!"), [("key", 46, False), ("key", 30, False), ("key", 33, False), ("key", 33, False),
                                                   ("paste", "è"), ("key", 57, False), ("paste", "😀👍"), ("key", 2, True)])

    def test_every_printable_ascii_character_has_a_key(self):
        for code in range(32, 127):
            self.assertIn(chr(code), keys.US, repr(chr(code)))

    def test_chord(self):
        self.assertEqual(keys.chord(("ctrl", "shift", "v")), [29, 42, 47])
        self.assertEqual(keys.chord(("alt", "tab")), [56, 15])
        with self.assertRaises(KeyError):
            keys.chord(("ctrl", "è"))


class FakeClipboard:
    def __init__(self, held="before"):
        self.held, self.log = held, []

    def get(self):
        return self.held

    def set(self, text, sensitive=False):
        self.held = text
        self.log.append((text, sensitive))


class Sending(unittest.TestCase):
    def keyboard(self):
        kb = keys.Keyboard(clipboard=FakeClipboard(), pause=lambda s: None)
        kb.sent = []
        kb.key = lambda code, down: kb.sent.append((code, down))
        return kb

    def test_shift_goes_down_around_the_key(self):
        kb = self.keyboard()
        kb.type("A")
        self.assertEqual(kb.sent, [(42, True), (30, True), (30, False), (42, False)])

    def test_latched_modifiers_wrap_every_key(self):
        kb = self.keyboard()
        kb.type("c", held=("ctrl",))
        self.assertEqual(kb.sent, [(29, True), (46, True), (46, False), (29, False)])

    def test_a_pasted_character_is_kept_out_of_the_history_and_the_clipboard_comes_back(self):
        kb = self.keyboard()
        kb.type("è")
        self.assertEqual(kb.clipboard.log, [("è", True), ("before", False)])
        self.assertEqual(kb.sent, [(29, True), (47, True), (47, False), (29, False)])
        self.assertEqual(kb.clipboard.held, "before")

    def test_a_history_entry_becomes_the_clipboard(self):
        kb = self.keyboard()
        kb.paste_kept("an address")
        self.assertEqual(kb.clipboard.held, "an address")


class Suggest(unittest.TestCase):
    def words(self, d):
        listed = os.path.join(d, "words")
        with open(listed, "w") as f:
            f.write("hello\nhelp\nhelmet\nHelen\nhe\nworld\n")
        return words.Words(os.path.join(d, "mine.json"), lists=(listed,))

    def test_own_words_first_then_the_list_short_ones_first(self):
        with tempfile.TemporaryDirectory() as d:
            w = self.words(d)
            self.assertEqual(w.suggest("he"), ["help", "hello", "helmet"])
            self.assertEqual(w.suggest("h"), [])
            for _ in range(2):
                w.learn("helmet")
            self.assertEqual(w.suggest("he")[0], "helmet")
            self.assertEqual(w.suggest("He")[0], "Helmet")
            w.save()
            with open(os.path.join(d, "mine.json")) as f:
                self.assertEqual(json.load(f), {"helmet": 2})
            self.assertEqual(words.Words(os.path.join(d, "mine.json"), lists=()).suggest("hel"), ["helmet"])

    def test_typing_follows_the_word(self):
        with tempfile.TemporaryDirectory() as d:
            t = words.Typing(self.words(d))
            self.assertTrue(t.sentence_start)
            t.text("h"), t.text("e")
            self.assertEqual(t.word, "he")
            self.assertEqual(t.suggestions(), ["help", "hello", "helmet"])
            self.assertEqual(t.pick("hello"), [("back", 2), ("text", "hello ")])
            self.assertEqual(t.word, "")
            # a second space after a word: a full stop, and a sentence starts
            self.assertEqual(t.text(" "), [("back", 1), ("text", ". ")])
            self.assertTrue(t.sentence_start)
            t.text("w")
            t.backspace()
            self.assertEqual(t.word, "")
            t.text("ok")
            t.forget()
            self.assertEqual((t.word, t.last_space), ("", False))

    def test_two_spaces_without_a_word_stay_two_spaces(self):
        with tempfile.TemporaryDirectory() as d:
            t = words.Typing(self.words(d))
            self.assertEqual(t.text(" ") + t.text(" "), [("text", " "), ("text", " ")])


class Privacy(unittest.TestCase):
    def test_nothing_is_learnt_unless_asked(self):
        self.assertFalse(app.DEFAULTS["learn"])
        w = words.Words(None, lists=())
        w.learning = False
        w.learn("hunterpassword")
        self.assertEqual(w.counts, {})
        w.learning = True
        w.learn("hunterpassword")
        self.assertEqual(w.counts, {"hunterpassword": 1})


class Layout(unittest.TestCase):
    def test_plasma_s_list_then_the_system_s(self):
        with tempfile.TemporaryDirectory() as d:
            rc = os.path.join(d, "kxkbrc")
            with open(rc, "w") as f:
                f.write("[Layout]\nLayoutList=it,us\nUse=true\n")
            self.assertEqual(app.system_layout(rc), "it")

            class Done:
                stdout = "   System Locale: LANG=en_US.UTF-8\n      X11 Layout: us\n"
            self.assertEqual(app.system_layout(os.path.join(d, "none"), run=lambda *a, **k: Done), "us")


class Terminals(unittest.TestCase):
    def test_by_window_class(self):
        for name in ("org.kde.konsole", "konsole", "kitty", "org.wezfurlong.wezterm", "Alacritty", "org.gnome.Ptyxis"):
            self.assertTrue(app.is_terminal(name), name)
        for name in ("org.kde.kwrite", "firefox", "", None, "org.kde.konsolepart.viewer"):
            self.assertFalse(app.is_terminal(name), name)


class StockKeyboard(unittest.TestCase):
    def test_ours_shown_switches_plasma_s_off_and_remembers(self):
        self.assertEqual(app.stock_action(True, True, False, False, 1, None), (0, False, 1))
        self.assertEqual(app.stock_action(True, True, False, False, 0, 1), (None, False, 1))

    def test_ours_hidden_gives_plasma_s_back(self):
        self.assertEqual(app.stock_action(False, False, False, False, 0, 1), (1, False, None))
        self.assertEqual(app.stock_action(False, False, False, False, 0, None), (None, False, None))   # it was off before us

    def test_a_touch_on_a_text_field_brings_ours_up_only_with_auto(self):
        self.assertEqual(app.stock_action(False, True, False, True, 1, None), (None, True, None))
        self.assertEqual(app.stock_action(False, False, False, True, 1, None), (None, False, None))

    def test_the_lock_screen_always_keeps_plasma_s(self):
        # ours was shown (Plasma's off): locking gives Plasma's back and never shows ours
        self.assertEqual(app.stock_action(True, True, True, False, 0, 1), (1, False, 1))
        # unlocked again, Plasma's already switched off by the image's guard: the mode to give back is still known
        self.assertEqual(app.stock_action(True, True, False, False, 0, 1), (None, False, 1))
        self.assertEqual(app.stock_action(False, True, False, False, 0, 1), (1, False, None))
        self.assertEqual(app.stock_action(False, True, True, True, 1, None), (None, False, None))
        self.assertEqual(app.stock_action(True, True, True, True, 1, None), (None, False, None))


class Settings(unittest.TestCase):
    def test_defaults_bad_values_and_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "osk.json")
            self.assertEqual(app.load_settings(path), app.DEFAULTS)
            app.save_settings(dict(app.DEFAULTS, floating=False, x=120, scale=9, opacity="thick"), path)
            got = app.load_settings(path)
            self.assertEqual((got["floating"], got["x"], got["scale"], got["opacity"]), (False, 120, 1.6, app.DEFAULTS["opacity"]))
            with open(path, "w") as f:
                f.write("not json")
            self.assertEqual(app.load_settings(path), app.DEFAULTS)


if __name__ == "__main__":
    unittest.main()
