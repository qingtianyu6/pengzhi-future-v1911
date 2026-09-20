from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.disease.train import finalize_existing_artifacts, run_resnet_fallback, run_training


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the tomato disease recognition model")
    parser.add_argument("--smoke", action="store_true", help="Run the required 64-per-class one-epoch smoke flow")
    parser.add_argument("--finalize-existing", action="store_true", help="Finalize plots/card from the saved best checkpoint")
    parser.add_argument("--resnet-fallback", action="store_true", help="Run the single allowed ResNet18 fallback")
    args = parser.parse_args()
    if args.resnet_fallback:
        result = run_resnet_fallback()
    elif args.finalize_existing:
        result = finalize_existing_artifacts()
    else:
        result = run_training(smoke_only=args.smoke)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status", "passed") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
