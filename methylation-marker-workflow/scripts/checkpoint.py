"""Local manifest and checkpoint manager. Never executes analysis/model code.

Paths in task/evidence artifacts and model cards resolve against the run root.
Single-writer lock plus atomic state replacement; no remote access/dependencies.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

STAGES = ["registration", "format_qc", "model_snapshot", "coarse_screen",
          "secondary_screen", "local_model", "internal_comparison", "freeze",
          "external_comparison", "archive"]
DONE = {"passed", "reused", "not_applicable"}
MODEL_STATES = {"registered", "metadata_checked", "smoke_passed", "interface_passed",
                "evaluable", "frozen", "information_missing", "incompatible", "failed",
                "resource_exceeded", "license_blocked", "disabled"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(root, path):
    require(isinstance(path, str) and bool(path), "Missing artifact path")
    p = Path(path)
    return (p if p.is_absolute() else root / p).resolve()


def artifacts(root, items):
    require(isinstance(items, list), "artifacts must be a list")
    out = []
    for item in items:
        p = resolve(root, item.get("path"))
        require(p.is_file(), f"Missing local artifact: {p}")
        sha = digest(p)
        require(sha == item.get("sha256"), f"Artifact hash mismatch: {p}")
        out.append({"path": str(p), "sha256": sha})
    return out


def validate(root):
    task = read(root / "task.json")
    require(task.get("schema_version") == 1, "Unsupported task schema")
    for key in ["task_id", "task_definition", "statistical_semantics", "organ"]:
        require(bool(task.get(key)), f"Missing task field: {key}")
    require(task.get("task_type") in {"tissue_source", "tumor_normal", "low_fraction_cfdna", "multicancer_source"}, "Invalid task_type")
    require(task.get("protocol") in {"fixed_panel", "discovery"}, "Invalid protocol")
    require(task.get("external_label_use") == "evaluation_only", "External labels must be evaluation_only")
    require(type(task.get("seed")) is int, "Explicit integer seed required")
    budget = task.get("budget", {})
    for key in ["max_seconds", "max_memory_mb", "cpu", "max_samples", "max_regions"]:
        require(type(budget.get(key)) in {int, float} and budget[key] > 0, f"Missing positive budget: {key}")
    require(type(budget.get("gpu")) is int and budget["gpu"] >= 0, "Explicit GPU budget required")
    pinned = artifacts(root, task.get("artifacts", []))
    with (root / "samples.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    require(bool(rows), "samples.csv has no samples")
    ids, donor_splits, donor_folds, label_folds = set(), {}, {}, {}
    coordinates = {"pat": "cpg_ordinal_1based", "beta": "cpg_ordinal_1based",
                   "mhap": "base_pair_declared", "summary": "base_pair_declared",
                   "patterns": "region_id", "features": "region_id"}
    required = ["sample_id", "donor_id", "cohort_id", "role", "label", "biosample_label",
                "target_unit", "split", "fold", "format", "genome_build", "coordinate_system",
                "data_path", "donor_evidence"]
    for row in rows:
        require(all(row.get(k) for k in required), "Incomplete sample row")
        sid, donor = row["sample_id"], row["donor_id"]
        require(donor.strip().lower() not in {"unknown", "information_missing", "none", "null", "nan", "na", "n/a"}, "Unknown donor cannot pass formal registration; keep preparation audit")
        require(sid not in ids, f"Duplicate sample_id: {sid}")
        ids.add(sid)
        require(row["role"] in {"target", "background", "audit", "external"}, "Invalid role")
        require(row["split"] in {"train", "calibration", "test", "audit"}, "Invalid split")
        require((row["role"] == "audit") == (row["split"] == "audit"), "Audit role/split mismatch")
        require((row["role"] == "external") == (row["split"] == "test"), "External role/split mismatch")
        require(row["genome_build"] in {"hg19", "hg38"}, "Unsupported genome build")
        require(coordinates.get(row["format"]) == row["coordinate_system"], "Format/coordinate mismatch")
        if row["format"] in {"pat", "mhap"}:
            require(bool(row.get("index_path")), "PAT/mHap index required")
        require(donor_splits.setdefault(donor, row["split"]) == row["split"], f"Donor split leakage: {donor}")
        if row["split"] != "audit":
            require(donor_folds.setdefault(donor, row["fold"]) == row["fold"], f"Donor fold leakage: {donor}")
        if row["role"] == "background" and row["split"] == "train":
            label = row["biosample_label"]
            require(label_folds.setdefault(label, row["fold"]) == row["fold"], f"Background label fold leakage: {label}")
    registry = read(root / "registry.json")
    require(registry.get("schema_version") == 1, "Unsupported registry schema")
    models = registry.get("models")
    require(isinstance(models, list), "models must be a list")
    model_ids = set()
    for model in models:
        mid = model.get("model_id")
        require(bool(mid) and mid not in model_ids, "Missing/duplicate model_id")
        model_ids.add(mid)
        require(model.get("source") in {"builtin", "user"}, "v1 supports builtin/user only")
        require(model.get("status") in MODEL_STATES, "Invalid model status")
        require(type(model.get("enabled")) is bool, "enabled must be boolean")
        if model.get("card_path"):
            p = resolve(root, model["card_path"])
            require(digest(p) == model.get("card_sha256"), f"Model card hash mismatch: {mid}")
            pinned.append({"path": str(p), "sha256": digest(p)})
            card = read(p)
            require(card.get("schema_version") == 1 and card.get("model_id") == mid and card.get("source") == model["source"], "Model card identity mismatch")
            if model["enabled"] and model["status"] in {"evaluable", "frozen"}:
                for key in ["version", "author", "license", "component", "code_path", "code_sha256",
                            "training", "environment", "resources", "entrypoint", "smoke", "isolation_plan", "adaptation_scope", "limitations"]:
                    require(bool(card.get(key)), f"Incomplete evaluable model: {mid}/{key}")
                require(type(card.get("seed")) is int, "Model seed required")
                require(isinstance(card["entrypoint"], list) and all(isinstance(x, str) for x in card["entrypoint"]), "entrypoint must be argv")
                inp, out = card.get("input_contract", {}), card.get("output_contract", {})
                require(inp.get("missing_semantics") == "unobserved", "Missing state must be unobserved")
                require(type(inp.get("count_weighted")) is bool, "Explicit count semantics required")
                for key in ["format", "genome_build", "k_range", "tensor_axes", "coverage_gate"]:
                    require(bool(inp.get(key)), f"Missing input contract: {key}")
                for key in ["output_type", "meaning", "direction", "pooling"]:
                    require(bool(out.get(key)), f"Missing output contract: {key}")
                if out["output_type"] == "loglr":
                    for key in ["log_base", "numerator", "denominator", "smoothing", "coverage_condition"]:
                        require(out.get(key) is not None, f"Missing logLR semantics: {key}")
                for section, keys in [("training", ["required", "fit_data", "selection_data", "calibration_data", "pretrained_data", "overlap_audit"]), ("smoke", ["input", "expected_output", "tolerance", "audit"])]:
                    require(isinstance(card[section], dict) and all(card[section].get(k) is not None for k in keys), f"Incomplete {section}")
                pinned.extend(artifacts(root, [{"path": card["code_path"], "sha256": card["code_sha256"]}]))
                if card.get("weights_path"):
                    pinned.extend(artifacts(root, [{"path": card["weights_path"], "sha256": card.get("weights_sha256")}]))
        else:
            require(not (model["enabled"] and model["status"] in {"evaluable", "frozen"}), "Evaluable model card required")
    pinned.extend({"path": str((root / name).resolve()), "sha256": digest(root / name)}
                  for name in ["task.json", "samples.csv", "registry.json"])
    return task, models, pinned


def load_checked(root):
    task, models, pinned = validate(root)
    state = read(root / "state.json")
    require(state["pins"] == pinned, "Frozen manifest changed; create a new experiment")
    require(state.get("schema_version") == 1 and state.get("task_id") == task["task_id"], "State identity/schema mismatch")
    require(isinstance(state.get("stages"), list) and len(state["stages"]) == len(STAGES), "Invalid state stages")
    replay = [{"name": name, "status": "pending"} for name in STAGES]
    require(isinstance(state.get("history"), list), "Invalid state history")
    for event in state["history"]:
        stage = event.get("stage")
        require(type(stage) is int and 0 <= stage < len(STAGES), "Invalid history stage")
        first = next((i for i, row in enumerate(replay) if row["status"] not in DONE), None)
        require(stage == first, "History contains illegal stage transition")
        require(event.get("status") in {"running", "passed", "reused", "not_applicable", "failed", "blocked"}, "Invalid history status")
        if event["status"] == "not_applicable":
            require(task["protocol"] == "fixed_panel" and stage in {3, 4}, "Illegal skipped history stage")
        replay[stage]["status"] = event["status"]
    require(state["stages"] == replay, "State/history mismatch; restore reviewed checkpoint")
    for event in state["history"]:
        require(digest(event["evidence_path"]) == event["evidence_sha256"], "Accepted evidence changed")
        artifacts(root, event["artifacts"])
    return task, models, state


def next_stage(state):
    return next((i for i, s in enumerate(state["stages"]) if s["status"] not in DONE), None)


@contextmanager
def locked(root):
    lock = root / ".checkpoint.lock"
    fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def save(root, state):
    temp = root / ".state.tmp"
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, root / "state.json")


def init(root):
    with locked(root):
        require(not (root / "state.json").exists(), "Existing state; use check/status")
        task, _, pins = validate(root)
        save(root, {"schema_version": 1, "task_id": task["task_id"], "pins": pins,
                    "stages": [{"name": n, "status": "pending"} for n in STAGES], "history": []})


def record(root, stage, status, evidence_path):
    with locked(root):
        task, models, state = load_checked(root)
        require(type(stage) is int and 0 <= stage < len(STAGES), "Stage must be an integer 0-9")
        require(stage == next_stage(state), "Only first unfinished stage may advance")
        require(status in {"running", "passed", "reused", "not_applicable", "failed", "blocked"}, "Invalid status")
        p = Path(evidence_path).resolve()
        require(all(e["evidence_path"] != str(p) for e in state["history"]), "Use a new evidence file for every transition")
        evidence = read(p)
        require(bool(evidence.get("note")), "Evidence note/reason required")
        files = artifacts(root, evidence.get("artifacts", []))
        if status in {"passed", "reused"}:
            require(type(evidence.get("exit_code")) is int and evidence["exit_code"] == 0, "Success requires exit_code=0")
            checks = evidence.get("checks")
            require(isinstance(checks, list) and bool(checks) and all(isinstance(c, dict) and c.get("name") and c.get("passed") is True for c in checks), "Success requires all QC checks passed")
            require(bool(files), "Success requires hashed artifacts")
            if stage == 2:
                enabled = [m for m in models if m["enabled"]]
                require(bool(enabled) and all(m["status"] in {"evaluable", "frozen"} for m in enabled), "Stage 2 requires accepted enabled models")
                require(bool(evidence.get("model_audits")), "Stage 2 requires model audit evidence")
            if status == "reused":
                audit = evidence.get("reuse_audit") or {}
                require(all(audit.get(k) is True for k in ["input_match", "code_match", "config_match", "semantics_match"]), "Reuse requires all four matches")
        if status == "failed":
            require(type(evidence.get("exit_code")) is int and evidence["exit_code"] != 0, "Failed execution requires nonzero exit_code; use blocked for pre-execution issues")
        if status == "not_applicable":
            require(task["protocol"] == "fixed_panel" and stage in {3, 4}, "Only fixed_panel stages 3/4 may be not_applicable")
        state["stages"][stage]["status"] = status
        state["history"].append({"stage": stage, "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(), "note": evidence["note"],
            "evidence_path": str(p), "evidence_sha256": digest(p), "artifacts": files,
            "exit_code": evidence.get("exit_code"), "model_failures": evidence.get("model_failures", [])})
        save(root, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "check", "status", "record"])
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("stage", type=int, nargs="?")
    parser.add_argument("status", nargs="?")
    parser.add_argument("evidence", type=Path, nargs="?")
    args = parser.parse_args()
    root = args.run_dir.resolve()
    try:
        if args.action == "init":
            init(root)
        elif args.action == "record":
            require(args.stage is not None and args.status is not None and args.evidence is not None, "record needs stage/status/evidence")
            record(root, args.stage, args.status, args.evidence)
        task, models, state = load_checked(root)
        i = next_stage(state)
        print(json.dumps({"task_id": task["task_id"], "check": "passed", "next_stage": i,
                          "stages": state["stages"], "models": [{"model_id": m["model_id"], "status": m["status"], "enabled": m["enabled"]} for m in models]}, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Checkpoint rejected: {exc}\n")


if __name__ == "__main__":
    main()
