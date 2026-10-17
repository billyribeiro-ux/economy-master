# Economics & Finance — Mastery Library

A dependency-free HTML textbook and curriculum. All text is original instructional synthesis. Edition 0.1 is a growing working manuscript governed by `PRODUCTION_PLAN.md`, not a university credential or a replacement for supervised doctoral research.

## Read

Open `dist/index.html` directly in a browser. Every chapter, search, and the print edition works offline. The reading list links require internet access.

Alternatively, download and extract `economics-finance-mastery-offline.zip`, then open `mastery-library/index.html`.

## Repository snapshot

This repository preserves the local `book/` Git history, with that directory's contents at the repository root. It includes manuscripts, generated HTML, project data and code, sources, review records, production drafts, and the offline edition. `STATUS.json` and `content/curriculum.json` distinguish accepted material from unfinished work; uploading a snapshot does not mean the entire library is complete.

The enclosing workspace's `MASTER_PLAN.md` and `WORKSPACE_AGENTS.md` are included for recovery. Temporary downloaded reference documents and machine caches are excluded; source links and retained review evidence remain in the project.

## Rebuild

Run `python3 scripts/build.py` from this directory. Run `python3 scripts/verify.py` to check internal links, chapter structure, source references, and worked-example arithmetic. No packages are required.

## Structure

- `content/`: editable volume manuscripts and curriculum metadata.
- `assets/`: shared typography, navigation, and search.
- `scripts/`: standard-library build and verification tools.
- `dist/`: generated, ready-to-read HTML edition.

## Editorial standard

Every chapter contains prerequisites, a capability objective, instruction, a worked example, exercises, solutions or evaluation criteria, and a route to further study. The distinction between compact core coverage and research-level depth stays explicit. A major edition requires independent subject-matter review, additional problems and proofs, and external assessment of research and teaching. The dated edition boundary is 6 October 2026; current laws, prices and product details are not asserted without dated verification.
