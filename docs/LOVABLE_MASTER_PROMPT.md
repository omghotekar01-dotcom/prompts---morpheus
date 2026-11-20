# MORPHEUS — Lovable master prompt

Copy the prompt below into Lovable together with the MORPHEUS repository. The repository is the source of truth for current behavior; this prompt defines the simpler product experience.

---

## COPY FROM HERE

You are a senior product designer and full-stack engineer. Redesign and implement the MORPHEUS web experience using the repository I provide. First inspect the existing frontend, API client, backend routes, tests, and documentation. Then make the actual website coherent, polished, simple to demonstrate, and connected to the existing system.

Do not return only a mockup or a proposal. Implement the frontend changes in the existing project. Preserve working features and backend contracts. Do not replace real behavior with demo-only responses.

### 1. Product truth: what MORPHEUS is

MORPHEUS is a workload-aware data-structure selection and synthesis workbench for software engineers and DSA learners. A user describes or uploads data, declares the operations an application performs and their expected frequency, and sets constraints. MORPHEUS evaluates its registered data-structure implementations, explains the eligible candidates, estimates their costs, and can generate a C++20 physical-plan artifact for inspection and verification.

The central user journey is:

1. Supply a dataset or choose a clearly marked synthetic example.
2. Describe the data fields and expected operations (lookups, ranges, filters, prefixes, and supported mutations).
3. Set workload weights and constraints.
4. Compare the feasible evaluated data-structure candidates and understand why they were included or excluded.
5. Inspect generated C++20, run its compile and behavior checks, and review the saved evidence.

Be precise about results:

- A profile's row count, field types, and distinct-value counts come from the supplied data.
- A reference query reports matches found by scanning supplied records; it is not an index benchmark.
- Candidate latency, memory, and scores are modeled estimates unless the screen explicitly presents valid measurement evidence.
- Compile/behavior verification proves only the checks actually run; it does not prove a speedup.
- A "best" candidate means the best feasible candidate MORPHEUS evaluated for the submitted model, constraints, and search budget—not a universally fastest structure.
- Operation weights are user assumptions unless derived from a real workload trace. A dataset alone does not reveal how an application will query it.
- Never invent a winner, timing, verification pass, telemetry, record, or evidence to make the screen look complete.

### 2. Accurate implementation and language layers

Keep the existing architecture and use the repository to confirm exact file names, behavior, and routes:

- **React + TypeScript frontend:** user interaction, forms, navigation, state, and result presentation. Reuse the current API client and existing shared types.
- **Python FastAPI control plane:** HTTP validation, workload orchestration, data adapters, cost/scoring compatibility, code-generation orchestration, and evidence/run APIs.
- **C++20 engine:** native dataset profiling and bounded configuration-space search; the actual registered physical structures include Robin Hood Hash, B+ Tree, Sorted Array, Radix Trie, Compressed Bitmap, and CSR Graph. Which structures are eligible depends on operation and field semantics.
- **Java 17+ scorer:** evaluates weighted modeled objectives and constraints when compiled and enabled. It scores modeled inputs; it is not itself a hardware benchmark.
- **C11 learning example:** a separate, small binary-search lesson. Do not imply it is the C++ synthesis engine.
- **Persistence/evidence:** saved runs, artifacts, and the integrity ledger belong to the existing backend. Display their real status and errors.
- **Optional AI:** may draft or explain language when configured. It is not required for normal synthesis, must not choose results in place of the engine, and must not create evidence or control actions.

The repository is transitioning responsibilities from Python to native code. Do not claim the whole product is already implemented only in C++/Java/C. Do not claim machine learning is responsible for data-structure selection unless the actual inspected code proves that for the specific feature.

### 3. Product and audience

Design for two overlapping audiences:

- A student/teacher who needs to understand and demonstrate DSA concepts in plain language.
- An engineer who wants a transparent, evidence-aware workload-specific design workflow.

Make the first view understandable in under a minute. Explain unfamiliar terms inline (short tooltips or “What does this mean?” disclosures), not with paragraphs of jargon. Keep algorithm details available without making every visitor navigate a research console.

Suggested product name and short description:

**MORPHEUS — Workload-aware DSA Workbench**
“See how your data is used. Compare implemented data structures. Inspect and verify the generated C++.”

### 4. Information architecture: simple first, advanced when needed

Use a small primary navigation:

