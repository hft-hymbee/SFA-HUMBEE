#!/usr/bin/env python3
"""Generate the committed OpenAPI artifact from the FastAPI app."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "apps" / "api" / "src"))

    from humbee_sfa.main import create_app  # pylint: disable=import-outside-toplevel

    app = create_app()
    openapi = app.openapi()
    output_path = repo_root / "packages" / "api-contract" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        f"{json.dumps(openapi, indent=2, sort_keys=True, ensure_ascii=True)}\n",
        encoding="utf-8",
    )
    print(f"Wrote OpenAPI contract: {output_path}")


if __name__ == "__main__":
    main()
