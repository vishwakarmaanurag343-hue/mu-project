# AlphaLens Standard Operating Procedures (SOP)

---

## 1. Local Setup

### Prerequisites
- **Python**: 3.11 or higher (managed via `uv`).
- **Node.js**: v20+ or v22+ LTS (npm v10+).
- **Package Managers**: [uv](https://github.com/astral-sh/uv) (Python) and `npm` (Frontend).
- **Git**: Installed with pre-commit support.

### Step-by-Step Initialization
```bash
# 1. Clone repository and initialize Python environment + pre-commit hooks
make setup

# 2. Configure local development environment
cp .env.example .env
# Edit .env: Ensure JWT_SECRET_KEY is at least 32 characters long.
# For local dev, dummy LLM keys can be left blank or filled with test tokens.

# 3. Initialize and build the frontend application
cd frontend
npm install
npm run build
cd ..

# 4. Start the backend service (Uvicorn on 127.0.0.1:8000 with auto-reload)
make api

# 5. In a separate terminal, launch the frontend dev server (Vite proxy to FastAPI)
make web
```
The application will be accessible at `http://localhost:5173` (Vite dev server proxying `/api` requests to `127.0.0.1:8000`) or directly at `http://127.0.0.1:8000` when serving `frontend/dist`.

---

## 2. Daily Workflow with the Coding Agent

All contributors and AI agents must follow this rigorous branch-per-task workflow:

```
[ New Task Received ]
         │
         ▼
[ Create Branch: feat/, fix/, docs/, chore/, test/ ]
         │
         ▼
[ Formulate Plan in Planning Mode ]
         │
         ▼
[ Plan Review & Human Approval ]
         │
         ▼
[ Implementation & Automated Verification (make check) ]
         │
         ▼
[ Commit with Conventional Commit Message ]
         │
         ▼
[ Pull Request with Automated CI Verification ]
```

### Protocol Steps
1. **Branch Creation**: Never commit directly to `main`. Create a feature or fix branch from an up-to-date `main`:
   ```bash
   git checkout main && git pull
   git checkout -b <prefix>/<brief-task-name>
   ```
   *Permitted branch prefixes*: `feat/`, `fix/`, `docs/`, `chore/`, `test/`.
2. **Planning First**: Formulate an explicit, step-by-step plan using the task template. Wait for explicit human reviewer approval before executing modifications.
3. **Rollback Commit**: Always create a clean git commit prior to launching complex agent tasks to establish an immediate rollback point.
4. **Execution & Strict Rules Compliance**: Follow all constraints defined in [AGENT_RULES.md](file:///c:/Users/vishw/Desktop/project/docs/AGENT_RULES.md). Never read `.env`, never disable tests, and never introduce unauthorized dependencies.
5. **Quality Verification**: Execute the full verification suite before concluding turns:
   ```bash
   make check
   cd frontend && npm run lint && npm run typecheck && npm run test && npm run size
   ```
6. **Pull Request Protocol**: Submit a PR summarizing changes, test evidence, and verification logs. Merge only after all automated CI checks pass and senior review approval is granted.

### Standard Task Planning Template
```markdown
### Task Plan: [Short Descriptive Title]

#### 1. Context & Objectives
- Summary of requirements and target outcomes.
- Referenced files and ADR constraints.

#### 2. Proposed Changes
- **Files to create/modify**:
  - `path/to/file.py`: description of changes.
- **Function signatures & data structures**:
  - `def function_name(param: Type) -> ReturnType:`

#### 3. Dependencies
- State whether new packages are needed (None / List with justification).

#### 4. Test Strategy
- Unit tests to create/update.
- Edge cases and security validation assertions.

#### 5. Verification Plan
- Specific commands to run (`make check`, frontend test suite).
```

---

## 3. Commit Messages (Conventional Commits)

All git commit messages must follow the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short description in imperative present tense>

[optional body explaining context and rationale]

[optional footer(s)]
```

### Approved Types & Examples
- `feat(reports)`: add Server-Sent Events streaming for verified LLM evidence
- `fix(auth)`: enforce token rotation and reuse detection on refresh endpoints
- `docs(threat-model)`: ground STRIDE analysis in Phase 1 codebase implementation
- `test(uploads)`: assert process parser timeout raises HTTP 422
- `refactor(db)`: decouple prediction logs from user table via UserPseudonym
- `chore(deps)`: update ruff to 0.8.0 and pin lockfile

---

## 4. Definition of Done (DoD) Checklist

A task is considered complete **only** when all items in this checklist are satisfied:

- [ ] **Type Annotations**: Python code is 100% typed; `mypy src` passes in strict mode without errors.
- [ ] **Documentation**: Every public module, class, and function has a clear docstring.
- [ ] **Unit & Integration Tests**: Comprehensive tests added; no live external network calls in automated tests (`@pytest.mark.live` used for real calls).
- [ ] **Test Coverage**: Pytest line coverage $\ge 80.0\%$ (`pytest -m "not live"` enforces `--cov-fail-under=80`).
- [ ] **Python Quality**: `ruff check .`, `ruff format --check .`, and `bandit -c pyproject.toml -r src` report zero violations.
- [ ] **Frontend Quality**: `npm run lint`, `npm run typecheck`, and `npm run test` pass with zero warnings.
- [ ] **Bundle Budget**: Initial gzipped frontend bundle is verified under $200\text{ KB}$ via `npm run size`.
- [ ] **Zero Secrets**: No tokens, API keys, or `.env` content committed or printed to terminal output.
- [ ] **Documentation Synchronization**: [ARCHITECTURE.md](file:///c:/Users/vishw/Desktop/project/docs/ARCHITECTURE.md), [THREAT_MODEL.md](file:///c:/Users/vishw/Desktop/project/docs/THREAT_MODEL.md), and relevant ADRs updated if application behavior or schemas changed.

---

## 5. Adding Dependencies

Adding external dependencies requires explicit review and justification.

### Backend Dependencies (`pyproject.toml`)
1. **Justify**: Document in the task plan why existing dependencies or Python standard library tools are insufficient.
2. **Evaluate**: Verify license compatibility (permissive MIT/Apache/BSD; avoid GPL in proprietary distribution) and active maintenance.
3. **Install**: Run `uv add "<package_name>>=<version>"` to ensure `uv.lock` is updated.
4. **Audit**: Run `uv run pip-audit` and `uv run bandit` to verify zero known vulnerabilities.

### Frontend Dependencies (`frontend/package.json`)
1. **Install**: Run `npm install --save-exact <package_name>` inside the `frontend/` directory.
2. **Budget Verification**: Re-run `npm run build && npm run size` to verify the bundle size remains strictly $< 200\text{ KB}$ gzipped.
3. **Audit**: Run `npm audit --audit-level=high`.

---

## 6. Secrets Management

- **Local Development**: All local secrets reside exclusively in the untracked `.env` file (copied from `.env.example`).
- **Production / CI**: Secrets are injected via environment variables or GitHub Actions repository secrets.
- **Strict Prohibition**: Never hardcode API keys, tokens, or JWT secrets in code or fixtures.
- **Masking**: All secrets in configuration classes must use `pydantic.SecretStr` so they never print or log in plaintext.
- **Log Sanitation**: Structlog is pre-configured with `_redact_sensitive_keys` to automatically strip tokens and authorization headers from application logs.

---

## 7. Incident Response Procedures

### Procedure A: Leaked Credential or API Token
1. **Immediate Revocation**: Instantly revoke the compromised key in the provider dashboard (e.g. LLM provider, database host).
2. **Credential Rotation**: Generate a replacement secret and update `.env` or production deployment environment settings.
3. **Repository History Purge**:
   - If committed locally: Amend the commit prior to pushing.
   - If pushed to remote: Use `git-filter-repo` or BFG Repo-Cleaner to permanently purge the file from git history.
   - Verify removal using Gitleaks: `gitleaks detect --source . --verbose`.
4. **Log Review**: Inspect provider usage logs to detect unauthorized token consumption or exfiltration.
5. **Incident Documentation**: Document root cause, timeline, and mitigation in the project incident log.

### Procedure B: Suspected Security or Data Breach
1. **Containment**: Revoke all active refresh tokens in the database:
   ```sql
   UPDATE refresh_tokens SET revoked = 1;
   ```
2. **Forensic Inspection**: Analyze `audit_logs` and server access logs filtered by `request_id` to establish the extent of unauthorized access.
3. **Regulatory Review (DPDP Act 2023)**: Determine if compromised data includes personal identification. If applicable, coordinate notification requirements per statutory timelines.
4. **Remediation & Patch**: Deploy hotfix branch following the emergency review protocol.

---

## 8. Handling User Privacy Data Requests

### User Data Deletion Request (Right to Erasure)
- **Self-Service Protocol**: Authenticated users can navigate to **Settings $\to$ Privacy & Account Deletion**, enter their current password, and type `DELETE`.
- **Backend Execution**:
  1. Authenticates current password (wrong password $\to$ HTTP 403).
  2. Executes an atomic transaction: replaces `user_id` and identifiers with `pseudo_id` in `audit_logs` and `consent_records`; deletes user record (cascading `user_pseudonyms`, `upload_records`, `user_profiles`, and `refresh_tokens`). Historical `prediction_logs` remain preserved anonymously.
  3. Deletes physical files from `./data/uploads` and vector directories from `./cache/vectors/`.
  4. If filesystem deletion fails, records the incident in `pending_deletions`.
- **Manual Cleanup**: Administrators can process any queued deletion tasks via the CLI:
  ```bash
  python -c "from alphalens.db.session import SessionLocal; from alphalens.api.routes.profile import process_pending_deletions; db = SessionLocal(); print(process_pending_deletions(db))"
  ```

### Data Access Request
1. Retrieve user's profile and consent metadata via standard authenticated endpoints (`GET /api/profile`, `GET /api/uploads`).
2. Provide export of served predictions from `prediction_logs` matching the user's active `pseudo_id`.

---

## 9. Releases & Versioning

AlphaLens follows [Semantic Versioning (SemVer 2.0.0)](https://semver.org/): `MAJOR.MINOR.PATCH`.

### Release Workflow
1. Ensure all features and fixes are merged into `main` via PRs with passing CI.
2. Update application version in `pyproject.toml` and `frontend/package.json`.
3. Update `CHANGELOG.md` with release notes, security fixes, and breaking changes.
4. Create an annotated git tag:
   ```bash
   git tag -a v0.2.0 -m "Release v0.2.0: Calibrated equity research engine & user features"
   git push origin v0.2.0
   ```

---

## 10. Phase Review Gates (Roadmap Compliance)

Before advancing from one phase to the next, the project must satisfy its designated review gate:

- [x] **Phase 0 (Foundation)**: FastAPI app skeleton, security headers, request ID, structured logging, CI setup.
- [x] **Phase 1 (User Features & Auth)**: Argon2 auth, JWT + refresh tokens, CSRF protection, PDF upload sandbox, Delete-My-Data privacy flow, canonical calibration decoupling, React SPA.
- [ ] **Phase 2 (Quantitative Engine & Backtesting)**: Multi-factor ranking algorithms (Value, Momentum, Quality, Low Volatility) and walk-forward cross-validation.
- [ ] **Phase 3 (Live Ingestion & Evidence Scrapers)**: Live NSE announcements, financial news scrapers with SSRF guards, and domain allowlist filtering.
- [ ] **Phase 4 (Distributed Architecture)**: Migration from in-memory SlowAPI to Redis storage backend; Celery task queue integration.
- [ ] **Phase 5 (Vector Embeddings & RAG)**: ChromaDB user vector index partitioning and semantic search retrieval pipeline.
- [ ] **Phase 6 (Automated Batch Precomputation)**: Scheduled nightly cron jobs precomputing Nifty 100 factor rankings.
- [ ] **Phase 7 (Production Containerization)**: Multi-stage Docker packaging, non-root user execution, and cloud deployment orchestration.
- [ ] **Phase 8 (Advanced Calibration Analytics)**: Longitudinal Brier score tracking and empirical reliability curves.
- [ ] **Phase 9 (Security Audit & Pen-Test)**: Comprehensive penetration testing, OWASP LLM audit, and external dependency license review.
- [ ] **Phase 10 (SEBI Compliance Review)**: Disclaimer banners, research methodology disclosures, and algorithmic transparency audits.
- [ ] **Phase 11 (Public Beta Launch)**: Performance stress testing, monitoring, and final public release.
