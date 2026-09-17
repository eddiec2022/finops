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
Phase 1 (Azure) — Task 1 (environment & repo scaffolding) complete. Task 2
(Azure Resource Graph inventory connector) in progress.
See `docs/governance/GOV-001-project-charter-phase1-azure.md` for full scope.

## Known issue: WSL2/dockerd restart recurrence (Task 3)
During Task 2 live verification, a recurring restart pattern was observed at the
WSL2-instance level (dockerd/journald cycling, roughly every 20–90 seconds in bursts).
It was ruled out as a repeat of an earlier, separate Trusted Launch/nested-virt
VM-level issue (that one restarted the whole Hyper-V VM; this one restarts the
Ubuntu-24.04 WSL instance one layer down — kernel uptime never resets, no Hyper-V
event, no OOM-kill, no Windows reboot, no Windows Update install correlates). Root
cause has not been pinned down.

A lightweight monitor now runs inside the WSL2 distro to record recurrences instead
of losing them to silence:
- Script: `/usr/local/bin/check-docker-restart.sh` (source of truth checked into
  `ops/wsl-monitoring/`), run every 30s by `docker-restart-monitor.timer`
  (systemd unit, also in `ops/wsl-monitoring/`).
- Log: `/var/log/docker-restart-monitor.log` inside the WSL2 distro. Each line is
  either a `check_ok` heartbeat or a `RESTART_DETECTED` line with the previous and
  new dockerd start timestamps.
- To check it: `wsl -d Ubuntu-24.04 -- cat /var/log/docker-restart-monitor.log`
- To check the timer itself is alive: `wsl -d Ubuntu-24.04 -- systemctl list-timers docker-restart-monitor.timer`
- To reinstall after the WSL distro is reset/recreated: copy the two files from
  `ops/wsl-monitoring/` to `/usr/local/bin/` and `/etc/systemd/system/` respectively,
  then `sudo systemctl daemon-reload && sudo systemctl enable --now docker-restart-monitor.timer`.

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
