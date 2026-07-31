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
- Keep the `Status` line current — `Approved — awaiting go-ahead`, `In progress`, `Executed`
  with its commit hash, or `Superseded` / `Abandoned` with the reason.
- Newest plan at the top, as in `changes.md`. Keep executed plans in the file rather than
  deleting them; where a plan and its outcome differed, that record is the useful part.
- A plan that changes during execution is amended in `plans.md`, not silently outgrown.

## Mandatory Change Log

- Before performing any request that will add, edit, delete, rename, move, generate, or otherwise modify project files or system behavior, read `changes.md` in full.
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
