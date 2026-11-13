# ADR-002: React (Vite) frontend + FastAPI backend

Status: Accepted · Date: 2026-11-13 · Supersedes: Streamlit plan

## Decision
- Frontend: React 18 + TypeScript, built with Vite (no Next.js, no SSR).
  TanStack Query, React Router, Tailwind CSS, Recharts, react-markdown.
- Backend: Python FastAPI, single service.
- Same-origin deployment: FastAPI serves the built frontend (frontend/dist)
  and the API under /api. In development, Vite proxies /api to FastAPI.
  Result: no CORS, httpOnly cookie auth works everywhere.
- API contract: TypeScript types generated from FastAPI's OpenAPI schema
  (openapi-typescript). CI fails if they drift.

## Why
- React: industry standard, rich ecosystem, strong portfolio value.
- Python-only backend: the ML stack (pandas, scikit-learn,
  sentence-transformers, ChromaDB) is Python; one backend language
  keeps the 18-week timeline realistic.
- Speed comes from precompute + caching + streaming, not language choice.

## Performance design
- Nightly precompute of factors and quant scores for the Nifty 100.
- Two-tier report: instant quant result; LLM evidence streamed via SSE.
- Daily cache of LLM summaries per ticker.
- Route-level code splitting; charts lazy-loaded.

## Targets
- Initial JS bundle < 200 KB gzipped.
- Quant result on screen < 300 ms after request.
- Full report (with LLM evidence) < 15 s, streamed progressively.

## Security
- Auth: httpOnly + Secure + SameSite=Lax cookies; CSRF double-submit token.
- No dangerouslySetInnerHTML anywhere; react-markdown without rehype-raw.
- Strict CSP served by FastAPI.

## Alternatives considered
- Streamlit: slow full reruns, awkward auth, breaks strict CSP.
- Next.js: unnecessary SSR/Node server.
- Go gateway: no user-visible speed gain; +2–3 weeks. Listed as future work.
