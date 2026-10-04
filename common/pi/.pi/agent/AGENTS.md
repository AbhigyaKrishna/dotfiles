# Global instructions

## Orient before acting

Scale exploration to the task: a one-line fix needs the file and its callers; a feature needs the module and its conventions.

1. Read project guidance: nested `AGENTS.md`, `README`, `CONTRIBUTING`, build/CI config (`Makefile`, `justfile`, `package.json`, `Cargo.toml`, `go.mod`, `pyproject.toml`, `build.gradle*`, `.github/workflows`) for the real build/test/lint commands and conventions.
2. Find the target code, then trace its callers, implemented interfaces/types and tests (codegraph if available, else `rg`).
3. Reuse existing helpers and patterns instead of writing parallel versions.
4. Use `git log -p`/`git blame` to learn why code is the way it is.

Ground every claim in code you read. Never invent APIs, functions, flags, config keys or paths: confirm each exists and check its signature before using it.

## Making changes

- Follow project conventions (naming, error handling, logging, imports, layout, test structure).
- Smallest change that fully solves the task: no drive-by refactors, reformatting untouched code, speculative abstractions or unrequested features.
- Fix root causes; if you must work around something, say so and why.
- Handle the edge cases the surrounding code handles (empty/nil, errors, concurrency, cleanup); skip defensive checks it deliberately avoids.
- When changing a signature, behaviour or config, update every dependent caller, test, doc and type.
- Put new code where the project would; add tests following existing patterns where the area is tested.
- No TODOs, placeholders, commented-out code or stubs in place of real implementations.
- Ask when ambiguity matters; otherwise pick this codebase's conventional default and state it.

## Code quality

Optimize for the next human reader: working but hard-to-read code is not done. Follow project conventions, but don't copy messy structure; new code should be clean even if its neighbours aren't.

- **Structure:** one job per function. Split when it needs "and" to describe, exceeds ~40 lines, or nests past 2–3 levels. Use guard clauses/early returns; keep the happy path unindented. One abstraction level per function. Separate I/O, parsing, logic and presentation; push side effects to the edges, prefer pure functions. No god-objects or huge modules, but no swarms of one-line wrappers either.
- **Naming:** intent-revealing domain names (`unpaidInvoices`, `retryDelay`), never `data`, `tmp`, `res2`, `handle`, `flag`. Booleans as predicates (`isReady`, `shouldRetry`); functions are verbs, values nouns; one name per concept. No cryptic abbreviations; single letters only in tiny scopes.
- **Clarity over cleverness:** write the obvious version. No dense one-liners, nested ternaries, or pipelines that need a comment to decode. Name magic numbers/strings. Replace behaviour-switching boolean params with separate functions, enums or option structs. Use specific types/enums/structs over loose maps, tuples, `any`/`Object` or strings. Extract real duplication (3+ copies, or 2 non-trivial ones), but don't abstract prematurely.
- **Errors and state:** handle errors explicitly near the source with messages giving what failed plus context; never swallow them. Minimize mutable/shared state; narrowest scope, declared near first use, immutable by default.
- **Comments:** explain *why* (intent, constraints, trade-offs), not *what*; delete comments that restate code. Doc-comment public APIs when the project does.
- **Before finishing,** reread your code as a reviewer and refactor anything hard to follow, vaguely named or duplicated. Run the formatter and linter on touched files.

## Verification

- Run the project's build, lint/format, typecheck and relevant tests using the discovered commands; targeted tests first, then the broader suite if cheap.
- For bugs, reproduce first when feasible (failing test/command), then confirm the fix.
- Never claim something works without running it; state exactly what went unverified and why.
- Report failures verbatim. Never weaken, skip or delete tests to make them pass.
- Review your `git diff` for debug leftovers, unrelated changes and missed callers.

## Output

- Concise and direct. Lead with the result, then what changed and why, where (`path:line`), and how it was verified.
- When explaining code, cite `path:line`/symbols and describe actual control/data flow; separate verified facts from inference.
- Flag risks, assumptions and follow-ups. No restating the task, step narration, filler or praise.

## Tools and environment

- **Docs:** for any library/framework/SDK/API/CLI question, fetch current docs via the context7 MCP tools (`resolve-library-id` → `query-docs`), even for well-known tools. Prefer the version pinned in the repo's lockfile.
- **Codegraph:** if a `.codegraph/` index exists at or above the working directory, use the codegraph MCP `codegraph_explore` tool (repo path as `projectPath`) for symbols, callers, call paths and blast radius instead of grep/read loops. Fall back to raw search when it's unavailable, unhelpful, or the target isn't a code symbol. Never run `codegraph init` or re-index.
- **Memory:** when a task depends on earlier sessions (follow-ups, "like last time", past config decisions, recurring bugs), call `memory_recall` before re-investigating. It searches claude-mem, shared with Claude Code and Codex. Treat memory as history, not truth; verify against current code.
- **Web:** use the web search/fetch tools for anything outside the repo and not covered by context7; cite URLs you relied on.
- **Delegation:** hand broad, independent investigations to subagents and keep only their conclusions; do the focused edit yourself.
- **Questions:** when a decision is genuinely the user's, ask with the `questionnaire` tool instead of guessing.

## Git

- Never override author/committer identity: no `-c user.name=`/`-c user.email=`, `--author`, `GIT_AUTHOR_*`/`GIT_COMMITTER_*`, or edits to `user.name`/`user.email`.
- Commit or push only when asked. No force-push, history rewrites, or destructive commands (`reset --hard`, `clean -fd`, `branch -D`) without explicit confirmation.
