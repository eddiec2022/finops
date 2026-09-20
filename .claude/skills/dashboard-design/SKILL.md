---
name: dashboard-design
description: Design direction for the FinOps platform dashboard. Read this before building or modifying any frontend/UI work - it sets the visual direction and concrete defaults so new screens don't default to a generic templated look.
---

# FinOps Dashboard Design Guide

## The bar this has to clear

GOV-001 states the explicit goal: more intuitive and friendly than both NISE's own
dashboard and the native cloud cost tools (Azure Cost Management, AWS Cost Explorer,
GCP Billing). Those native tools are dense, technical, and cold - the opposite of what
this product needs to feel like. A generic, uncustomized shadcn/ui-default dashboard
(gray-on-white, default Inter, four stat cards + a line chart + a data table, zero
personality) would technically work but would fail this bar just as badly as the tools
it's supposed to beat.

## Direction: Warm & Approachable (teal & amber)

Friendly SaaS feel - rounded, calm, less severe than typical cost-management tooling.
This is still a B2B financial tool people trust with real numbers, so "warm" means
considered and human, not playful or childish. The palette below was chosen from
rendered options, not picked blind - use these values directly, don't reinterpret them.

### Color (exact values - convert to your Tailwind/shadcn config's expected format,
### hex or HSL, but use these exact colors, not approximations)

- **Primary (teal):** `#0F6E56` - buttons, links, primary chart lines/bars, anything
  that's the main interactive or "this is the important number" color
- **Primary light fill:** `#E1F5EE` - card backgrounds, subtle highlights, hover
  states behind teal content
- **Primary dark (text-on-light-teal):** `#04342C` or `#085041` - text/icons sitting
  on the light teal fill above (e.g. inside a highlighted recommendation card)
- **Secondary/warning accent (amber):** background `#FAEEDA`, text `#633806` or
  `#854F0B` - use for informational callouts and anything warning-adjacent. This is
  NOT the primary accent - teal leads, amber supports
- **True errors/danger:** a real red, used sparingly - only for genuine problems
  (a failed sync, a broken connection), never for routine cost/idle flags. Routine
  "this resource is idle" or "this is over budget" states should use amber or teal,
  not red - red should mean "something is actually broken," not "here's a number."
- **Neutrals:** warm-toned grays, not blue-grays. Small difference, but blue-grays
  read as cold/clinical by default.

### Shape & type

- **Border radius:** generous (8-12px on cards and buttons, not sharp corners) -
  this one detail does a lot of the "warm" work on its own.
- **Shadows:** soft, subtle elevation. Avoid harsh drop-shadows.
- **UI font:** something rounded-but-professional - Inter or Plus Jakarta Sans, not a
  stiff corporate serif or an overly technical monospace-everywhere look.
- **Numbers/figures specifically:** use a tabular/monospace font (e.g. JetBrains Mono)
  for dollar amounts and metrics. This is a small, deliberate fintech convention -
  it makes columns of numbers actually scannable and reads as considered rather than
  default. Don't use it for body text or labels, only for the figures themselves.

When customizing shadcn/ui: change the actual theme tokens (colors, radius, font
family) rather than using the component defaults out of the box. Using shadcn's
components with zero token customization is exactly the generic look to avoid.

## FinOps-specific UX patterns

- **Default landing view** (aggregate spend + 90-day forecast): this is the "at a
  glance, how are we doing" view - it should read as calm and clear, not overwhelming.
  Resist the urge to cram every number onto this screen.
- **Drill-down navigation** (subscription -> resource group -> service/resource):
  should feel like moving through one continuous space (breadcrumbs, smooth
  transitions), not jarring separate page loads.
- **Forecast display:** distinguish actual/historical data from projected data
  visually (e.g. solid line for actuals, dashed for projection) - the backend is
  explicit that this is a simple v1 burn-rate model, not a precise prediction, and
  the UI should carry that honesty rather than presenting a dashed guess as
  confidently as real history.
- **Recommendation cards:** lead with the specific action and dollar impact. Use the
  primary-light teal fill (`#E1F5EE` bg / `#085041` text) as the default recommendation
  card treatment - it's the "here's something good you can do" color, not a warning.
  The backend's "approximate, not a billing quote" caveats should be present (a small
  info affordance, not buried) but shouldn't read as a scary disclaimer block that
  undermines trust in the recommendation itself.
- **Empty states matter a lot here** - several endpoints correctly return empty
  results when there isn't enough history yet (a real, expected v1 state given how
  new this environment's data is, not an error). Empty states should be warm and
  informative ("Not enough usage history yet - check back once N days of data have
  synced"), never a bare "No results" or a broken-looking blank panel.

## What to avoid

- The generic AI-dashboard cliche: stat cards + line chart + data table, assembled
  with no point of view.
- Cold enterprise blue-on-white SaaS template look.
- Dense, spreadsheet-style tables with no visual hierarchy - that's the native
  tools' failure mode, not something to replicate.
- Using red/alarm styling for routine informational states - that's what the amber
  accent and teal recommendation treatment are for.
- Shipping shadcn/ui components with default tokens unchanged.
