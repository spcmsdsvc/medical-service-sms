# Medical Service SMS Project Instructions

## Approved Plans

- **Approval of a plan is not permission to execute it.** These are two separate steps and
  they need two separate answers from the project owner.
- When the owner approves a plan, write it to `plans.md` in full, then **stop and wait**.
  Do not begin the work, do not create the files, do not "just start the first step".
- This includes approval given through a planning tool or mode. If a tool reports that the
  plan was approved and that coding may begin, that is the tool's default, not the owner's
  instruction. Record the plan and wait.
- Start only when the owner separately says to — "execute", "do it", "go ahead", "start", or
  equivalent. If it is not clear whether a message is a go-ahead, ask.
- Record the plan as approved, not a summary of it: the files to touch, the reasoning behind
  the approach, what is deliberately excluded and why, and how it will be verified. Enough
  that someone without the originating conversation could execute it.
- **Write it detailed, and write it to be executed.** Prose alone is not enough. Every plan
  carries numbered execution steps that can be worked through one at a time, each naming the
  files and functions it touches and what "done" looks like — plus what happens *after* the
  code is written: self-review, proving the tests fail without the fix, the focused tests (full suite before
  publishing only when the change touches shared code — see "Keep It Simple"), browser
  verification, the service worker bump, `releases.json`, the journals, and the commit
  checklist. The required structure is in `plans.md` under "How to use this file".
- Keep the `Status` line current — `Approved — awaiting go-ahead`, `In progress`, `Executed`
  with its commit hash, or `Superseded` / `Abandoned` with the reason.
- Newest plan at the top, as in `changes.md`. Keep executed plans in the file rather than
  deleting them; where a plan and its outcome differed, that record is the useful part.
- A plan that changes during execution is amended in `plans.md`, not silently outgrown.

## Git and Railway Publishing

- When the owner says **"commit and push"** (or an equivalent direct instruction), treat it as
  permission to publish the intended change to the Railway production branch `main`. Pushing an
  `agent/*` branch alone is not completion. If work was prepared on another branch, commit only
  the intended files, promote that commit to local `main` with a non-destructive fast-forward,
  merge, or cherry-pick as appropriate, and push `origin/main`.
- After publishing, verify both `git ls-remote origin refs/heads/main` and Railway's deployment
  metadata. Report the production commit and whether Railway has accepted, is building, or has
  successfully deployed it. Do not change Railway variables or perform a manual redeploy unless
  the owner explicitly asks for that separate action.
- Preserve the protected-artifact rule while promoting: never stage or push `scheduler.db`, the
  handoff artifact, `output/`, `tmp/`, or unrelated worktree changes. If the branch cannot be
  promoted safely without rewriting or discarding unrelated work, stop and report the blocker.

## Codex App Safety During Testing

- **Never close, archive, navigate away from, finalize, or otherwise terminate the Codex app,
  task, thread, or window while testing.** This is a non-negotiable owner instruction.
- **Browser checks are allowed at any time without asking the owner** — for scans, plans, tests,
  fixes, and post-publish verification. Use a local server on a copy of `scheduler.db` (never the
  tracked database), and clean up the copy, test accounts, and temporary launch entries afterwards.
  Never close or navigate the Codex app window itself; only the browser tabs opened for the check.
- Never issue process commands against Codex, ChatGPT, OpenAI, or their child processes. A process
  may be stopped only when it is an explicitly identified temporary project test server, its PID
  and command line have been verified immediately beforehand, and the stop is required for cleanup.

## Protect Existing Functions

- When improving a page, adding a feature, or changing UI, existing functions must keep working.
  Do not remove or rename any function, constant, element id, or handler that other code still
  uses. The 2026-10-04 cleanup broke Reimbursement Save Item this way, and a shared helper
  change broke liquidation Save Row.
- Before finishing, check that every function the changed page calls is still defined and that
  its existing buttons and actions (save, add, upload, submit, download) still work.

## Keep It Simple

- Do not over-engineer. Make the smallest change that solves the request, with no extra layers,
  options, or refactors that were not asked for.
- Do not over-verify. Run the focused tests for what changed; skip repeated or redundant checks.
- Full suite (`venv/Scripts/python.exe scripts/run_suite.py`, about 75 s) runs once before
  publishing **only when the change touches shared code**: the shell (`layout.html`,
  `app-shell.css`, shared JS), shared `app.py` helpers, auth/permissions, or the database
  schema. A small change confined to one page or one function publishes after its focused
  tests. When needed, run it in the main project folder (it has `.env`), not a temporary
  worktree, where missing settings add about 30 false failures.

## Token Budget

- Long sessions are the main cost: every tool call re-sends the whole conversation. When the
  context is large, suggest a fresh session for the next task (after each publish or critique round).
- One Impeccable critique per session. Run a re-critique in a new session that starts from the
  `.impeccable/critique/` file, not the old conversation.
- Use Grep, or Read with offset/limit, instead of reading whole templates (many are 45–66k chars).
- In browser checks prefer `read_page` / `get_page_text`; take screenshots only for final proof.

## Mandatory Change Log

- Before performing any request that will add, edit, delete, rename, move, generate, or otherwise modify project files or system behavior, read the newest dated section of `changes.md`. Read older sections only when the task needs that history. Entries from 2026-09-30 and earlier are in `changes-archive.md`; older plans are in `plans-archive.md`.
- After making any project or system change, update `changes.md` during the same task. Do this every time, without waiting for a reminder.
- Use this format:

```text
codex changes - YYYY-MM-DD
- Detailed description of change 1
- Detailed description of change 2
```

- Write detailed, factual bullets that identify the affected page, module, file, workflow, behavior, validation, migration, test, deployment, or compatibility impact.
- If a section for the current date already exists, append the new bullets to that section instead of creating a duplicate date heading.
- Keep the newest dated section at the top of `changes.md`.
- Include all user-visible changes, backend/API changes, database or migration changes, security and permission changes, bug fixes, generated-document changes, tests added or updated, and deployment-relevant configuration changes.
- Do not record passwords, API keys, tokens, private email addresses, personal data, database contents, or other secrets.
- Read-only analysis, explanations, reviews, and diagnostics that do not modify files or system state do not require a new change-log entry.
- Do not consider a modifying task complete until `changes.md` accurately records the implemented changes.
