# Economics & Finance — Mastery Library

A dependency-free HTML textbook and curriculum. All text is original instructional synthesis. Edition 1.0 contains all 216 chapters, 18 volume assessment/project packages and eight cross-volume examinations or portfolios, governed by `PRODUCTION_PLAN.md`. It is not a university credential or a replacement for supervised doctoral research.

## Read

Open `dist/index.html` directly in a browser. Every chapter, search, and the print edition works offline. The reading list links require internet access.

Alternatively, download and extract `economics-finance-mastery-offline.zip`, then open `mastery-library/index.html`.

## Repository snapshot

This repository preserves the local `book/` Git history, with that directory's contents at the repository root. It includes manuscripts, generated HTML, project data and code, sources, review records, production drafts, and the offline edition. `STATUS.json` and `content/curriculum.json` record editorial acceptance and the latest actual validation and deployment.

The enclosing workspace's `MASTER_PLAN.md` and `WORKSPACE_AGENTS.md` are included for recovery. Temporary downloaded reference documents and machine caches are excluded; source links and retained review evidence remain in the project.

## Rebuild

Run `python3 scripts/build.py` from this directory. Run `python3 scripts/verify.py` to check internal links, chapter structure, source references, and worked-example arithmetic. No packages are required.

## Structure

- `content/`: editable volume manuscripts and curriculum metadata.
- `assets/`: shared typography, navigation, and search.
- `scripts/`: standard-library build and verification tools.
- `dist/`: generated, ready-to-read HTML edition.

## Editorial standard

Every chapter contains prerequisites, a capability objective, instruction, a worked example, exercises, solutions or evaluation criteria, and a route to further study. The distinction between compact core coverage and research-level depth stays explicit. Internal author, distinct agent peer and coordinating reviews are recorded with their scope; they do not substitute for qualified independent human assessment of learner research, teaching and leadership. The dated edition boundary is 6 October 2026; current laws, prices and product details are not asserted without dated verification.
