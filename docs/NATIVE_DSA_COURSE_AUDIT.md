# MORPHEUS DSA course audit and native empirical cost path

## What is implemented (do not overclaim)

- Six real **C++20** structures: Robin Hood Hash, B+ Tree, Mutable Sorted Array, Radix Trie, Adaptive Bitmap, and CSR Graph. They are in the corresponding files under core/include/morpheus/.
- CSV profiling/reference query scans and bounded exhaustive/beam/greedy search execute in compiled **C++20** with the native Windows engines enabled.
- Hard constraint and objective scoring can run in compiled **Java 17+** (PlanScorer).
- New experimental **C++20 empirical ridge-regression cost model** in empirical_cost_model.hpp; standalone training/prediction process in empirical_cost_cli.cpp. It **does not** ship a trained production model or make up benchmark data.
- Implemented capability filtering for the six registered algorithms executes in **C++20** when launched in native mode through morpheus_native_capabilities. Python remains a transport and metadata/fallback layer.
- Existing production cost modeling, some ranking, generated header construction, and API orchestration **still run in Python**. This feature branch does NOT establish an exclusively native DSA decision pipeline. Python is still required to run the website.

## Where the six structures are

| Implementation | File | Typical queries |
| --- | --- | --- |
| Robin Hood Hash | core/include/morpheus/structures.hpp | exact lookup |
| B+ Tree | core/include/morpheus/bplus_tree.hpp | ordered/range, equality, mutations |
| Sorted Array | core/include/morpheus/mutable_indices.hpp | ordered/range |
| Radix Trie | core/include/morpheus/mutable_indices.hpp | string prefix |
| Adaptive Bitmap | core/include/morpheus/compressed_bitmap.hpp | equality filters |
| CSR Graph | core/include/morpheus/csr_graph.hpp | graph traversal |

Only implemented and tested algorithms should be advertised. Algorithm capabilities and protocol validation are necessary fixed *software definitions*, not hardcoded answers. Unsupported operation–index pairs should be rejected.

## Native data-driven model: what it does

This model is **trained only on externally supplied measured per-operation latency samples**. It learns separate models per physical primitive and operation. Input features are:

1. row count (log2-scaled);
2. distinct-value cardinality (log2-scaled);
3. query selectivity;
4. updates per second (log1p-scaled).

A ridge-regression model in C++ fits these features and predicts latency in microseconds. Fewer than eight samples per primitive/operation cannot produce a model. Predicting outside the range of its training inputs is explicitly refused. The CLI never uses a hardcoded predicted winner.

### Build and test on Windows (Visual Studio C++ toolchain)

From the repository root:

~~~powershell
cmake -S core -B build/native-dsa
cmake --build build/native-dsa --config Release --target morpheus_empirical_cost morpheus_empirical_cost_tests
ctest --test-dir build/native-dsa -C Release -R morpheus_empirical_cost_tests --output-on-failure
~~~

The executable is generally build/native-dsa/Release/morpheus_empirical_cost.exe on MSVC, or build/native-dsa/morpheus_empirical_cost with a single-config compiler.

### Input protocol

Input to the C++ CLI on standard input:

~~~text
MORPHEUS_EMPIRICAL_COST_V1
S
primitive operation rows cardinality selectivity update_rate actual_measured_latency_us
... S rows ...
Q
primitive operation rows cardinality selectivity update_rate
... Q queries ...
~~~

The example above is a **schema specification, not demonstration measurements**. Use actual records exported from repeatable compiled C++ benchmarks with their source, compiler, machine, workload, warmup and repetition evidence. Do not invent training labels for a research paper.

The output protocol begins with OK Q, followed by:
- P predicted_latency_us training_rmse_us training_sample_count
- U NO_MATCHING_TRAINED_MODEL, U OUTSIDE_MEASURED_FEATURE_RANGE or U NONPOSITIVE_MODEL_PREDICTION

**Training RMSE is not held-out accuracy.** Measure MdAPE, ranking agreement and regret on a separate held-out set before claiming model quality. The model is experimental and not a complete predictor for categorical skew, hardware cache effects or prefix length.

### Optional API integration

Store the protocol header, S and S measured rows (do not include Q) in a UTF-8 file. Then set:

~~~powershell
$env:MORPHEUS_EMPIRICAL_COST_TRAINING_FILE = "C:\path\to\real_benchmark_measurements.txt"
$env:MORPHEUS_EMPIRICAL_COST_EXECUTABLE = "C:\path\to\morpheus_empirical_cost.exe"
# Optional: refuse bootstrap estimates when calibration and learned evidence are missing
$env:MORPHEUS_REQUIRE_EMPIRICAL_COST = "1"
.\START-MORPHEUS.bat
~~~

For a supported workload, the Python API transports metrics to the compiled C++ process, and returned predictions are labeled NATIVE_CPP_LEARNED_USER_MEASUREMENTS. If a precise matching calibration measurement exists, the calibrated path still takes precedence. If the model is untrained, out of its range, or lacks the required selectivity, default mode transparently retains the *labeled bootstrap estimate*, while strict mode rejects it.

There is **no bundled training data** and therefore no guaranteed trained prediction until the researcher collects and provides measurements.

## Generated C++ headers

Real CSV Data calls backend/app/artifact_codegen.py to generate headers from the selected configuration. Those headers wrap the real C++20 structures and can be used in a standalone C++ application when compiled with core/include, but downloading them does not compile or test that exact generated artifact. Use the explicit compile/behavior gates or build a driver and test every query and mutation path.

**Important gap:** Header construction still uses Python templates. A follow-up migration is required to implement this generation in C++/Java. It would be dishonest to call this part native now.

## Still required to meet a strict C/C++/Java-only DSA course mandate

1. Move the remaining catalog metadata and implementation declarations into C++ as the single authoritative manifest; native C++ eligibility decisions now run in the primary Windows path, but the Python registry still supplies metadata and fallback.
2. Port all cost estimation, calibrated lookup and memory accounting into C++/Java. The new empirical cost learner is opt-in, not a complete replacement for cost_model.py.
3. Move full candidate evaluation, Pareto extraction, winner selection and workload orchestration out of Python.
4. Port generated header code construction to C++20 and verify generated code for the user-supplied input.
5. Build a Java-based control plane when Python must be only optional ML training or HTTP transport.
6. Collect genuine benchmark training data, held-out validation and local complete CP walkthrough proof.

### Native capability-filter verification

~~~powershell
cmake -S core -B build/native-dsa
cmake --build build/native-dsa --config Release --target morpheus_native_capabilities morpheus_native_capabilities_tests
ctest --test-dir build/native-dsa -C Release -R morpheus_native_capabilities_tests --output-on-failure
~~~

The Windows launcher now requires the SHA-256-verified capability executable. Its native transport protocol processes the current operation, column type and cardinality. No recorded dataset value or preselected index is embedded in the capability rules.

Do not label the 39/39 engineering completion counter as proof of these specific language migration goals or as research publication evidence.
