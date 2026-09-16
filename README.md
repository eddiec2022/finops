# FinOps Platform (working name — TBD)

Vendor-agnostic multi-cloud FinOps platform: resource inventory, utilization tracking,
cost forecasting (up to 90 days), and cost-optimization recommendations across
Azure, AWS, and GCP.

Separate project from CORNETiQ/NISE. Built in phases, one cloud provider at a time —
Azure first, then AWS, then GCP. v1 is not complete until all three ship with a
normalized data model and unified dashboard.

## Canonical test command

```
docker compose build
docker compose run --rm backend pytest -q
```

`docker compose up` brings up `backend` (FastAPI, :8000), `frontend` (Vite dev server, :5173),
and `db` (PostgreSQL, :5432).

## Status
Phase 1 (Azure) — Task 1 (environment & repo scaffolding) in progress.
See `docs/governance/GOV-001-project-charter-phase1-azure.md` for full scope.

## Roles
| Role | Owner |
|---|---|
| Lead Architect | Claude |
| Approver (interim CIO) | Edson |
| Domain Reviewer | Partner |
| Implementer | Claude Code |

## Structure
- `docs/governance/` — numbered governance docs (architecture, scope decisions), same convention as NISE
- `backend/` — Python/FastAPI service (ingestion, normalization, forecasting, API)
- `frontend/` — React/TypeScript dashboard
- `next_task.txt` — current task for Claude Code, same queue pattern as NISE

## Working pattern
Lead Architect drafts governance doc → Edson approves → task written to `next_task.txt` →
Claude Code implements → tests verified → Domain Reviewer exercises the prototype.
