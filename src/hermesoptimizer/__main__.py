from __future__ import annotations
import sys
from hermesoptimizer.cli import build_parser, dispatch
from hermesoptimizer.paths import ensure_dirs

def main() -> int:
    ensure_dirs()
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:])
    return dispatch(args)

if __name__ == "__main__":
    raise SystemExit(main())
