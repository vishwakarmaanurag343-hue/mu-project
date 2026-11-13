# AlphaLens Threat Model

## Threat Vectors & Mitigations

### 1. Untrusted Financial Data & Web Extraction
- **Threat**: Prompt injection or malicious instruction embedding through external filings, PDFs, earnings calls, or news feeds.
- **Mitigation**: All external data is treated strictly as passive data. Content is sanitized and isolated from execution contexts.

### 2. Secret & Credential Leakage
- **Threat**: Accidental leakage of API keys, model provider tokens, or database credentials.
- **Mitigation**:
  - `pydantic.SecretStr` for all sensitive settings.
  - Secret-safe structured logging (`alphalens.logging`) with redacting processors.
  - Git pre-commit hooks (`gitleaks`, `detect-private-key`).
  - Automated CI scanning with `gitleaks-action`.

### 3. Web & API Vulnerabilities
- **Threat**: XSS, CSRF, and clickjacking attacks against user sessions.
- **Mitigation**:
  - Strict Content Security Policy (CSP) headers served by FastAPI.
  - Double-submit CSRF tokens.
  - Auth tokens stored in `httpOnly`, `Secure`, `SameSite=Lax` cookies.
  - No `dangerouslySetInnerHTML`; markdown rendered securely via `react-markdown` without `rehype-raw`.
