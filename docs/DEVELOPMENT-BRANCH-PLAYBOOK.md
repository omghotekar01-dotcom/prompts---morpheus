# MORPHEUS Development Branch Playbook

## Branch roles and initial baseline

- `main` is the stable release branch. Do not develop directly on it.
- `morpheus-next` is the persistent integration and day-to-day development branch.
- The branch was created on 2026-11-12 from `feat/dsa-native-core-migration-20261102` at `7fa06c93b899c106b212faee4b6b28a40ebd0f22`.
- `feat/native-cpp-dsa-search-20261025` at `a4ec60f81a7f3e42c100edda5eaa5745413b9653` is an ancestor of the selected DSA branch, so it contributes no separate commits to integrate.
- The latest `origin/main` at setup was `07f36c25fd2c38f9c8d4c0982ecfab18b4ada2d7`. It was merged without conflicts; the merge commit is `d23f497b8a0f63048e084e816bc598e3bc69be4e`.
- Audited and merged the unique trace-import race guard and real-export intake hardening from `fix/trace-import-race-guard` and `fix/trace-intake-real-export-hardening` (merge commits `371de7d7cfd888604ef3af34c08cbd6c04ae35fb` and `fbcca76d06a5b04114dce27b071894f7846028f6`).
- The native C++ branch is an ancestor of the selected DSA branch. The reference-workbench, chat-onboarding, and readability branch content is already represented in the selected tree; their older branch heads were not merged over the newer integration tree.
- The original `main` branch was not changed.

The local/remote recovery refs created before integration:

| Ref | Commit |
|---|---|
| `backup/morpheus-main-2026-11-12` | `07f36c25fd2c38f9c8d4c0982ecfab18b4ada2d7` |
| `backup/morpheus-feature-dsa-2026-11-12` | `7fa06c93b899c106b212faee4b6b28a40ebd0f22` |
| `backup/morpheus-feature-cpp-2026-11-12` | `a4ec60f81a7f3e42c100edda5eaa5745413b9653` |
| `backup/morpheus-local-2026-11-12` | `7fa06c93b899c106b212faee4b6b28a40ebd0f22` |
| `backup/morpheus-design-2026-11-12` | `75fd575f783fd62b134d5ad67e9470fe3f5c2c36` |
| `backup/morpheus-chat-onboarding-2026-11-12` | `20044b05d2739ef8117852a36b0e23ee0959ac85` |
| `backup/morpheus-readability-2026-11-12` | `5c7dfca4bcfd7112ee08a6e973c65411398015bc` |
| `backup/morpheus-trace-race-2026-11-12` | `a9830af6bcf149630e14d7da340092e6fa95eca5` |
| `backup/morpheus-trace-intake-2026-11-12` | `fbb5aca2997e05e75ef513f36606218165a459ae` |
| `morpheus-known-good-before-next-2026-11-12` | `7fa06c93b899c106b212faee4b6b28a40ebd0f22` |

These are historical setup references. Keep them and create new, dated refs for later recovery points rather than moving or deleting them.

## Daily development

Check branch and worktree before starting:

```bash
git status --short --branch
git switch morpheus-next
git pull --ff-only origin morpheus-next
```

Make the change, review it, and run the relevant checks. Then commit and push:

```bash
git status --short
git diff --check
git diff
git add <intended-files>
git commit -m "feat: describe completed change"
git push origin morpheus-next
git rev-parse HEAD
```

Stage explicit paths when possible; do not accidentally add local binaries, generated outputs, credentials, or unrelated untracked work.

## Recovery points and rollback

Before substantial or risky work, record the current commit with a new dated branch or tag. Do not move an existing recovery ref:

```bash
git switch morpheus-next
git branch backup/morpheus-next-YYYY-MM-DD HEAD
git tag morpheus-next-known-good-YYYY-MM-DD HEAD
git push origin backup/morpheus-next-YYYY-MM-DD
git push origin morpheus-next-known-good-YYYY-MM-DD
```

Create known-good tags only after the relevant tests pass. Record the commit, test results, build status, and limitations in [DEVELOPMENT-CHANGELOG.md](./DEVELOPMENT-CHANGELOG.md).

For a pushed faulty change, inspect the range and reverse the problematic commit with a new commit; never reset or force-push shared history:

```bash
git switch morpheus-next
git pull --ff-only origin morpheus-next
git log --oneline --decorate -20
git show --stat <problematic-commit-sha>
git revert <problematic-commit-sha>
# Resolve and test any revert conflicts, then:
git push origin morpheus-next
```

For a multi-commit change, inspect its dependency order and revert commits in reverse order. Verify the rollback and document it. The pre-integration tag can be inspected with `git show morpheus-known-good-before-next-2026-11-12`; it is not a command to rewrite the shared branch.

## Testing and review

Use the repository's [CI workflow](../.github/workflows/ci.yml) and the commands in [README.md](../README.md) as the source of truth. At minimum, run the applicable backend tests, frontend production build, C++20 build/tests, Java tests when changed, and deployment/container smoke checks when available. Run native integration tests with the actual native executables and Java classes configured as in CI. Report unavailable toolchains or failed checks; do not treat skipped tests as passing.

Review the staged diff and check for secrets before each commit. Update documentation when setup, behavior, or release procedures change. Push each tested milestone and confirm its remote SHA.

## Release process

Develop and verify on `morpheus-next`. Open or update a pull request from `morpheus-next` to `main` for review. Merge only after the requested behavior is complete, required tests/builds and deployment checks pass, documentation is current, critical regressions are resolved, and release approval is explicit. Never merge automatically just because the development branch is ahead.
