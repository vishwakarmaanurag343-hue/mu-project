## What
## Why (link issue / ADR)
## How tested
## Security checklist
- [ ] No secrets, keys, or .env changes
- [ ] All external input validated (pydantic)
- [ ] Missing data = None, not 0
- [ ] New functions have type hints, docstrings, tests
- [ ] No new dependencies (or listed + justified)
