# MORPHEUS Windows: native C++ startup without a local compiler

The one-click launcher must run the **compiled C++20 optimizer and CSV profiler**.
FastAPI serves only as the adapter; there is no silent Python-only fallback.

## Why you saw "No CMAKE_CXX_COMPILER could be found"

CMake located **Visual Studio 18 2026** but could not find a usable C++
compiler in that installation. Python, React, and Git are not the cause.
Installing Visual Studio *alone* does not guarantee that the **Desktop
development with C++** workload / MSVC x64 build tools are installed.

## Option A — install the C++ workload (for developers)

1. Open **Visual Studio Installer**.
2. Find Visual Studio 2026 (or Build Tools), choose **Modify**.
3. Check **Desktop development with C++** and ensure **MSVC Build Tools
   for x64/x86** and a **Windows SDK** are included.
4. Complete installation and open a new PowerShell window.
5. From your MORPHEUS Git clone:

~~~powershell
git pull --ff-only
.\START-MORPHEUS.bat
~~~

The updated launcher now uses a separate CMake directory
\`build\native-windows\`, so the old failed \`build\core\` cache won't prevent
toolchain detection. It reports exact remediation instructions if CMake fails.

## Option B — run real C++ without installing a local compiler

Use the C++20 binaries built by **your own repository's Windows GitHub Actions
job**. The launcher accepts a matching commit, or an earlier ancestor whose
native C++ sources and CMake recipe are provably unchanged.

1. In GitHub, open **Actions → MORPHEUS CI** on
   \`feat/native-cpp-dsa-search-20261025\`, and choose the latest **successful**
   run for the exact current branch commit.
2. Under **Artifacts**, download the zip named
   \`morpheus-native-windows-x64-<commit sha>\`. You may need to be signed into
   GitHub. The archive contains:
   - \`morpheus_native_search.exe\`
   - \`morpheus_csv_profile.exe\`
   - \`SHA256.json\`
3. Extract **all three files**, without adding another nested directory, to
   \`<MORPHEUS repo>\bin\windows-x64\`.
4. From the MORPHEUS repository root, execute:

~~~powershell
git pull --ff-only
Get-ChildItem .\bin\windows-x64
.\START-MORPHEUS.bat
~~~

The launcher checks that both executables exist, that the manifest is the
expected format, that it names the **exact commit currently checked out**,
and that the SHA-256 of each executable matches the manifest. It refuses to
run invalid, stale or mismatched binaries. Download only artifacts produced
by your own repository's trusted GitHub Actions workflow.

**Important:** This path runs C++ synthesis and CSV profiling, but it does not
install a C++ compiler. To compile or verify freshly generated C++ artifacts
on this Windows machine, you will still need a C++20 compiler (or an approved
remote build/verification service). Do not call generated code verified
without that evidence.

## One-command GitHub CLI download (if installed)

After pulling the feature branch, if the official `gh` command is installed
and already authenticated, `START-MORPHEUS.bat` now looks for a Windows
native artifact matching your checked-out commit and downloads it before
trying CMake. It checks the artifact's version, source commit and hashes.

For an installation that does not include `gh`, manually download the
artifact from a [Windows C++ CI build of the current branch](https://github.com/omghotekar01-dotcom/prompts---morpheus/actions/workflows/ci.yml).
Choose a **successful** `Core / Windows / MSVC C++20` job and select the
artifact named `morpheus-native-windows-x64-<its-source-commit>`.
For example, the [Windows C++ build for 4ce2d77](https://github.com/omghotekar01-dotcom/prompts---morpheus/actions/runs/40173427873)
published `morpheus-native-windows-x64-4ce2d773fbd69ea983b216999d6682639b846a43`
after the native CSV-query implementation changed. The earlier binary from
`516c1d3` is **not** compatible with these updated sources.

Extract **both** EXEs and `SHA256.json` to `bin\\windows-x64`, overwriting
the existing files without a nested directory. The launcher accepts a bundle
from an ancestor source commit only when tracked native sources and build
recipes have not changed. **Do not download executables from unofficial
websites and do not bypass the source or checksum checks.**

## If neither option is configured

The launcher intentionally **stops** with a clear error rather than inventing
results using an unrelated Python rule. You can inspect your local toolchain
with:

~~~powershell
cmake --version
Get-Command cl.exe, g++, clang++, cmake -ErrorAction SilentlyContinue
~~~

\`cl.exe\` may be missing from a normal PowerShell PATH even when an MSVC
toolset is installed; the **Visual Studio C++ Developer Command Prompt** is
another way to check compiler availability. CMake's own configuration result
is the final authority.

For Microsoft installation guidance:
https://learn.microsoft.com/en-us/cpp/overview/acquire-msvc