1. **Home** — what MORPHEUS does, system connection state, and one obvious “Start a demo” action.
2. **Data** — upload the supplied demo workbook or a user's own supported data; show the actual profile and preview.
3. **Workload** — choose operations/fields, set relative traffic weights and constraints, and run synthesis.
4. **Results** — recommendation, alternatives, per-operation eligibility, rejection explanations, search coverage, and clear evidence labels.
5. **Code & Verify** — inspect generated C++, run compile/behavior checks, and show exactly which gates passed.
6. **Learn DSA** — a compact teaching area explaining the structures actually implemented and the separate C and Java roles.

Put **Saved Runs** and secondary engineering screens under a tidy **More tools** destination rather than showing all of them as equal-priority navigation. Preserve useful current advanced functions such as the MORPHEUS Guide, Decision Review, Hot Path Doctor/Watch, Search Space, Cost Model, Primitive Registry, Machine Profiles, Runtime Observatory, Audit & Evidence, and MORPHEUS Copilot. Group them by purpose and label them optional or advanced; do not delete them or put them in the first-run path.

Avoid duplicate destinations, multiple competing “start” pages, and repeated versions of the same action. One clear primary button per step is enough. Secondary actions should be visually quieter.

### 5. Main screen behavior and content

#### Home

- One-sentence product explanation and a simple “How it works” sequence: **Data → Workload → Compare → Verify**.
- Offer two clear starting points: **Start with real data** or **Try a sample workload**. Do not silently select or upload a local workbook.
- Show only a few sample workload shortcuts on Home; provide **Browse all workloads** for the complete editable example list.
- Show whether the local backend is online, locked, or offline. A status refresh must refresh status only; it must not pretend to restart services.
- Show a short “What is real vs estimated?” note.
- Mark every bundled example and the included 100,000-row inventory workbook as **synthetic demo data**.

#### Data

- Support the formats and limits actually implemented in the repository. The current UI supports CSV and `.xlsx`, reads the active worksheet, and enforces 15 MB, 100,000 records, and 64 columns; verify current code before presenting these as immutable.
- Clearly show the selected file name, active worksheet, row count, columns, detected types, distinct counts, and a paged preview after actual profiling.
- Explain that the workbook is sent to the configured/local MORPHEUS API for processing; do not claim that uploaded bytes never leave the browser.
- Do not save an upload permanently or imply it is stored unless the existing implementation says so.
- Provide helpful errors for unsupported/oversized files and a retry path.

#### Workload

- Use simple, labeled controls first: operation, field, relative frequency, and any required predicate/range.
- Use sliders or number inputs with clear units and explain that frequency values are assumptions unless the user supplied genuine trace evidence.
- For a multiple-operation workload, keep weights understandable and show their total.
- Put advanced MWS YAML/JSON import/export, search strategy, candidate budget, and detailed objective weights in a collapsible **Advanced settings** area.
- Provide a few editable presets, labeled synthetic. Selecting a preset must not be presented as running it.
- Never silently repair invalid fields or relax hard constraints. Display validation errors beside the relevant control.
- Optional AI drafting and access-trace analysis must be clearly optional, collapsible, reviewable before applying, and accompanied by honest privacy/evidence caveats.

#### Results

- Lead with one human-readable summary: **best feasible evaluated plan** or **no candidate met the constraints**.
- Show why the candidate fits, which operation routes use which structure, and why competing structures were excluded.
- Visually label **Model estimate**, **Measured on this machine**, **Compile check**, and **Behavior check** as different kinds of evidence. Never style an estimate as a measurement.
- Show the search method, how many configurations were evaluated, theoretical search size where available, and whether the search was truncated.
- Offer a compact comparison first; put full ranked candidates, Pareto details, and search-quality analysis in an expandable advanced view.
- Explain constraints in plain language, including why a fast candidate may be rejected for memory or capability limits.

#### Code & Verify

- Show the actual generated C++ returned by the existing backend; do not use placeholder code.
- Distinguish **Generated**, **Compile passed/failed**, and **Behavior passed/failed**.
- Make **Run verification** the primary action after code generation. Clearly state that passing those gates is not a speed claim.
- Keep any benchmark/local measurement action separate, labeled with its machine and measurement limits.
- Allow download only for a real generated artifact and show its filename and relevant candidate/run identity.

#### Learn DSA

Use short, visual explanations tied to real project behavior:

