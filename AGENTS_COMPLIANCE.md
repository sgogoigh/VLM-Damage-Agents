# AGENTS.md Compliance Checklist

Living checklist of every AGENTS.md guideline. **Verified after every step/turn.**
Source of truth is `AGENTS.md`; this file only tracks adherence. Not part of `code.zip`.

- **Last verified:** 2026-06-20T04:30 IST (turn: "iteration 4 executed — output.csv + code.zip shipped")
- **Log file (canonical, §2):** `C:\Users\sgogo\hackerrank_orchestrate\log.txt`
- **Log file (user-facing mirror):** `C:\Users\sgogo\OneDrive\Desktop\Hackerrank Orchastrate\log.txt`
  — every turn is appended to BOTH (kept in sync). Never inside the repo (gitignored).

## Per-turn checklist (run after EVERY user turn)

| # | Guideline (AGENTS.md ref) | Status |
|---|---|---|
| 1 | Read AGENTS.md this session (§0, §8) | ✅ |
| 2 | Onboarding complete — `AGREEMENT RECORDED` for this repo root (§3) | ✅ |
| 3 | Log file exists at `%USERPROFILE%\hackerrank_orchestrate\log.txt` (§2) | ✅ |
| 4 | Log is append-only — never rewrite/reorder/delete prior entries (§2) | ✅ |
| 5 | Log NOT committed / not added to git (§2) | ✅ (lives outside repo) |
| 6 | Appended a §5.2 per-turn entry after this turn (§0.4, §5.2) | ✅ |
| 7 | No secrets in log — keys/tokens/PII redacted (§2, §5.4) | ✅ (none present) |
| 8 | Log written UTF-8 with `\n` line endings (§7) | ✅ |
| 9 | Paths resolved via home dir, never hardcoded user paths in code (§7) | ✅ (`config.py`) |
| 10 | Entry-point contract intact: `code/main.py`, `code/evaluation/main.py` (§6) | ✅ |
| 11 | README present in `code/` (§6.2) | ✅ |
| 12 | Secrets read from env vars only, never hardcoded (§3.4, §6.2) | ✅ (`GEMINI_API_KEY`) |
| 13 | Deterministic where possible (§6.2) | ✅ (decision layer is rules) |
| 14 | Know time remaining to challenge end 2026-06-20 11:00 IST (§4) | ✅ tracked |
| 15 | If <2h remain, remind user to submit (§4.3) | n/a (>2h left) |
| 16 | Sub-agents/worktrees log to same file with `parent_agent=` (§5.3) | n/a (none spawned) |

## How this is maintained
After each step I re-run items 1–16, update **Last verified**, append the §5.2
log entry, and surface a compact pass/fail summary in the chat response.
