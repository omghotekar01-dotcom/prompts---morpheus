# MASTER PROMPT #32 — CROSS-PLATFORM PORTABILITY, TOOLCHAINS, ABI & FFI

## Mission
Make MORPHEUS portable without erasing platform differences. The system must preserve identical logical semantics while explicitly recording compiler, standard library, architecture and operating-system conditions that may alter measured performance or generated-artifact compatibility.

## Supported portability matrix
Treat support as a matrix, not a slogan. Track at minimum:
- Linux x86_64: GCC and Clang;
- Windows x86_64: MSVC;
- macOS ARM64/x86_64 where CI or validated hardware exists;
- Linux ARM64 where validated;
- Python versions explicitly tested by CI;
- Node/TypeScript versions used by the Command Center.

A platform is supported only to the level actually built/tested. "C++20" source compatibility is not automatically ABI compatibility.

## C++20 discipline
Use standard C++20 as the default portability substrate. Isolate compiler-specific intrinsics, attributes, pragmas and linker behavior behind small adapter layers. Avoid relying on undefined behavior, implementation-defined object layout or accidental standard-library internals.

## Compiler differences
Test and document differences in:
- diagnostic strictness;
- signed/unsigned behavior;
- alignment and padding;
- filesystem/path conventions;
- symbol visibility/export annotations;
- exception/runtime flags;
- optimization flags;
- sanitizer availability;
- floating-point optimization;
- atomics and memory-order implementation;
- vectorization and intrinsic naming.

Never compare benchmark numbers across toolchains without recording the exact compiler/version/flags.

## ABI contract
Generated native artifacts require an explicit ABI strategy. Prefer a narrow stable C ABI for cross-language or dynamically loaded boundaries. Do not expose unstable C++ STL types across a long-lived plugin ABI unless compiler/runtime identity is deliberately constrained.

Define versioned ABI structures with:
- ABI version;
- structure size;
- primitive/artifact identity;
- supported operation flags;
- creation/destruction hooks;
- query/update function pointers;
- error/status contract;
- ownership rules.

Reject incompatible versions fail-closed.

## Dynamic loading
Abstract `dlopen/dlsym/dlclose` and `LoadLibrary/GetProcAddress/FreeLibrary` behind one interface if native dynamic activation is implemented. Loading alone does not prove state migration or safe hot swap. Verify symbol contract, ABI version and artifact hash before use.

## Endianness and serialization
Persistent/on-wire formats must define byte order and schema version. Avoid dumping native structs directly. Use deterministic serialization for manifests/IR/evidence. Record numeric widths explicitly.

## Alignment and memory layout
Primitive internals may optimize for cache lines or SIMD, but public serialized formats must not depend on host padding. Use `static_assert` only for local implementation invariants and document when a layout is architecture-specific.

## Atomics and concurrency
Use the C++ memory model deliberately. Cross-platform concurrency tests should verify published invariants on GCC/Clang/MSVC. A test passing on x86 does not prove correctness on weaker memory-order architectures. Prefer simple acquire/release or mutex-based correctness before architecture-sensitive lock-free designs.

## Filesystem and paths
Use platform path APIs (`std::filesystem`, Python `pathlib`) and avoid hand-built separators. Validate canonical workspace containment. Account for Windows drive letters, reserved names and file locking. Temporary files must be safely scoped and cleaned.

## Process execution
Use argument arrays, never shell-constructed command strings. Windows and POSIX process termination/cancellation semantics differ; normalize observable worker states. Capture exit code, signal/status where available, wall time and bounded output.

## Build system
Use CMake with explicit minimum version and reproducible presets/toolchain configuration. Separate Debug/Release/sanitizer builds. Avoid absolute developer-machine paths in generated build files.

Recommended artifacts:
- `CMakePresets.json` for common profiles;
- toolchain files only where necessary;
- feature detection via `check_cxx_source_compiles` or compile definitions;
- generated config header for capabilities, not platform-name sprawl.

## Python boundary
Keep Python control-plane logic portable. Native extension dependencies must have wheels or a documented build path for supported Python/OS combinations. Do not force a Python downgrade merely to hide incompatible dependencies; either support the declared version or label it unsupported.

## FFI
For Python/Rust/other bindings, prefer the stable ABI layer rather than duplicating internal semantics. FFI tests must cover:
- lifecycle/ownership;
- null/error paths;
- large values and edge cases;
- exceptions not crossing C ABI;
- thread-safety contract;
- version mismatch rejection.

## Generated artifact compatibility
Every artifact manifest should record:
- target OS;
- target architecture;
- compiler ID/version;
- standard library/runtime when relevant;
- compilation flags;
- ABI contract version;
- source/config hashes.

An artifact verified on one environment is not silently portable to all environments.

## Determinism across platforms
Semantic hashes of platform-independent inputs must remain stable. Performance measurements need not match. If canonical JSON/YAML lowering differs across platforms, treat it as a correctness defect.

## CI strategy
Minimum gate:
- backend Python tests on Linux and Windows for declared Python versions;
- native C++ build/tests on GCC/Clang or GCC plus MSVC as available;
- sanitizer profile on supported compiler;
- frontend production build;
- generated artifact compilation on multiple toolchains;
- canonical IR/hash golden tests.

Expand to macOS/ARM only when infrastructure exists; do not mark those supported in advance.

## Portability acceptance gates
- no platform-specific code leaks into semantic layers without an adapter;
- canonical MWS/IR/config identities are stable across tested OSes;
- C++20 core builds/tests on declared toolchains;
- generated artifacts compile on declared toolchains;
- ABI version mismatch fails closed;
- filesystem/process behavior has platform-specific tests;
- release evidence records toolchain/platform identity.

## Truth boundary
Portability means tested compatibility on an enumerated matrix. It does not mean every compiler, OS, CPU, libc, Python distribution or embedded platform is automatically supported.