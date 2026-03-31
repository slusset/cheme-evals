---
name: No worktrees - work on main
description: User prefers direct changes on main branch, not git worktrees
type: feedback
---

Don't use worktrees. Make changes directly on main and let user manage git.

**Why:** User cannot easily switch to worktree to test changes. Creates confusion about where code actually lives.

**How to apply:** Never use EnterWorktree. All edits go to /Users/tedslusser/PycharmProjects/cheme-evals/ directly.
