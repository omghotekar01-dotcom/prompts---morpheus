# MASTER PROMPT #39 — MORPHEUS TRUE GRAND MASTER FINAL INTEGRATION & IMPLEMENTATION PLAN

## Status
This is the **canonical final integration prompt** of the 39-prompt MORPHEUS Engineering Bible. Prompt #30 is an integration checkpoint from the earlier corpus; this file supersedes it as the final execution directive. Specialized volumes remain normative for their domains. Tested code and versioned executable contracts remain higher authority than prose when implementation and documentation diverge.

## Mission
Build MORPHEUS as a real workload-aware physical data-structure synthesis and adaptation system that can accept declarative workload intent, construct a typed semantic IR, reason over compatible physical structures/compositions, estimate and measure target-machine costs, search under explicit constraints/objectives, generate executable C++20, verify correctness, benchmark fairly, preserve evidence and optionally adapt under workload drift with transition-cost-aware safety.

MORPHEUS is not "an LLM that picks a data structure." Its core intelligence is deterministic systems engineering:

`specification -> semantic IR -> capability algebra -> calibrated evidence -> constrained search -> physical ConfigurationIR -> code generation -> compile/correctness gates -> measurement -> evidence -> guarded adaptation`.

AI is an optional translation/explanation layer and can never manufacture measurement truth, authorize blocked features or override deterministic validators/control policies.

# I. Non-negotiable constitution
1. Correctness before speed.
2. Measured, predicted, inferred and proposed are distinct truth states.
3. Hard constraints are never silently relaxed.
4. Unsupported semantics fail explicitly.
5. Logical workload intent remains separate from physical design.
6. Every important decision/artifact has versioned provenance and identity.
7. Calibration binds to exact implementation/operation/scale/distribution where required.
8. Search quality is tested against exhaustive/model or empirical oracle on tractable spaces.
9. Generated code is untrusted until compile and behavioral verification pass.
10. Runtime switching requires policy authority, migration verification and rollback semantics.
11. Research-only features remain fail-closed for automatic control.
12. Release/public claims never exceed packaged evidence.
13. CI smoke performance is not publication-grade performance evidence.
14. A repository engineering percentage is not publication, patent, customer or universal-SOTA validation.
15. The system must remain useful without an external LLM.

# II. Canonical architecture
The complete architecture is layered:

1. **MWS / input layer** — YAML/JSON/form/NL translation into one declarative contract.
2. **Validation/resolution** — syntax, semantics, assumptions/defaults, units and contradictions.
3. **WorkloadIR** — canonical typed logical workload identity.
4. **Primitive/implementation registry** — capabilities, parameters, maturity and platform support.
5. **Machine/calibration evidence** — target-machine profile and exact measurement cells.
6. **Cost/uncertainty model** — operation-specific and composition-aware estimators.
7. **Candidate/composition builder** — ownership, query routing and mutation dependencies.
8. **Feasibility engine** — semantic/platform/security and hard-resource constraints.
9. **Search engine** — exhaustive small-space, greedy baseline, beam/Pareto and future advanced search.
10. **ConfigurationIR** — canonical physical design decision.
11. **Code generator** — standalone/native implementation artifact.
12. **Verification** — compile, stateful differential, sanitizer/property/fuzz gates.
13. **Benchmark/research harness** — frozen experiments, baselines, statistics and held-out evaluation.
14. **Evidence/provenance store** — content hashes, ledger, manifests and release bundles.
15. **Runtime monitor/adaptation** — immutable observed snapshots, drift, transition-aware resynthesis.
16. **Local data-plane publication** — versioned in-process activation/rollback where implemented.
17. **Control plane/API/CLI/UI** — inspectable developer/product surface.
18. **Optional Copilot/agent layer** — bounded tools and evidence-grounded explanation.
19. **Release/reproducibility layer** — claim gates, contract fingerprints and deterministic packaging.
20. **Research/patent/product layer** — experiments, prior-art discipline, paper/IP/pilot workflow.

# III. Core proof path
A complete local engineering proof must be reproducible from a clean checkout:

`MWS -> validate/resolve -> WorkloadIR -> compatible real primitive/composite candidates -> calibrated/bootstrap cost with provenance -> hard feasibility -> deterministic search/Pareto -> ConfigurationIR -> generated C++20 -> compile -> stateful differential correctness -> baseline/candidate measurement -> evidence/reproducibility manifest`.

If runtime adaptation is claimed, additionally reproduce:

`declared workload + immutable observed snapshots -> drift -> re-evaluation -> predicted long-horizon benefit - switching cost -> policy/hysteresis/health gates -> verified migration -> safe local activation/retain/rollback -> cumulative benefit experiment`.

# IV. Canonical data contracts
Maintain typed/versioned identities for at least:
- MWS raw/resolved input;
- assumption ledger;
- WorkloadIR;
- PrimitiveManifest and implementation ID;
- MachineProfile;
- CalibrationProfile/Measurement;
- CostEstimate;
- ConfigurationIR;
- SearchSummary/Pareto set;
- ArtifactManifest;
- VerificationManifest;
- ExperimentManifest/raw measurement/statistical summary;
- ObservedWorkloadSnapshot;
- AdaptationDecision/MigrationPlan;
- FeatureRegistry/promotion policy;
- evidence ledger;
- release manifest;
- strict reproducibility manifest.

Breaking semantics require new contract versions. Never reinterpret old evidence silently.

# V. Search and synthesis requirements
The optimizer must:
- derive candidate options from capabilities and workload semantics;
- support physical compositions, not just one primitive per project;
- canonicalize/deduplicate configurations;
- prune semantic and hard-resource infeasibility before ranking;
- preserve raw metric vectors;
- separate exhaustive/model-oracle evaluation from heuristic selection;
- report theoretical/evaluated counts and truncation;
- retain deterministic tie-breaking and search parameters;
- expose Pareto alternatives when objectives conflict.

No general global optimality claim is allowed for beam/greedy or a bounded primitive universe.

# VI. Composite physical design requirements
A composite plan must define:
- authoritative storage;
- secondary indexes/filters/projections;
- logical operation routes;
- mutation dependency graph;
- memory/build/update accounting;
- synchronization semantics;
- migration order;
- correctness oracle.

A heterogeneous design should be chosen only when it satisfies semantics and the objective under evidence. Demonstrate at least one workload where composition is compared against best single structure and a reasonable manual baseline if composition benefit is publicly claimed.

# VII. Cost/model requirements
Start interpretable. Consume measured anchors only under compatible identity. Preserve bootstrap fallback and uncertainty. Evaluate:
- absolute error;
- ranking correlation;
- top-k recall;
- selected-candidate regret;
- coverage by operation/implementation/scale/distribution;
- failure/out-of-distribution behavior.

Do not extrapolate invisibly. Candidate-level end-to-end measurement is stronger evidence for that exact artifact/workload/machine than independent primitive-level anchors.

# VIII. Hardware-aware requirements
MachineProfile and calibration may include cache/topology/compiler/architecture information. Explore cache regimes, locality, skew, branch behavior, SIMD and memory bandwidth only with measured or explicitly modeled evidence. Cross-machine transfer is a separate research question requiring multi-machine validation.

# IX. Primitive ecosystem requirements
Primitive admission lifecycle:

`PLANNED -> IMPLEMENTED_REFERENCE -> CORRECTNESS_VERIFIED -> BENCHMARK_CALIBRATED -> SEARCH_ELIGIBLE -> optional RUNTIME_ELIGIBLE`.

The encyclopedia may list advanced families (ART, Roaring, Bloom/Cuckoo/Xor filters, LSM, learned indexes, spatial/graph/succinct structures), but the runtime registry/tested code determines actual support.

# X. Code generation and correctness
Generated source must be deterministic enough for provenance, compile under supported toolchains and implement the same semantics encoded in WorkloadIR/ConfigurationIR. Verification includes stateful operation sequences and secondary-index synchronization. Correctness failure invalidates a candidate regardless of predicted performance.

A host subprocess with timeout is not a hardened sandbox. Production-grade sandbox claims require stronger isolation evidence.

# XI. Benchmark science
Freeze:
- commit;
- workload/spec/config hashes;
- machine profile;
- compiler/version/flags;
- baseline identity/version;
- scale/distribution parameters;
- operation counts;
- warmups/repetitions/seeds;
- analysis protocol;
- raw result hashes.

Use fair identical logical semantics, paired analysis where appropriate, confidence/sample reporting and negative-result retention. CI measurement smokes validate protocol/execution, not final scientific superiority.

# XII. Runtime adaptation
Runtime observations never mutate historical declared workload/evidence. Switching decisions include transition cost, uncertainty, hysteresis/cooldown and feature-policy authority. Research trace classifiers cannot drive automatic switching until explicitly promoted through a validated readiness/policy path.

