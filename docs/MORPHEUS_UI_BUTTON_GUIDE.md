# MORPHEUS screen and button guide

This guide describes the controls in the current MORPHEUS web application. A button can be disabled until its required input or evidence exists. Text such as “Synthesizing…” means the action is running.

## What MORPHEUS does

MORPHEUS takes a data/workload description, searches its registered data-structure implementations, estimates candidate costs, and can generate C++ for the selected design. A prediction is not a benchmark. Compilation, behavior verification, local measurement, and audit evidence are separate actions and results.

## Controls shared across screens

- **Sidebar screen names** — navigate to a screen; they do not run the action described by that screen. **Engineering** opens an advanced-tools index.
- **Describe / Design / Review / Verify** — the progress strip navigates to that part of the workflow. It does not itself execute the step.
- **The large “next action” button** — changes with the current state. It may ask you to connect, synthesize, assess confidence, measure finalists, verify code, or download a brief. Read the title above it to see which action is currently needed.
- **Refresh icon in the top bar** — asks the backend for its latest health/state. It does not restart the backend.
- **Retry** in an error banner — retries the connection when the backend is offline. **Dismiss (X)** hides the message; it does not fix the cause.
- **Settings** — opens local access, AI-provider, diagnostics, and example-workload controls.
- **Theme button** — switches the interface between its available appearance modes.

## Start

- **Build a student database / Run complete demo / Show generated C++ / Verify the code** — suggested prompts for the MORPHEUS Guide. They send a request to the guide; they are shortcuts, not separate screens.
- **Ask MORPHEUS** and the send-arrow button — submit your own question/request to the guide.
- **Example workload cards** — choose a synthetic, editable workload as a starting point. Selecting one prepares it; it does not prove real traffic or speed.
- **View all … examples / Show fewer examples** — expands or collapses the example list.
- **Run complete demo** — runs the guide's synthetic example flow. It does not analyze a CSV/XLSX you uploaded. Use **Real CSV Data** for that.
- **Review workload** — opens Workloads so you can edit the input.
- **Run synthesis** — asks the guide to run the current workload in the real backend.
- **Inspect C++** — opens Code Generator.
- **Check correctness** — asks the guide to verify generated code. It stays unavailable until a design exists and the backend is online.
- **See saved runs** — opens Experiment History.
- **Continue current design** — opens Synthesis Lab for the current result.

## Command Center

- **Diagnose my hot path** — opens Hot Path Doctor to compare your current structure with the operations in the current workload.
- **Edit workload / Open Workloads** — opens the workload editor.
- **Review confidence** — appears after a result exists and opens Decision Review.
- **Download decision brief** — downloads a summary of the current decision and its evidence; it does not deploy anything.
- **Workload preset cards (“Use this workload”)** — load a synthetic template for editing. They do not automatically claim that its assumptions match your application.
- **Run current workload** — sends the current MWS specification to the synthesis engine and produces a candidate result. It is not a performance benchmark.
- **Retry connection** — checks the backend again if the page reports it offline.

## Hot Path Doctor

- **What do you use today?** — select the existing container/structure to assess. This is a description, not a code change.
- **Diagnose this hot path** — evaluates the selected current structure against the declared workload and reports coverage gaps and a modeled recommendation.
- **Edit workload** — opens Workloads to change the operations or assumptions.
- **Did traffic invalidate the old decision? / Compare traces** (changes to **Result ready** after a result) — expands or collapses the optional drift-watch panel.
- **Load TXT/CSV/JSON** under **Baseline window** — loads an older key-traffic window that represents the accepted design.
- **Load TXT/CSV/JSON** under **Observed window** — loads a newer window from the same route.
- **Check recommendation validity** — compares the two supplied windows and re-evaluates the recommendation under the current constraints. It does not switch production traffic.
- **Clear windows** — clears both trace inputs and the displayed watch result.
- **Open human-controlled rollout & rollback ticket** — opens the evidence and safety checklist. It is a review document, not an automatic rollout.
- **Review observed workload in MORPHEUS** — copies the observed-window workload draft into Workloads for review; it does not deploy it.
- **Export freshness passport** — downloads the current decision-freshness evidence.
- **Keep current MWS** — closes the watch result and leaves the current workload unchanged.
- **Continue to Synthesis** — runs synthesis for the current workload when a recommendation is available.
- **Refine workload** — opens the workload editor without running synthesis.

