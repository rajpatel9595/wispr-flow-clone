---
name: vocab
description: Add words, replacements, or snippets to the Flow Clone personal dictionary. Use when the user says Whisper misheard a word, wants a name/jargon recognized, or wants a voice snippet.
---

# Manage personal dictionary

File: `~/.flowclone_dict.json` — three sections:
- `words`: proper nouns/jargon to bias recognition (fed to Whisper initial_prompt). Add here first for any mishear.
- `replacements`: `{"mishear": "correct"}` forced fixes — use when biasing alone doesn't fix it (ask the user what Whisper actually output, use that exact string as the key).
- `snippets`: `{"phrase": "expansion"}` — spoken "insert <phrase>" expands.

Steps: read the JSON, add the entry (preserve existing), write back, then `launchctl kickstart -k gui/501/com.rajpatel.flowclone` (dictionary loads at startup). Confirm by having the user redictate the word.
