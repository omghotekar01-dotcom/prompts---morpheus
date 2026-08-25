# MASTER PROMPT #14 — V12: MORPHEUS TERMINAL, VISUALIZATION & DEVELOPER EXPERIENCE

Create a world-class engineering interface for MORPHEUS—not a decorative dashboard. It must let a beginner specify a workload while giving researchers full visibility into search, predicted/measured cost, constraints, generated structures and provenance.

## Product surfaces
Build: (1) guided workload studio, (2) raw MWS editor, (3) synthesis command center, (4) candidate/Pareto explorer, (5) generated-design inspector, (6) benchmark laboratory, (7) runtime adaptation timeline, (8) research/export center. CLI and web must expose the same domain semantics.

## Visual language
Use a dense professional terminal aesthetic inspired by scientific/financial engineering tools without copying any product. Large readable typography, strong hierarchy, keyboard-first navigation, responsive panes, restrained glass/translucency only where readability survives, accessible contrast and reduced-motion support. Avoid tiny text, meaningless neon, excessive cards and fake telemetry.

## Workload Studio
Offer NL input, form wizard and Monaco YAML/JSON editor converging on MWS. Show schema autocomplete, semantic errors, assumptions, operation mix, field graph, selectivity/cardinality and hard constraints before synthesis. Never hide an inferred value.

## Synthesis Command Center
Live event stream: validation -> IR lowering -> candidate generation -> pruning -> model scoring -> finalist benchmarking -> correctness verification -> code generation. Display elapsed time, candidates explored/pruned, incumbent objective, feasibility and resource budget. Clearly label PREDICTED vs MEASURED.

## Pareto Explorer
Interactive latency/memory/update/build tradeoff plot; filter by primitive composition and feasibility. Selecting a point reveals ConfigurationIR, per-operation routing, memory decomposition, predicted metrics, benchmark metrics, uncertainty and why it is/non-dominated. Never fabricate measurements.

## Design Inspector
Render logical dataset -> operations -> selected physical structures -> generated API as an explorable graph. Show ownership and update propagation across composite structures. Provide source tabs for generated C++/manifest/tests and exact build command in safe copyable form.

## Runtime
Timeline declared workload versus observed windows, drift score, proposed candidate, hysteresis state, rebuild/migration cost and switch events. Users must see why adaptation did or did not trigger.

## Research mode
Expose seeds, machine profile, compiler, model version, baselines, repetitions, confidence intervals, raw experiment references and export manifest. Add comparison view for two synthesis runs with semantic workload diff and configuration diff.

## CLI
Implement concise commands: `morpheus validate`, `synthesize`, `inspect`, `benchmark`, `compare`, `export`, `serve`. Human output is elegant; `--json` is stable machine output. Exit codes distinguish invalid input, infeasible design, build/test failure and internal failure.

## Performance/accessibility
Virtualize long candidate tables/logs, lazy-load source artifacts, preserve URL-deep-link state, meet keyboard navigation and WCAG expectations. Do not animate high-frequency telemetry continuously.

## Deliverable
Create information architecture, routes, component system, state/query layer, API client, error/empty/loading states, responsive layouts, command palette, shortcuts, visualization specifications, design tokens and end-to-end tests. Every visual must answer a real engineering question.
