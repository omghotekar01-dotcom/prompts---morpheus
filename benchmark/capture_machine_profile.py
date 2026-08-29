from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.machine_profile import (  # noqa: E402
    capture_machine_profile,
    machine_identity_document,
    machine_profile_fingerprint,
)


# Preserve the historical public helper name used by benchmark scripts/tests.
def capture() -> dict[str, object]:
    return capture_machine_profile()


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture MORPHEUS benchmark machine/toolchain provenance.")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    rendered = json.dumps(capture(), sort_keys=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