## Real CSV Data

- **Choose your own dataset** — selects a local CSV or `.xlsx`. For Excel, MORPHEUS reads the active worksheet. The current limits are 15 MB, 100,000 records, and 64 columns.
- **Open [dataset] (CSV/XLSX)** — switches to a dataset saved in this browser session.
- **Forget from session** — removes that entry from the in-browser session list; it does not delete the original file from your computer.
- **Keep current pasted CSV in session list** — saves pasted CSV text in the current browser session list.
- **Analyze uploaded dataset using C++** — sends the selected records through the workbook/CSV adapter and native C++ profiler. It reports actual row count, fields, types, and distinct counts; it does not benchmark indexes.
- **Previous 20 / Next 20** — pages through the actual uploaded records.
- **Query real records using C++** — scans the uploaded records for the selected predicate and reports the real match count and sample rows. This is a reference scan, not an index-speed test.
- **Remove operation** — removes that workload route from the draft.
- **Add another operation** — adds a query or mutation route to describe expected usage.
- **Search and compare actual DSA candidates** — runs the bounded candidate search using your workload, constraints, and objective weights. Scores are modeled estimates.
- **Open this dataset's editable MWS** — transfers the dataset-derived schema to Workloads so you can edit the formal workload description.
- **Show all … evaluated candidates / Show top 25** — expands or collapses the candidate table.
- **Export real candidate comparison (JSON)** — downloads the current comparison, including the input/spec fingerprints and search evidence.
- **Download generated C++ header** — downloads the selected generated header. This action does not compile, behavior-test, or benchmark it.
- **Inspect generated C++ source** — expands the generated source inline; it does not execute it.

## Workloads

- **Start with a practical example** — loads a synthetic workload template into the editor; it does not run it.
- **Frequency sliders** — change the relative weight of each operation. The other weights are automatically adjusted so the total remains 100%. These are assumptions unless based on real trace data.
- **Run current workload** — performs synthesis on the current MWS.
- **See selected routes** — opens Synthesis Lab.
- **View C++ code / Open full code** — opens Code Generator when generated code is available.
- **Edit full specification** — expands the advanced YAML editor.
- **Import MWS** — loads a workload specification file into the editor.
- **Export MWS** — downloads the current workload specification.
- **Restore example** — replaces the current editor contents with the built-in example workload.
- **Open assistant** under the AI section — expands the optional natural-language workload drafter.
- **Generate validated MWS** — asks a configured language provider for a draft, then checks the draft with MORPHEUS's deterministic validator. Review the assumptions before using it. If the provider is remote, the description and optional base MWS are sent to it.
- **Configure AI** — opens Settings. AI is optional; the normal editor and synthesis flow work without it.
- **Apply to editor / Discard draft** — respectively copy the reviewed AI draft into the workload editor or throw the draft away.
- **Open assistant** under the access-trace section — expands the optional trace analyzer.
- **Analyze & preview draft** — computes descriptive key-frequency metrics and proposes workload semantics for review. It is not a statistical fit test or performance benchmark.
- **Clear trace** — clears the trace text and its draft.
- **Apply draft to workload / Keep current workload** — apply the reviewed trace-derived draft, or discard it and preserve the current workload.

## Synthesis Lab

- **Run current workload** — appears when no result exists; performs synthesis.
- **View generated C++ code** — opens Code Generator.
- **Run Full Verification** — runs separate compile and behavior checks on the generated artifact. A pass is evidence of those checks, not evidence of speed.
- **Review decision confidence** — evaluates whether uncertainty in the model makes the ranking sensitive. It is an engineering heuristic, not a statistical confidence interval.
- **Download decision brief** — saves the current decision summary and evidence.
- The operation-to-primitive diagram is informational; it shows which index type is assigned to each declared route.

