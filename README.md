# AlphaLens

Calibrated, evidence-cited equity research assistant for the National Stock Exchange of India (NSE).

## Documentation
- [Agent Rules](docs/AGENT_RULES.md)
- [ADR-001: Market, prediction target, and universe](docs/adr/001-scope.md)
- [ADR-002: React (Vite) frontend + FastAPI backend](docs/adr/002-frontend.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Standard Operating Procedures](docs/SOP.md)

## Development Setup

### Backend
```bash
uv sync
uv run pre-commit install
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Quality & Verification
```bash
make check
```
