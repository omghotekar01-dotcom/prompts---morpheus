# MORPHEUS screen and button guide

This guide describes the controls in the current MORPHEUS web application. A button can be disabled until its required input or evidence exists. Text such as “Synthesizing…” means the action is running.

## What MORPHEUS does

MORPHEUS takes a data/workload description, searches its registered data-structure implementations, estimates candidate costs, and can generate C++ for the selected design. A prediction is not a benchmark. Compilation, behavior verification, local measurement, and audit evidence are separate actions and results.

## Controls shared across screens

- **Home / Data / Workload / Results / Code & Verify / Learn DSA** — the six primary destinations. They navigate; they do not run the action described by the screen.
- **More tools** — opens the index for the guide, history, decision review, audit, and advanced engineering screens. It preserves those features without crowding the main path.
- **Data / Workload / Results / Code & Verify** — the workflow strip navigates between steps. It does not itself execute the step.
- **The large “next action” button** — changes with the current state. It may ask you to connect, synthesize, assess confidence, measure finalists, verify code, or download a brief. Read the title above it to see which action is currently needed.
- **Refresh icon in the top bar** — asks the backend for its latest health/state. It does not restart the backend.
- **Retry** in an error banner — retries the connection when the backend is offline. **Dismiss (X)** hides the message; it does not fix the cause.
- **Settings** — opens local access, AI-provider, diagnostics, and example-workload controls.
- **Theme button** — switches the interface between its available appearance modes.

## MORPHEUS Guide (More tools)

- **Build a student database / Run complete demo / Show generated C++ / Verify the code** — suggested prompts for the MORPHEUS Guide. They send a request to the guide; they are shortcuts, not separate screens.
- **Ask MORPHEUS** and the send-arrow button — submit your own question/request to the guide.
- **Example workload cards** — choose a synthetic, editable workload as a starting point. Selecting one prepares it; it does not prove real traffic or speed.
- **View all … examples / Show fewer examples** — expands or collapses the example list.
- **Run complete demo** — runs the guide's synthetic example flow. It does not analyze a CSV/XLSX you uploaded. Use **Real CSV Data** for that.
- **Review workload** — opens Workloads so you can edit the input.
- **Run synthesis** — asks the guide to run the current workload in the real backend.
- **Inspect C++** — opens Code & Verify.
- **Check correctness** — asks the guide to verify generated code. It stays unavailable until a design exists and the backend is online.
- **See saved runs** — opens Experiment History.
- **Continue current design** — opens Synthesis Lab for the current result.

## Home

- **Start with real data / Open Data** — opens the CSV/XLSX workspace. You choose the file; the app does not silently upload it.
- **Try a sample workload / Open Workloads** — opens the editable workload workspace.
- **View current results** — appears after a result exists and opens Results.
- **Sample workload cards (“Use this workload”)** — load an editable synthetic template and open Workload. They do not claim its assumptions match your application.
- **Browse all workloads** — opens the full workload editor and its complete example list.
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

