# Standard Operating Procedures (SOP)

## Development Workflow
1. **Branching**: Each feature or task runs in its own branch (e.g. `feat/`, `chore/`, `fix/`).
2. **Conventional Commits**: Commit messages follow standard conventional format (`type(scope): summary`).
3. **Environment**:
   - Backend managed via `uv`.
   - Frontend managed via `npm`.
4. **Local Quality Gates**:
   - Run `make check` locally prior to pushing or raising PRs.
   - Run `npm run lint && npm run typecheck && npm run test` inside `frontend/`.

## PR & Code Review Standards
- Ensure all CI workflows (`quality`, `secrets`, `frontend`) are green.
- Verify missing data is handled as `None` (never `0` or `NaN` in models).
- Confirm zero secret leakage and compliance with `docs/AGENT_RULES.md`.
