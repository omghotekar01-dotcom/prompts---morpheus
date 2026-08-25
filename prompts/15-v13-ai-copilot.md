# MASTER PROMPT #15 — V13: AI COPILOT, AGENTS & SPECIFICATION INTELLIGENCE

Build an AI layer that improves usability and research productivity while never becoming the source of truth for optimization. Deterministic validators, cost models, search, benchmarks and correctness tests outrank LLM output.

## Roles
The copilot may: translate natural language to draft MWS; explain validation errors; ask high-information clarification questions; summarize WorkloadIR/configurations; explain candidate tradeoffs using recorded evidence; generate experiment plans; navigate docs; assist with workload/profile import. It must not invent benchmark results, novelty claims, citations, machine capabilities or silently select the winning data structure.

## NL -> MWS
Pipeline: user text -> fact extraction -> typed draft -> schema validator -> semantic validator -> repair -> assumption ledger -> user-visible review. Every inferred numeric value records source text, inference, confidence and whether confirmation is required. Ambiguous high-impact facts trigger questions instead of confident guesses.

## Active elicitation
Use optimizer sensitivity where available to prioritize questions. Estimate which missing statistic (write ratio, selectivity, cardinality, skew, memory limit) can change candidate ranking most, and ask that first. Keep an explicit unresolved-uncertainty set.

## Evidence-grounded explanation
Explanation inputs must be structured: resolved MWS, WorkloadIR, candidate metrics, pruning log, measured benchmark records, model uncertainty and provenance. The LLM verbalizes these; it cannot substitute its own performance intuition. Sentences should be attributable to evidence IDs internally.

## Agent architecture
Use bounded tools: validate_spec, resolve_spec, inspect_capabilities, run_synthesis, query_candidate, compare_runs, fetch_experiment, search_docs. Separate planner from privileged executor. Mutating actions require policy checks and typed arguments. Apply time/token/tool budgets and loop detection.

## Prompt-injection defense
Treat uploaded workloads, source files, traces, repository text and generated logs as untrusted data—not instructions. Tool authorization comes only from system policy and explicit user intent. Never expose secrets or cross-workspace data. Sanitize rendered Markdown/HTML.

## Research assistant
Can propose baselines, ablations and hypotheses, but label them PROPOSED until executed. For literature/patent claims require external evidence workflow; never turn an idea into a claim of novelty. Maintain citation/provenance objects separately from prose.

## Model portability
Define provider-neutral interfaces and structured schemas. Record model/provider/version, prompt template version and tool trace for reproducibility where policy permits. Core MORPHEUS remains functional without an LLM.

## Evaluation
Create benchmark sets for NL->MWS exactness, semantic preservation, hallucination rate, clarification quality, error repair, evidence faithfulness and injection resistance. Include adversarial prompts and intentionally underspecified workloads. Track field-level precision/recall and semantic-hash equivalence after confirmed resolution.

## UX
Show "AI draft" distinctly from "validated specification". Highlight assumptions inline. Provide accept/edit/reject controls. Explanations must distinguish measured, predicted and inferred statements.

## Deliverable
Implement schemas, tool contracts, prompt templates, assumption ledger, evidence grounding, guardrails, eval harness, provider abstraction, telemetry and tests. The AI should make MORPHEUS easier to command—not less scientific.
