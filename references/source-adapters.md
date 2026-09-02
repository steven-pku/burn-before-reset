# Source Adapters

## Common rules

- Roots must be absolute, exist, resolve inside the configured allowlist, and not be symlinks escaping it.
- Index metadata first. Read at most the configured byte cap per text file.
- Never copy full transcripts into reports. Record source type, stable local reference, timestamp, title, signal count, and short redacted snippets.
- Skip secret-like basenames and configured excluded path fragments before opening a file.

## Codex sessions

Expected source: user-approved subtrees under `CODEX_HOME/sessions` or archived sessions. Accept only JSONL files whose first object is structurally a `session_meta` record. Do not infer truth from `originator` spelling.

Extract only session id, timestamp, cwd, and bounded task/next-step signals. Do not read `auth.json`, config, shell snapshots, databases, caches, or logs unless separately approved for a specific audit.

## Claude sessions

Expected source: explicit project subtrees under the local Claude configuration directory. Accept only JSONL files whose first record is a typed entry bound to a session — a string `type` plus a `sessionId`, `cwd` or `uuid`. That shape is observed on real transcripts, not published as a contract; a data export or log that merely ends in `.jsonl` is skipped. Treat transcripts as private plaintext. Extract bounded task signals only; never publish or commit transcript content.

## Obsidian and Markdown

Index title, frontmatter, modification time, checkbox/TODO markers, and bounded snippets. Preserve Source/Research immutability and the target Vault's local AGENTS rules. Default output stays outside the Vault.

## Git repositories

Read repository metadata and status with a timeout. Candidate signals include TODO/FIXME, failing tests supplied by the user, doc drift, and uncommitted work. Planner never stages, commits, branches, or edits the repository.

## Known enforcement boundary

The deterministic indexer enforces these rules itself. A model Worker is a separate process and relies on the Codex sandbox plus prompt/rules. Because the standard sandbox is not a narrow read allowlist, execution against sensitive roots remains unsupported in v0.1.
