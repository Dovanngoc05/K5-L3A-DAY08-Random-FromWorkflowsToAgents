"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item, aggregate
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    graded = [m["id"] for m in spec["metrics"] if m["id"] in GRADERS]
    pairs = []
    for name, report in (("PR", pr), ("baseline", base)):
        manifest = report.get("manifest", {})
        rows = report.get("rows", [])
        seeds = manifest.get("seeds", [])
        keys = [(r.get("item_id"), r.get("seed")) for r in rows]
        pairs.append(set(keys))
        if not seeds or len(set(seeds)) != len(seeds):
            problems.append(f"{name}: invalid seed manifest")
        if "seeds" in spec and set(seeds) != set(spec["seeds"]):
            problems.append(f"{name}: seed manifest differs from metric spec")
        if len(rows) != manifest.get("items", 0) * len(seeds) or len(keys) != len(set(keys)):
            problems.append(f"{name}: dropped or duplicated rows")
        by_item = {}
        for row in rows:
            by_item.setdefault(row.get("item_id"), []).append(row.get("seed"))
            if any(type(row.get(mid)) is not bool for mid in graded):
                problems.append(f"{name}: missing or invalid graded row value")
            cost = row.get("cost", 0)
            if not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                problems.append(f"{name}: invalid row cost")
        if len(by_item) != manifest.get("items") or any(Counter(ss) != Counter(seeds) for ss in by_item.values()):
            problems.append(f"{name}: incomplete item x seed coverage")
        if report.get("evaluator_failures"):
            problems.append(f"{name}: evaluator failures")
        for mid, value in report.get("metrics", {}).items():
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                problems.append(f"{name}: invalid metric {mid}")
        # Public unit-test reports omit cost and derived metrics. Real reports
        # carry them; recompute those reports rather than trusting their means.
        if rows and all("cost" in r for r in rows) and not problems:
            calculated = aggregate(rows, graded, k_values=spec.get("pass_k", []))
            for mid, value in calculated.items():
                if report.get("metrics", {}).get(mid) != value:
                    problems.append(f"{name}: aggregate mismatch {mid}")
    if pairs[0] != pairs[1]:
        problems.append("PR and baseline item/seed sets differ")
    base_tags = {(r["item_id"], r["seed"]): set(r.get("slices", [])) for r in base.get("rows", [])}
    for row in pr.get("rows", []):
        if set(row.get("slices", [])) != base_tags.get((row["item_id"], row["seed"]), set()):
            problems.append("slice tags changed")
    if base_spec and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        def ratchet(old_entries, new_entries, key):
            new = {key(e): e for e in new_entries}
            for old in old_entries:
                entry = new.get(key(old))
                if entry is None:
                    problems.append(f"removed spec entry {key(old)}")
                    continue
                if old.get("blocking") and not entry.get("blocking"):
                    problems.append(f"nonblocking {key(old)}")
                before, after = old.get("threshold", old), entry.get("threshold", entry)
                for field in ("min", "max", "max_increase"):
                    if field in before and (field not in after or
                            (after[field] < before[field] if field == "min" else after[field] > before[field])):
                        problems.append(f"loosened {key(old)} {field}")
                if before.get("no_significant_drop") and not after.get("no_significant_drop"):
                    problems.append(f"removed paired check {key(old)}")
        ratchet(base_spec.get("metrics", []), spec.get("metrics", []), lambda e: e["id"])
        ratchet(base_spec.get("slices", []), spec.get("slices", []), lambda e: (e["name"], e["metric"]))
        if spec.get("seeds") != base_spec.get("seeds"):
            problems.append("spec seeds changed without new eval-set version")
    return sorted(set(problems))


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for entry in spec.get("slices", []):
        name, mid = entry["name"], entry["metric"]
        identifier = f"slice:{name}/{mid}"
        a, b = per_item(pr, mid, name), per_item(base, mid, name)
        keys = sorted(a)
        failed = not keys or set(a) != set(b)
        value = sum(a.values()) / len(a) if a else None
        note = ""
        if value is not None:
            failed |= "min" in entry and value < entry["min"]
            failed |= "max" in entry and value > entry["max"]
        if entry.get("no_significant_drop") and keys and set(a) == set(b):
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027), confidence=bs.get("confidence", 0.95))
            note = f"delta={d:+.4f} CI [{lo:+.4f}, {hi:+.4f}]"
            failed |= hi < 0
        if failed and entry.get("blocking"):
            blocked.append(identifier)
        lines.append(f"  {identifier}: {value} {note} {'BLOCK' if failed and entry.get('blocking') else 'warn' if failed else 'ok'}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027), confidence=bs.get("confidence", 0.95))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
