"""Entrena desde el backend configurado o crea un par de demostración aislado."""

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import create_app
from app.ml.train_models import train


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--demo", action="store_true", help="Usa SQLite en memoria y datos simulados.")
    args = parser.parse_args()
    if not 0 <= args.seed <= 2_147_483_647:
        parser.error("Semilla fuera de rango.")
    app = create_app("testing") if args.demo else create_app()
    if args.demo:
        app.config.update(ML_LABEL_FILE=None, ML_ARTIFACT_DIR=str(BACKEND / "ml_artifacts" / "demo"))
    with app.app_context():
        result = json.dumps({"runs": train(args.seed)}, indent=2, ensure_ascii=False, allow_nan=False)
        print(result)
        if args.demo:
            version = json.loads(result)["runs"][0]["version"]
            (Path(app.config["ML_ARTIFACT_DIR"]) / version / "runs.json").write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
