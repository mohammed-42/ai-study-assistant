Create a file AGENT_RULES.md in the project root with exactly these rules, then follow it for every task from now on:

- Do ONLY the task I give you. No extra work, no refactors, no new features.
- Never print or write secrets (keys, passwords, tokens, DB URLs, project ref).
- Save raw outputs to backend/logs/<step>.log. Reply in under 20 lines.
- "PASSED" needs a proof line from real output. Not run = NOT RUN.
- Max 2 fix attempts per problem. Never rerun a failing command more than 3 times; then write FAILED to backend/logs/RUN_STATUS.md and STOP.
- If any Gemini call returns 429 / ResourceExhausted: STOP everything, clean up, report. No retries.
- Live scripts delete ONLY what they created.
- No weakening or deleting tests (except one I name).
- After each task: append one line to backend/logs/RUN_STATUS.md, update only the affected rows in PROGRESS.md (statuses: LIVE-VERIFIED, UNIT-TESTED (mocked), NOT VERIFIED, NOT IMPLEMENTED), commit if the task passed, and make sure no env, sample or log file is staged.