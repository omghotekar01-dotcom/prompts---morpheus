from __future__ import annotations

"""Native C++ reference scans of submitted records (not timing benchmarks)."""

import subprocess

from .native_csv_profile import CsvProfilingError, CsvProfilerMissing, _profiler_executable


def probe_submitted_csv(
    csv_text: str, column_index: int, kind: str, lower: str,
    upper: str = "", preview_limit: int = 20,
) -> dict:
    if kind not in {"point_lookup", "filter", "range_scan", "prefix_search"}:
        raise CsvProfilingError("unsupported query operation")
    if not 0 <= preview_limit <= 50:
        raise CsvProfilingError("query preview must request 0-50 rows")
    args = [
        str(_profiler_executable()), "--probe", str(column_index), kind,
        lower.encode("utf-8").hex() or "-", upper.encode("utf-8").hex() or "-",
        str(preview_limit),
    ]
    try:
        proc = subprocess.run(
            args, input=csv_text, encoding="utf-8", text=True,
            capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CsvProfilerMissing("Unable to run native C++ reference scan") from exc
    if proc.returncode != 0:
        raise CsvProfilingError("C++ reference scan rejected input: " + proc.stderr[:350])
    lines = proc.stdout.splitlines()
    if not lines:
        raise CsvProfilingError("C++ reference scan returned no output")
    head = lines[0].split()
    if len(head) != 5 or head[0] != "MATCH_V1":
        raise CsvProfilingError("Native executable does not support MATCH_V1; download the latest compiled Windows artifact")
    try:
        total, matched, columns, returned = map(int, head[1:])
    except ValueError as exc:
        raise CsvProfilingError("invalid reference scan result") from exc
    if (not 1 <= total <= 100_000 or not 1 <= columns <= 64
            or not 0 <= matched <= total or not 0 <= returned <= min(matched, preview_limit)
            or len(lines) != returned + 1):
        raise CsvProfilingError("inconsistent native reference scan counts")
    records: list[dict] = []
    for line in lines[1:]:
        tokens = line.split()
        if len(tokens) != columns + 2 or tokens[0] != "ROW":
            raise CsvProfilingError("invalid native row preview")
        try:
            index = int(tokens[1])
            cells = [bytes.fromhex(token).decode("utf-8") if token != "-" else ""
                     for token in tokens[2:]]
        except (ValueError, UnicodeError) as exc:
            raise CsvProfilingError("invalid native row bytes") from exc
        if not 1 <= index <= total:
            raise CsvProfilingError("invalid native record index")
        records.append({"record_index": index, "values": cells})
    return {
        "total_records": total,
        "matched_records": matched,
        "matched_selectivity": matched / total,
        "preview_records": records,
        "preview_truncated": matched > len(records),
        "evidence": "EXACT_SUBMITTED_RECORDS_NATIVE_CPP20_LINEAR_REFERENCE_SCAN",
        "performance_evidence": "NOT_A_BENCHMARK",
    }
