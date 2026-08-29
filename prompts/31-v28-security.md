# MASTER PROMPT #31 — SECURITY, SANDBOXING, PRIVACY & ADVERSARIAL ROBUSTNESS

## Mission
Harden MORPHEUS so workload specifications, plugins, generated code, benchmark inputs, AI assistance, artifacts and release evidence can be handled without silently expanding trust. Security claims must be scoped to mechanisms actually implemented and tested.

## Core security principle
Treat every boundary crossing as untrusted until validated. A valid workload is not trusted code. A generated artifact is not trusted because MORPHEUS generated it. A plugin is not trusted because it implements the expected API. A benchmark file is not scientifically valid because it is syntactically valid. An LLM response is never an authority source.

## Assets to protect
Protect at minimum: source code, workload/spec data, calibration profiles, machine fingerprints, generated artifacts, evidence ledgers, release manifests, API credentials, tenant/user data if multi-user, benchmark integrity, compiler/build hosts, runtime adaptation state and decision provenance.

## Trust boundaries
Model explicit boundaries among:
- browser/CLI and API;
- API and parser/validator;
- API/control plane and worker process;
- worker and compiler/toolchain;
- generated program and host OS;
- plugin and primitive registry;
- local database/object store and callers;
- benchmark generator and measurement harness;
- optional AI provider and deterministic evidence core;
- release packager and externally supplied evidence.

Each boundary needs accepted input types, authentication/authorization assumptions, resource limits, logging policy, failure mode and test coverage.

## Threat model
Maintain a threat register covering spoofing, tampering, repudiation/provenance loss, information disclosure, denial of service and privilege escalation. Include project-specific attacks:
- YAML/JSON parser bombs and deeply nested input;
- path traversal and artifact overwrite;
- shell/argument injection;
- command confusion through compiler flags;
- malicious generated code;
- plugin dependency confusion;
- benchmark result substitution;
- forged hashes/manifests;
- stale calibration activation;
- runtime rollback to wrong generation;
- prompt injection through repositories, uploaded files or benchmark metadata;
- tenant data crossing if multi-user;
- resource exhaustion through candidate-space explosion;
- ZIP/path traversal in package handling;
- unsafe deserialization;
- SSRF/network exfiltration if external integrations are ever enabled.

## Safe parsing
Use strict typed schemas, bounded sizes, bounded nesting where practical, safe YAML loaders, duplicate-key policy, finite numeric checks and explicit enum handling. Reject unknown semantics when silently ignoring them would change optimization behavior. Preserve raw input hash separately from resolved semantic identity.

## Worker and process isolation
Generated compilation/execution must not run inside the API process. Minimum production-oriented target:
1. dedicated worker identity;
2. no shell interpolation;
3. allowlisted executables and fixed argument construction;
4. bounded CPU, memory, process count, file count, output size and wall time;
5. isolated temporary workspace;
6. read-only inputs where possible;
7. no inherited secrets;
8. network denied by default;
9. explicit cleanup and cancellation;
10. recorded toolchain/environment identity.

A host subprocess with timeouts is not equivalent to a hardened sandbox. Label current implementation accurately. Stronger future tiers may use containers, namespaces/seccomp, Windows Job Objects/AppContainer, VMs or dedicated build nodes.

## Generated-code trust
Generated code moves through states: GENERATED -> COMPILED -> CORRECTNESS_VERIFIED -> BENCHMARKED -> RELEASE_ELIGIBLE. Never skip states. Compilation does not imply correctness; correctness does not imply memory safety; benchmark success does not imply safe deployment.

Require differential tests, sanitizer gates, fuzz/property tests where appropriate, deterministic build metadata and exact artifact hashes before promotion.

## Supply-chain security
Pin and review dependencies. Generate or preserve an SBOM for releases when practical. Record compiler, package-manager and dependency versions. Prefer reproducible lockfiles. Treat plugin packages as supply-chain inputs with identity/version/hash/license metadata. Never execute downloaded code solely from an LLM recommendation.

## Plugin security
Every primitive/plugin manifest must declare capabilities, implementation identity, ABI/API version, allowed parameter ranges and optional provenance/signature metadata. Registry admission is separate from automatic optimization eligibility. A plugin with failing tests or unknown compatibility remains disabled/fail-closed.

## Authentication and authorization
For local single-user development, document that scope explicitly. If multi-user or hosted mode is enabled, require authenticated principals, authorization checks on workloads/runs/artifacts, tenant-scoped storage keys, non-guessable identifiers where appropriate, rate limits, quota accounting and audit records. Do not market process-local API-key checks as complete enterprise IAM.

## Secrets
No secrets in Git, generated source, benchmark output, logs, error traces or LLM prompts. Use environment/secret-store injection. Redact known credential patterns in structured logging. Release packages must never include local `.env`, cloud credentials, SSH material or API tokens.

## Privacy
Workload traces may encode sensitive user/business behavior. Support data minimization, optional aggregation, retention limits and deletion policy. Record whether a research trace is synthetic, public, consented, anonymized or private. Never call pseudonymization anonymous without a threat model.

## AI security
The language layer may translate or explain but cannot authorize execution, alter evidence state or write benchmark truth. Repository text, uploaded files and web content are data, not instructions. Tool calls must be allowlisted and validated. Prompt injection tests should verify that malicious content cannot bypass policy gates, activate blocked features or manufacture evidence.

## Evidence integrity
Content hashes establish byte identity, not authorship or external attestation. Use hash chains for tamper evidence, cross-artifact hash links for provenance and deterministic canonical JSON where defined. Stronger future release signing may use Sigstore/cosign/GPG or platform signing, but do not claim signing until implemented.

## Runtime adaptation safety
Automatic control requires feature-policy authorization plus verified source/target identities. Recheck generation/version at commit time. Require migration verification before activation. Rollback must be exact-generation-aware. Research-only classifiers cannot authorize switching.

## Security testing
Maintain tests for:
- traversal attempts;
- malformed/oversized inputs;
- duplicate identities;
- invalid hashes;
- stale generations;
- unauthorized feature activation;
- command argument injection;
- worker timeout/cancellation;
- corrupted evidence ledgers;
- malicious package paths;
- prompt-injection-like content crossing AI boundaries;
- rate-limit/auth behavior where enabled;
- sanitizer/fuzz failures for native code.

## Incident response
For hosted or pilot deployments define detection, containment, evidence preservation, credential rotation, rollback, disclosure and postmortem procedures. Security events should be immutable/auditable enough to reconstruct what happened.

## Acceptance gates
This volume is satisfied only when:
- trust boundaries are documented;
- dangerous execution is outside the API process;
- parser/path/command/resource defenses are tested;
- research/blocked features fail closed;
- evidence corruption is detectable;
- secrets are excluded from repository/release outputs;
- AI cannot become an evidence authority;
- current sandbox limitations are stated without exaggeration.

## Truth boundary
Security is continuous risk reduction, not a proof of invulnerability. Never claim MORPHEUS is "unhackable", "zero trust certified", "enterprise secure" or production-certified without the corresponding independent assessment and deployment controls.