## Decision Review

- **Assess decision confidence** — evaluates whether finalist model estimates overlap enough to justify more evidence.
- **Run bounded local measurement** — compiles/runs a limited measurement of finalists only when the assessment requests it and the workload is within the synchronous record limit. It measures on this machine; it is not a universal speed guarantee.
- If no design exists, **Run current workload** takes you back to synthesis.

## Experiment History

- **Resume run** — reloads a persisted run and its result into the current workspace.
- **Explain** — opens MORPHEUS Copilot with that run selected so you can ask about its stored evidence.
- **Open Workloads** — starts a new experiment when no saved runs are present.

## Engineering and its advanced screens

- **Advanced-tool cards (“Open”)** — navigate to Cost Model, Primitive Registry, Search Space, Code Generator, Machine Profiles, Runtime Observatory, or MORPHEUS Copilot.
- **Cost Model** — read-only modeled latency, memory, build, and update values. If there is no result, **Run current workload** creates one.
- **Primitive Registry** — read-only list of structures available to the current synthesis workspace and which ones were selected.
- **Search Space: Feasible / Pareto / All** — changes which returned candidates are displayed. “Pareto” shows candidates not dominated across the compared objectives. The screen currently displays up to 20 entries in this explorer.
- **Compare Search Quality** — compares bounded search with an exhaustive model-space oracle. It checks search fidelity within the model; it does not compare hardware timings.
- **Code Generator: Open verification** — navigates to Synthesis Lab. The code preview itself is read-only. If no code exists, **Run current workload** creates a design first.
- **Machine Profiles** — read-only local Python, operating-system, architecture, compiler, CMake, and calibration diagnostics.
- **Runtime Observatory** — read-only control-plane status, persisted run/artifact/evidence counts, and recent events.
- **MORPHEUS Copilot: Change run** — opens Experiment History to select another persisted run.
- **MORPHEUS Copilot: Ask** — answers a question from the selected run's deterministic evidence. Optional AI may improve wording but cannot create evidence or control actions. If the configured provider is remote, the question and evidence text may be sent to it; without a provider, answers are deterministic.

## Audit & Evidence

- This screen is mainly read-only: the integrity badge and event list are populated from the backend. A verified hash chain means the recorded evidence links validate; it does not prove a performance claim.
- If no evidence exists yet, **Run current workload** creates a real synthesis action that can be recorded.

## Settings, startup, and error screens

- **Use for this tab** — stores the entered control-plane key for this browser session/tab and uses it on protected API requests.
- **Clear session key** — removes that stored key from this tab.
- **Test AI provider** — checks a configured optional server-side language provider. It does not install or configure a provider.
- **Refresh backend** — refreshes backend status and diagnostics; it does not restart services.
- **Reset example workload** — replaces the current workload with the built-in example and opens Workloads. It does not erase saved runs.
- **Close (X)** — closes Settings without changing other workspace state.
- **Unlock & retry** — submits the configured access key and retries startup when protected access is required.
- **Retry initialization** — repeats the startup readiness checks.
- **Open degraded workspace** — lets you inspect the UI while startup is incomplete; synthesis and verification may remain unavailable.
- On the error screen, **Try again** retries rendering the failed screen and **Reload app** reloads the frontend page. Neither repairs an offline backend.

## A simple classroom route

For the uploaded 100,000-row demo workbook: **Real CSV Data → Choose your own dataset → Analyze uploaded dataset using C++ → add a point lookup on `SKU` or range on `Unit_Price_INR` → Search and compare actual DSA candidates → inspect/download the generated header → Synthesis Lab → Run Full Verification → Experiment History**. Explain that candidate scores are model estimates, while the profile and reference-query counts come from the uploaded file.
