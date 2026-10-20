"""Print a compact function-level cProfile report for a saved local run."""

import argparse
import pstats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("--filter", default="visibility")
    parser.add_argument("--limit", type=int, default=35)
    args = parser.parse_args()
    stats = pstats.Stats(args.profile)
    rows = []
    for (filename, line, name), (
        _calls,
        total_calls,
        own_seconds,
        cumulative_seconds,
        _,
    ) in stats.stats.items():
        if args.filter in filename or args.filter in name:
            rows.append((cumulative_seconds, own_seconds, total_calls, filename, line, name))
    for cumulative, own, calls, filename, line, name in sorted(rows, reverse=True)[: args.limit]:
        print(f"{cumulative:8.3f} {own:8.3f} {calls:6d} {filename}:{line} {name}")


if __name__ == "__main__":
    main()
