"""Exporta o schema OpenAPI da API para `docs/openapi.json`.

Uso (a partir de `backend/`):
    python scripts/export_openapi.py          # regrava o arquivo
    python scripts/export_openapi.py --check  # falha se o arquivo estiver desatualizado
"""

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

OUTPUT = BACKEND_DIR.parent / "docs" / "openapi.json"


def render() -> str:
    app = create_app(Settings(_env_file=None))
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    content = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print(f"{OUTPUT} desatualizado; rode scripts/export_openapi.py", file=sys.stderr)
            return 1
        return 0

    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"OpenAPI gravado em {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