- Robin Hood Hash — a hash-based option for exact lookups; explain collision/probe behavior at a beginner level.
- Sorted Array and B+ Tree — ordered structures useful for range-oriented access where supported.
- Mutable Prefix Trie — prefix-oriented string lookup as implemented in the current mutable-index adapter.
- Compressed Bitmap — equality/filter workloads where supported.
- CSR Graph — graph representation/traversal in the advanced workload context.
- Binary search in C11 — a standalone algorithm lesson with user-provided input, complexity, and boundary cases; do not claim this is the synthesis engine.
- Java scorer — explain how candidate objectives/constraints are scored when the Java implementation is enabled; its inputs are model estimates, not measured latencies.

Only describe algorithms and capabilities found in the repository. Make complexity statements accurate and appropriately qualified. A learning card may link to source code or a simple example, but must not claim an unsupported operation is implemented.

### 6. Visual design system

Create a calm, professional, modern engineering/education interface—not a dense enterprise cockpit:

- Follow the design direction described by the `morpheus-workbench` reference README: quiet iOS-inspired composition, softly rounded cards, subtle dividers, segmented controls where useful, crisp typography, and restrained cool accents. Treat it as visual guidance, not a finished application to copy; keep MORPHEUS's real content and current design tokens.
- Clear page title, one short explanatory sentence, and a visible next action.
- Generous whitespace, readable typography, strong contrast, restrained color, and a consistent grid.
- Use a small palette: dark navy for structure, one cool accent (teal or blue) for actions, neutral backgrounds, and semantic colors only for status.
- Use simple diagrams for the pipeline and operation-to-structure routing. Avoid decorative charts that do not encode actual data.
- Use concise cards, progressive disclosure, and one primary button per panel. Avoid a wall of metrics, repeated navigation, unnecessary badges, and giant forms.
- Design mobile and desktop layouts; tables must scroll or reflow without hiding important columns.
- Meet keyboard, focus, contrast, screen-reader label, and reduced-motion accessibility expectations.
- Use the project's installed UI/dependency conventions where practical. Do not add a large UI library solely for decoration.

### 7. Interaction rules

- Every visible button must have a real action. No dead controls, decorative links styled as buttons, fake progress, or success-shaped fallback.
- Use action labels that say what happens: **Analyze dataset**, **Run synthesis**, **Run verification**, **Export results**.
- Use confirmation only for destructive actions. Make clear whether a button navigates, expands a section, downloads a file, or runs a backend action.
- Show loading state, disable duplicate submissions, preserve input on recoverable errors, and present actionable error messages.
- Do not make a disabled button look broken: explain the missing prerequisite next to it.
- Preserve the current workload and input when navigating between screens.
- On refresh/restart, be explicit about what is session-only and what is persisted by the backend.
- Never automatically deploy, switch production traffic, mutate an uploaded dataset, or claim production authorization.

### 8. Engineering constraints for implementation

- Treat this repository's current source and API client as authoritative. Reuse the API functions/types in `frontend/src/api.ts` and the real FastAPI routes; inspect them rather than guessing endpoint names or response shapes.
- Keep real synthesis, CSV/XLSX profiling, generated-code, verification, saved-run, and evidence flows working. If an endpoint is unavailable, show an honest unavailable state rather than a mock result.
- Do not change backend contracts to suit a mockup. Do not replace the real engine with hardcoded algorithm winners, sample results, or front-end-only calculations.
- Keep example data visibly separate from user-uploaded data. The example is not evidence about the user's file or actual application.
- Keep changes focused, typed, and consistent with the existing React/TypeScript code. Avoid `any`, broad exception swallowing, and hidden default values.
- Inspect and update existing tests for changed behavior. Run the smallest relevant frontend build/type check and tests; report what passed and what could not be run.
- Do not rewrite or delete the C++20 engine, Python API, Java scorer, C lesson, existing evidence model, or advanced features as part of a frontend redesign.

### 9. Definition of done

The implementation is complete only when:

1. A new user can find the demo and explain MORPHEUS in one sentence.
2. The included synthetic 100,000-row workbook can be selected and profiled using the real API/native profiler.
3. A user can set an operation mix, run the real candidate search, and understand the winner or infeasibility.
4. The UI never confuses predicted costs with measured results.
5. Generated C++ is real output, and verification status is shown only after actual checks run.
6. Main navigation is small and understandable, while advanced current features remain reachable.
7. All visible buttons work, disabled states explain why, and errors do not erase the user's work.
8. The experience is responsive, accessible, and build/tests pass.

Before finishing, summarize the screens changed, APIs reused, real flows tested, and any remaining limitations. Do not claim unrun tests, measurements, or capabilities.

## COPY TO HERE
