# MORPHEUS Startup Wedge — Workload Performance Doctor

Status date: 2026-10-07

## The problem we are solving

Backend teams routinely choose an in-memory map, tree, sorted vector, scan path, cache index or similar container early in a system's life and leave that choice in place while the workload changes.

That creates a practical engineering problem:

- access mix changes from lookup-heavy to mixed lookup/range/filter behavior;
- skew and hot-key concentration change;
- record count and memory pressure change;
- update/read ratios change;
- latency targets tighten;
- the original data-structure choice becomes folklore rather than a measured decision.

Database systems research and tooling already show the same underlying pattern: index quality is workload-dependent, workload drift matters, and useful advisors increasingly evaluate candidate changes before applying them. MORPHEUS deliberately takes that principle to application-level data structures instead of claiming to replace a database optimizer.

## The product

**MORPHEUS is a workload performance doctor for application hot paths.**

A user can:

1. describe the hot path as MWS or draft it from plain English;
2. import a bounded real access window from TXT, CSV or JSON;
3. diagnose whether the current structure semantically matches the declared operation mix;
4. synthesize workload-specific candidate structures and routes;
5. see uncertainty rather than a fabricated speedup number;
6. measure bounded finalists on the local target machine when the decision requires it;
7. compile and behavior-verify the generated C++20 artifact;
8. obtain a reversible migration playbook instead of an automatic production switch;
9. later import a fresh production window and ask whether the accepted decision is still current;
10. export an evidence-bound decision-freshness passport and rollout/rollback ticket.

## Why this is different

MORPHEUS is not positioned as “an LLM that guesses the fastest container.”

Its differentiation is the complete decision lifecycle:

**real workload → deterministic model → candidate search → uncertainty → bounded measurement → artifact verification → human-controlled migration → drift revalidation**

AI can help translate human intent into a draft or improve explanation wording, but deterministic validation, measurements, hashes and control policy remain authoritative.

## Real workload intake

The guarded trace intake accepts:

- plain integer TXT;
- one- or multi-column CSV;
- JSON scalar arrays;
- JSON objects containing `keys`, `events` or `records`;
- dotted JSON key paths such as `request.key`.

It refuses ambiguous key columns and invalid rows by default. The raw input and normalized key window receive separate SHA-256 identities. Raw production trace content is not written into the MORPHEUS audit event; only bounded metadata and hashes are recorded.

This adapter does not prove that a finite trace is representative of future traffic. That remains an operator/research judgment.

## Initial buyer / user

The first useful user is not “everyone who writes code.”

The initial user is a backend, platform, systems or performance engineer who:

- owns a latency-sensitive in-memory hot path;
- can identify the current container/structure;
- can provide a bounded representative key-access sample;
- needs a defensible recommendation and migration plan rather than a benchmark screenshot.

## Tomorrow pilot flow

The smallest credible pilot is:

1. run the guarded single-node deployment;
2. choose a provided workload preset or describe the actual hot path;
3. select the current structure;
4. import a baseline TXT/CSV/JSON trace;
5. run Hot Path Doctor;
6. assess decision confidence;
7. run bounded local measurement when requested;
8. run full generated-artifact verification;
9. export the decision brief;
10. import a fresh observed window into Hot Path Watch;
11. export the freshness passport;
12. keep deployment/cutover human-controlled.

## Pilot metrics that are safe to collect

Measure product usefulness rather than inventing performance claims:

- time from trace import to a reviewable recommendation;
- trace-import success/failure reasons;
- percentage of recommendations that require additional measurement;
- percentage of generated artifacts that pass compile + behavior verification;
- number of decisions later marked current, review-required or superseded by fresh trace evidence;
- user acceptance/rejection reason for each recommendation;
- measured local latency/memory difference only where the explicit measurement gate actually ran.

## Non-goals / truth boundary

The current startup does not claim:

- universal performance superiority;
- automatic production cutover;
- multi-tenant SaaS isolation;
- HA/distributed control plane;
- a calibrated online anomaly detector;
- database-wide SQL index optimization;
- scientific novelty or patentability;
- external production reliability or customer traction.

Those require separate evidence. The product should remain useful without pretending those outcomes already exist.
