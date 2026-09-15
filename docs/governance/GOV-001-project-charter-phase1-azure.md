# 001 — Project Charter & Phase 1 (Azure) Architecture Scope

**Status:** DRAFT — pending approval. No implementation work begins until this is signed off.

## Document Control

| Role | Owner | Responsibility |
|---|---|---|
| Lead Architect | Claude (this project) | Drafts architecture, governance docs, Claude Code task specs |
| Approver (interim CIO) | Edson | Architecture sign-off before implementation — filling the open CIO seat |
| Domain Reviewer | Partner | Functional/UX feedback on working prototypes, drawing on deep cloud experience |
| Implementer | Claude Code | Executes tasks via the `next_task.txt` queue, same pattern as NISE |

**Workflow:** Lead Architect drafts → Edson approves → Claude Code implements → tests verified → Domain Reviewer exercises the working prototype → feedback feeds the next task.

## 1. Purpose

A vendor-agnostic multi-cloud FinOps platform that connects to a customer's cloud environment(s), inventories deployed resources, tracks utilization, forecasts spend out to 90 days, and recommends concrete cost reductions — with a dashboard experience that is deliberately more intuitive than both the native cloud cost tools (Azure Cost Management, AWS Cost Explorer, GCP Billing) and NISE's own dashboard.

This is a standalone product, separate from CORNETiQ/NISE — its own repo, its own stack, its own identity (name TBD — see Section 9).

## 2. Product Definition & Phased Build

- **Phase 1 — Azure** (this document's scope)
- **Phase 2 — AWS**
- **Phase 3 — GCP**
- **v1 is not "done" until all three phases ship**, normalized into one data model with one unified dashboard.

**The single most important architectural decision in this document:** even though only Azure is being built right now, the ingestion → normalization → storage layer must be designed provider-agnostic from Phase 1. Azure-specific fields (subscription ID, resource group, SKU naming) get mapped into a shared schema from day one. Retrofitting a normalization layer after AWS/GCP connectors already exist would mean re-touching everything built in Phase 1 — expensive to avoid now, expensive to fix later.

## 3. Phase 1 (Azure) Scope

### 3.1 Environment
- Single Azure subscription (your current test/dev environment)
- Auth: service principal, least-privilege — **Cost Management Reader** + **Reader** roles at subscription scope. Read-only everywhere; no write/modify permissions anywhere in Phase 1.

### 3.2 Inventory
- Enumerate all deployed resources via **Azure Resource Graph** (fast, scales across resource types without per-service API calls)
- Capture: resource type, region, resource group, tags, SKU/size, creation date

### 3.3 Utilization
- Pull metrics via **Azure Monitor** (CPU, memory where available, disk I/O, network) for compute resources (VMs, App Services)
- Idle/low-utilization thresholds are a **configurable setting**, not hardcoded (e.g., default "<10% avg CPU over 14 days" but adjustable)

### 3.4 Cost Data & Forecasting
- Source: **Azure Cost Management API**, using the **amortized cost view** — not list price — so Reserved Instance and Savings Plan coverage is reflected in the actual burn rate rather than overstating it
- v1 forecasting model: burn-rate / linear extrapolation over a trailing rolling window, projected forward across next few days, weeks, and out to 90 days
- The forecasting model is built behind a pluggable interface so the Phase 2 upgrade (Prophet/ARIMA/ML-based, with confidence intervals) can replace it without touching ingestion or the dashboard
- Granularity: **aggregate subscription-level spend is the default view**, with drill-down to resource group → service/resource type → individual resource

### 3.5 Recommendations (v1 — advisory only, no automated action)
- **Rightsizing** — flag VMs/App Services with sustained low utilization relative to their SKU; suggest a smaller SKU
- **Idle/orphaned resource detection** — unattached disks, unused public IPs, stopped-but-not-deallocated VMs, empty resource groups
- **Non-peak scheduling** — identify likely non-production resources (tags, naming convention, or usage pattern) with low overnight/weekend usage; recommend a start/stop schedule as a *suggestion*, not an automated action
- **Reserved Instance / Savings Plan recommendations** — identify steady-state on-demand usage that would benefit from a commitment purchase, with estimated savings

Explicitly deferred to v2: storage tier optimization, egress/network cost recommendations, and any automated remediation (one-click or auto-execute actions) — per your call to keep v1 advisory-only.

### 3.6 Dashboard / UX
- Web-first, clean-slate frontend. Not an iteration on NISE's dashboard — the explicit bar is "more intuitive and friendly than NISE's dashboard and the native cloud tools."
- Default landing view: aggregate current spend + 90-day forecast trend
- Drill-down: subscription → resource group → service/resource
- Recommendations shown as an actionable list with estimated dollar impact per item

## 4. Proposed Technical Architecture — REQUIRES YOUR APPROVAL

| Layer | Proposal | Why |
|---|---|---|
| Backend | Python 3.x, FastAPI | Async-friendly, strong Azure/AWS/GCP SDK support, keeps the Python tooling/test discipline your team already has from NISE (pytest, Docker Compose regression pattern) even on a clean-slate codebase |
| Cloud SDK | `azure-mgmt-costmanagement`, `azure-mgmt-resourcegraph`, `azure-monitor-query` | Official Azure SDKs, straightforward swap-in for AWS/GCP equivalents in later phases |
| Database | PostgreSQL | Relational normalization across providers is a natural fit; time-series cost/utilization tables indexed by date + resource |
| Scheduling | APScheduler (v1) | Simple periodic ingestion jobs; revisit Celery+Redis only if job volume grows in later phases |
| Frontend | React + TypeScript, Tailwind CSS + component library (e.g. shadcn/ui), Recharts | Deliberately different visual foundation from NISE, chosen to hit the "intuitive, friendly" bar and support the drill-down navigation model |
| Forecasting | pandas / numpy / statsmodels (v1); Prophet or equivalent (Phase 2 upgrade) | Simple and inspectable to start, swappable later |
| Deployment | Docker containers on the existing Win2022 VM | Mirrors NISE's canonical Docker regression pattern |

## 5. Repo & Environment

- New GitHub repo — name TBD (see open decisions)
- Same Win2022 Server VM as NISE
- Task queue pattern: `next_task.txt` at repo root, same convention as NISE
- Canonical test command: to be defined once the stack above is confirmed

## 6. Out of Scope for v1 (Backlog)

- AWS integration (Phase 2) · GCP integration (Phase 3)
- Storage tier optimization and egress/network cost recommendations
- Automated remediation / action-taking — gated on v1's advisory recommendations proving accurate
- Advanced time-series forecasting — gated on the simple model being validated against real data
- Multi-subscription / multi-tenant support — architecture shouldn't preclude it, but it's not built or tested until it's actually needed

## 7. Open Decisions Requiring Your Sign-off

1. **Approve or revise the proposed stack** (Section 4)
2. **Product name** — needed for the repo and all doc headers going forward
3. Confirm idle/scheduling/rightsizing thresholds should ship as **configurable defaults** rather than fixed values (my assumption) — flag it if you want specific starting numbers instead
4. Confirm the review workflow in the Document Control table matches what you intend

---
Once this is approved, Section 3 becomes the first `next_task.txt` for Claude Code — starting with repo/environment scaffolding and the Azure Resource Graph inventory connector as the first working slice.