- **Start with a practical example** (selector) — loads one of the synthetic workload templates. It changes the current editor and clears the current result/verification; it does not delete saved runs or run synthesis.
- **Current / custom workload** — keeps the specification currently in the editor.
- **Workload / Records / Memory budget** — read-only summary of values in the current MWS.
- **Operation frequency sliders** — change the percentage for an existing operation route. The other routes are rebalanced proportionally so the total stays 100%. These percentages describe assumed traffic unless they came from real traces. Changing them invalidates the displayed current result and verification.
- **Run current workload** — submits the current MWS and selected search strategy to the real backend. While running, the button reads **Synthesizing…** and is disabled. A successful run opens Results and produces the candidate output; it does not benchmark or edit the uploaded data. If the backend is offline, it reports an error instead.
- **Ready when you are** — empty-state message shown before synthesis; it is not a button or a result.
- **See selected routes** — opens Results to show which structure was assigned to each operation.
- **View C++ code / Open full code** — opens Code & Verify when generated code exists; unavailable until synthesis returns code.
- **Edit full specification** — expands the advanced MWS YAML editor. Use it to change schema, record count, routes/fields, selectivity, constraints, or objective settings. The visual sliders only adjust weights for routes that they can parse; unsupported imported specs remain editable here.
- **Search** selector — chooses Auto, Exhaustive, Beam, or Greedy search for the next run. It does not execute search by itself.
- **Import MWS** — reads a YAML/JSON/text workload file into the editor (maximum 256 KB). Import replaces the current draft and clears its current result/verification.
- **Export MWS** — downloads the current specification as a `.mws.yaml` file.
- **Restore example** — replaces the current editor with MORPHEUS's built-in example and clears the current result/verification. It does not remove persisted runs.
- **Open assistant** under **OPTIONAL AI ASSISTANT** — expands the natural-language draft panel; AI is not required for normal editing or synthesis.
- **Use the current MWS as a base** — asks the optional drafter to preserve the current specification unless the description requests changes.
- **Generate validated MWS** — requests a draft from a configured provider, then validates it with MORPHEUS's parser. It is disabled without a configured provider, a description, or while drafting. A remote provider receives the description and, if selected, the base MWS.
- **Configure AI** — opens Settings if no provider is configured.
- **Apply to editor / Discard draft** — apply a reviewed validated draft to the current editor (clearing its result/verification), or discard the draft without changing the current MWS.
- **Open assistant** under **OPTIONAL REAL-WORLD INPUT** — expands the access-trace analyzer.
- **Target query** — selects which existing query route the trace should inform.
- **Load trace file / Integer access keys** — loads a local TXT/CSV trace (maximum 2 MB) or accepts pasted integer keys. This panel analyzes a finite window; it does not monitor production traffic.
- **Analyze & preview draft** — computes descriptive key-frequency metrics and proposes a workload draft. It is not a statistical fit test or performance benchmark; it is disabled until there is text and at least one query route.
- **Clear trace** — clears the pasted text and any proposed trace draft.
- **Apply draft to workload / Keep current workload** — apply the reviewed trace-derived draft to the editor (clearing current result/verification), or discard the draft and preserve the current MWS.

**Important distinction:** Data describes the uploaded records and can help you choose real columns/values. Workload describes the operations your application is expected to perform on those records. Uploading a file does not infer operation frequencies. To add or remove a route, use the Data workspace controls or edit the MWS under **Edit full specification**; the visual workload sliders only rebalance existing routes.

## Synthesis Lab

- **Run current workload** — appears when no result exists; performs synthesis.
- **Open Code & Verify** — opens the generated artifact screen.
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

## Code & Verify

- **Run Full Verification** — runs separate compile and behavior checks on the real generated artifact. A pass is evidence of those checks, not evidence of speed.
- **View synthesis results** — returns to Results.
- The generated C++ preview is read-only. If no artifact exists, use **Run current workload** from Workload or Results first.
- The verification card shows actual gate results only after the backend completes those checks.

## Learn DSA

- **Try a workload** — opens Workload so you can select or edit an operation mix.
- **Open Code & Verify** — opens the generated-code and verification screen.
- The cards explain the implemented Robin Hood hash index, B+ tree, sorted array, mutable prefix trie, compressed bitmap, and CSR graph. Complexity is presented as algorithmic intuition, not a measured result.
- The language cards distinguish the C++20 engine, Java 17+ deterministic scorer, and separate C11 binary-search lesson.

## More tools and advanced screens

- **MORPHEUS Guide / Hot Path Doctor / Decision Review / Saved runs / Audit & Evidence** — open the named workflow or evidence screen.
- **Advanced-tool cards (“Open”)** — navigate to Cost Model, Primitive Registry, Search Space, Machine Profiles, Runtime Observatory, or MORPHEUS Copilot.
- **Cost Model** — read-only modeled latency, memory, build, and update values. If there is no result, **Run current workload** creates one.
- **Primitive Registry** — read-only list of structures available to the current synthesis workspace and which ones were selected.
- **Search Space: Feasible / Pareto / All** — changes which returned candidates are displayed. “Pareto” shows candidates not dominated across the compared objectives. The screen currently displays up to 20 entries in this explorer.
- **Compare Search Quality** — compares bounded search with an exhaustive model-space oracle. It checks search fidelity within the model; it does not compare hardware timings.
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

For the uploaded 100,000-row demo workbook: **Data → Choose your own dataset → Analyze uploaded dataset using C++ → add a point lookup on `SKU` or range on `Unit_Price_INR` → Search and compare actual DSA candidates → inspect/download the generated header → Results → Code & Verify → Run Full Verification → More tools → Saved runs**. Explain that candidate scores are model estimates, while the profile and reference-query counts come from the uploaded file.