Native cross-process hot swap remains a separate capability from local in-process reference/version switching. Never merge those labels.

# XIII. Security
Apply the dedicated security volume: strict parsing, no shell interpolation, bounded workers, workspace containment, content hashes, tamper detection, secret hygiene, fail-closed feature policy and untrusted AI/repository content. Strong sandbox, multi-tenant IAM and external signing are separate maturity tiers.

# XIV. Portability
Keep semantic identity stable across supported platforms while recording toolchain/ABI differences. Test declared Linux/Windows/Python/C++/frontend matrices. Generated artifact compatibility is scoped to its target/toolchain identity. ARM/macOS/embedded/distributed support is not claimed without validation.

# XV. API, UI and developer experience
The user must be able to inspect:
- input workload and assumptions;
- WorkloadIR/config identity;
- search strategy/progress;
- infeasible reasons;
- Pareto/candidate trade-offs;
- predicted vs measured labels;
- active calibration coverage;
- generated source/verification;
- benchmark evidence;
- runtime/adaptation history;
- capability/completion truth states.

The UI cannot invent fake progress/telemetry. A CLI/API path must remain available independent of UI.

# XVI. AI/Copilot
AI may:
- translate natural language into a candidate MWS;
- ask clarifying questions;
- explain deterministic search/evidence;
- help navigate artifacts/docs;
- invoke explicitly allowed read-only or bounded tools.

AI may not:
- declare benchmark results without evidence;
- change feature maturity/automatic control through text alone;
- override validators/constraints;
- claim novelty/patent status;
- execute arbitrary commands/plugins because text requested it.

# XVII. Research program
Core research questions should test mechanisms actually implemented, for example:
- Do heterogeneous compositions beat best single structures on heterogeneous workloads?
- How accurately do machine/distribution-bound calibrations rank candidates?
- How close does beam search approach exhaustive optimum with fewer evaluations?
- Does active measurement reduce benchmark cost while retaining decision quality?
- Does transition-aware adaptation reduce long-horizon cost under workload drift?
- Does uncertainty-aware validation reduce incorrect switches/selection?
- How well does calibration transfer across machines?

Use strong standard/manual/specialist baselines, exhaustive small-space oracle where tractable, ablations and limitations/threats-to-validity sections.

# XVIII. Prior art, paper and patent
Never claim automatic data-structure design is unprecedented. Maintain literature and patent matrices against automatic physical design, Data Calculator/Periodic Table/Design Continuums, database tuning, adaptive indexing, learned indexes and older DS selection/synthesis work.

Potential MORPHEUS contribution hypotheses may combine standalone heterogeneous composition synthesis, machine/distribution-bound calibration, executable C++ code generation, explicit correctness/evidence gates, uncertainty/active measurement and transition-aware reversible adaptation. These remain hypotheses until novelty search and experiments support them. Patentability requires professional legal review.

# XIX. Product/startup
Validate real users in performance-sensitive infrastructure before scaling SaaS. Measure time/cost saved relative to manual selection/tuning. Start from a reproducible local/SDK workflow. Commercial claims, pricing and traction require real evidence.

# XX. Distributed/edge frontier
Distributed and embedded MORPHEUS are explicit future/research execution classes unless implemented/tested. They require network/consistency/failure or memory/flash/real-time cost models respectively. Do not count architecture documents as implementation.

# XXI. Test and continuity system
Every high-risk invariant maps to tests. Maintain cross-platform CI, native sanitizers, generated-artifact verification, calibration identity tests, evidence tampering tests, runtime failure-injection/concurrency tests and release claim/provenance tests. Record important architectural decisions and exact-head CI checkpoints. Conversational memory is never the only project record.

# XXII. Release and reproducibility
A release package must bind real artifact roles that physically exist, validate known structures, check cross-artifact hashes and evaluate claims from actual packaged evidence. Strict reproducibility should bind exact source commit, evidence files, API-contract fingerprint and feature-policy fingerprint. Hash identity is not external attestation/signature/scientific validation.

# XXIII. Engineering completion model
Maintain a machine-readable phase/gate ledger. A phase is complete only when each declared capability gate passes. If the system reports 100%, it means **100% of enumerated repository engineering gates**, and must list excluded outcomes such as:
- publication acceptance;
- patent filing/grant/freedom-to-operate;
- independent benchmark validation;
- production deployment at external organizations;
- customer traction;
- universal state-of-the-art superiority;
- regulatory/security certification not performed.

