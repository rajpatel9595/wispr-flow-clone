---
name: run-app
description: Restart/verify the always-on Flow Clone LaunchAgent and walk the manual smoke test. Use when asked to run, restart, launch, or manually verify the dictation app.
---

# Run & smoke-test Flow Clone

The app runs permanently as LaunchAgent `com.rajpatel.flowclone` — do NOT start a second instance with `python -m flow` (double-paste). To apply code/config changes:

1. `launchctl kickstart -k gui/501/com.rajpatel.flowclone`
2. Watch `~/Library/Logs/flowclone.log` until it prints `permissions OK` and `ready`. If it prints MISSING permissions: user must enable **python3.12** in System Settings → Privacy & Security → Accessibility + Input Monitoring, then kickstart again. Permissions are per-binary — if the venv python changed, they MUST be re-granted (remove stale entries with −, the app re-registers itself).
3. Smoke test (user performs): focus Notes.app → hold right Option → speak → release. Expect: Tink sound, black pill with voice-reactive bars, ⚙️ + Pop on release, text pasted <1.5 s, entry in menu bar History.
4. Feature checks: say "hello comma world period" (punctuation), "scratch that" (discard), "insert my email" (snippet), dictate in a terminal (verbatim tone — no added period).
5. Report release-to-paste latency and tone tag from the log line (`[App:tone]: text`).