Do not define an easy completion ledger merely to obtain 100%. Add gates when a capability becomes part of the declared product/research scope.

# XXIV. Canonical implementation phases
Use this dependency order for new work:

**Phase 1 — Formal input/compiler core**
MWS, validation, provenance, WorkloadIR.

**Phase 2 — Physical primitive laboratory**
Real tested primitive implementations and capability registry.

**Phase 3 — Empirical calibration and hardware identity**
MachineProfile, repeated primitive measurements, distribution identity.

**Phase 4 — Cost/uncertainty engine**
Transparent estimates, fallback, coverage, held-out evaluation.

**Phase 5 — Search and ConfigurationIR**
Exhaustive small spaces, greedy baseline, beam, Pareto, constraints.

**Phase 6 — Composite synthesis**
Ownership, routing, update consistency and end-to-end design graph.

**Phase 7 — Code generation and verification**
Standalone C++20, compile and differential correctness.

**Phase 8 — Benchmark/research evidence**
Strong baselines, frozen experiments, statistical analysis.

**Phase 9 — Runtime adaptation and safe publication**
Drift, switching cost, migration, rollback, local data-plane mechanism.

**Phase 10 — Product/control plane/UI/AI**
Persistent API/CLI/UI and bounded evidence-grounded Copilot.

**Phase 11 — Security/portability/release hardening**
Fail-closed feature policy, cross-platform CI, evidence package and strict reproducibility.

**Phase 12 — Research/paper/patent/product validation**
Ablations, prior art, publication artifacts, pilot hypotheses; external outcomes stay external.

# XXV. Definition of done for the repository engineering prototype
A repository engineering completion claim is allowed only when:
- the exact head is known;
- all mandatory CI jobs on that head pass;
- machine-readable completion gates pass;
- the canonical 39-prompt corpus is present/indexed;
- README/AI start/index/checklist point to this true final directive;
- unsupported/future features remain explicitly blocked/research;
- known limitations are preserved;
- no quantitative/public novelty claim exceeds evidence.

# XXVI. What "complete" must never mean
It never means:
- no future bugs/features;
- every primitive known to computer science is implemented;
- fastest on every workload/machine;
- patent granted;
- paper accepted;
- security certified;
- production proven at scale;
- independent replication already performed.

Those are separate evidence events.

# XXVII. Final audit questions
Before release/demo/paper answer from repository evidence:
1. What exact workload semantics were declared?
2. What assumptions/defaults were applied?
3. What physical configuration was considered/chosen and why?
4. Which costs are measured vs predicted vs bootstrap?
5. What exact implementation/machine/distribution evidence supports the decision?
6. Did generated code compile and pass stateful correctness?
7. Were baselines semantically fair?
8. Can raw evidence regenerate analysis?
9. If adaptation occurred, was switching cost included and rollback safe?
10. Which features remain research/blocked?
11. Which public claims are authorized by packaged evidence?
12. Can another evaluator reproduce the claimed local result from the exact revision?

If any relevant answer is missing, the corresponding gate is incomplete.

# XXVIII. Autonomous execution protocol
For every dependency-ready gap:
1. inspect the exact current repository head;
2. inspect tests/contracts before changing behavior;
3. implement the smallest real vertical slice;
4. add focused failure-catching tests;
5. run integration/cross-platform CI as appropriate;
6. fix red jobs rather than weakening truth gates;
7. update capability/phase/docs only after evidence exists;
8. commit/push coherent changes;
9. record remaining limitation;
10. immediately continue to the next dependency-ready slice while the active session permits.

Never claim background work that is not actually scheduled/executing.

# XXIX. Repository/storage discipline
Git stores source, Markdown, schemas, scripts, tests and small fixtures/manifests. Avoid large binaries, dependencies, raw benchmark dumps, generated media, model checkpoints and duplicate documents. Heavy reproducible evidence belongs outside Git with content hashes/references.

# XXX. Final directive
MORPHEUS should be impressive because it can survive scrutiny, not because its language is grandiose. Optimize for a system where every selection can answer:

**Why this design? Is it correct? What evidence supports its performance? What would make the decision change? Can another evaluator reproduce it?**

When the choice is between another flashy feature and stronger evidence for an existing capability, prefer evidence. When the choice is between an LLM shortcut and deterministic semantics, prefer deterministic semantics. When the choice is between an enormous claim and a narrower claim the experiments actually prove, publish the narrower proven claim.

# END OF THE CANONICAL 39-PROMPT MORPHEUS ENGINEERING BIBLE