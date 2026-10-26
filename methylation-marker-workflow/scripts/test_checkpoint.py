"""Synthetic management-layer acceptance tests; no analysis or server jobs."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

import checkpoint as cp


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        # Use a workspace-local temporary directory; never touches real results.
        parent = Path(__file__).resolve().parents[4] / "tmp"
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent, prefix="skill-checkpoint-")
        self.root = Path(self.temp.name)
        assets = Path(__file__).resolve().parents[1] / "assets"
        self.task = cp.read(assets / "task.json")
        self.task.update(task_id="synthetic", task_definition="Healthy source fixture",
                         organ="synthetic", seed=142, statistical_semantics="Fixture only; no statistics computed",
                         budget=dict(max_seconds=10, max_memory_mb=128, cpu=1, gpu=0, max_samples=3, max_regions=1))
        write(self.root / "task.json", self.task)
        fields = (assets / "samples.csv").read_text().strip().split(",")
        self.rows = [dict(zip(fields, ["s1", "d1", "c1", "target", "source", "target", "unit1", "train", "1", "patterns", "hg38", "region_id", "unread-fixture", "", "synthetic"])),
                     dict(zip(fields, ["s2", "d2", "c1", "background", "other", "other", "other", "train", "2", "patterns", "hg38", "region_id", "unread-fixture", "", "synthetic"]))]
        self.fields = fields
        self.samples()
        code = self.root / "model.txt"
        code.write_text("fixture metadata, never executed", encoding="utf-8")
        card = cp.read(assets / "model-card.json")
        card.update(model_id="fixture", source="user", version="1", author="test", license="test-only",
                    component="sample_fusion", code_path="model.txt", code_sha256=cp.digest(code),
                    environment="stdlib", resources="bounded", seed=142, entrypoint=["never-execute"],
                    isolation_plan="Not executed; synthetic metadata", adaptation_scope="synthetic", limitations="Not a scientific model")
        card["input_contract"] = dict(format="patterns", genome_build="hg38", k_range=[1, 1], tensor_axes="fixture", missing_semantics="unobserved", count_weighted=True, coverage_gate="fixture")
        card["output_contract"] = dict(output_type="score", meaning="synthetic", direction="higher source", pooling="none")
        card["training"] = {k: "not_applicable" for k in card["training"]}
        card["training"]["required"] = False
        card["smoke"] = dict(input="synthetic", expected_output="synthetic", tolerance=0, audit="synthetic only")
        self.card = card
        write(self.root / "card.json", card)
        self.registry = dict(schema_version=1, models=[dict(model_id="fixture", source="user", status="evaluable", enabled=True, card_path="card.json", card_sha256=cp.digest(self.root / "card.json"))])
        write(self.root / "registry.json", self.registry)
        self.result = self.root / "result.txt"
        self.result.write_text("synthetic QC artifact", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def samples(self):
        with (self.root / "samples.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.fields)
            writer.writeheader()
            writer.writerows(self.rows)

    def evidence(self, name, **updates):
        value = dict(note="Synthetic management-layer check only", exit_code=0,
                     checks=[dict(name="fixture QC", passed=True)],
                     artifacts=[dict(path="result.txt", sha256=cp.digest(self.result))],
                     model_audits=["synthetic-only"],
                     reuse_audit=dict(input_match=True, code_match=True, config_match=True, semantics_match=True))
        value.update(updates)
        p = self.root / name
        write(p, value)
        return p

    def test_complete_and_restore(self):
        cp.init(self.root)
        for i in range(10):
            status = "not_applicable" if i in {3, 4} else "passed"
            cp.record(self.root, i, status, self.evidence(f"e{i}.json"))
        _, _, state = cp.load_checked(self.root)
        self.assertIsNone(cp.next_stage(state))
        self.assertEqual(len(state["history"]), 10)

    def test_failure_resume_and_no_stage_jump(self):
        cp.init(self.root)
        with self.assertRaises(ValueError):
            cp.record(self.root, 1, "passed", self.evidence("jump.json"))
        cp.record(self.root, 0, "running", self.evidence("running.json", exit_code=None))
        cp.record(self.root, 0, "failed", self.evidence("failed.json", exit_code=5))
        cp.record(self.root, 0, "passed", self.evidence("repair.json"))
        self.assertEqual([e["status"] for e in cp.load_checked(self.root)[2]["history"]], ["running", "failed", "passed"])

    def test_nonzero_and_qc_failure_rejected(self):
        cp.init(self.root)
        for name, fields in [("exit", dict(exit_code=1)), ("qc", dict(checks=[dict(name="bad", passed=False)]))]:
            with self.assertRaises(ValueError):
                cp.record(self.root, 0, "passed", self.evidence(name+".json", **fields))

    def test_donor_leakage_across_cohorts(self):
        self.rows[1].update(donor_id="d1", cohort_id="another", role="external", split="test")
        self.samples()
        with self.assertRaisesRegex(ValueError, "Donor split leakage"):
            cp.init(self.root)

    def test_unknown_donor_blocks_formal_registration(self):
        self.rows[0]["donor_id"] = "unknown"
        self.samples()
        with self.assertRaisesRegex(ValueError, "Unknown donor"):
            cp.init(self.root)

    def test_coordinate_mismatch(self):
        self.rows[0].update(format="pat", coordinate_system="base_pair_declared", index_path="fixture.csi")
        self.samples()
        with self.assertRaisesRegex(ValueError, "coordinate mismatch"):
            cp.init(self.root)

    def test_missing_and_count_semantics(self):
        for key, value in [("missing_semantics", "biological-third-state"), ("count_weighted", None)]:
            card = json.loads(json.dumps(self.card))
            card["input_contract"][key] = value
            write(self.root / "card.json", card)
            self.registry["models"][0]["card_sha256"] = cp.digest(self.root / "card.json")
            write(self.root / "registry.json", self.registry)
            with self.assertRaises(ValueError):
                cp.init(self.root)

    def test_evidence_and_output_tampering(self):
        cp.init(self.root)
        p = self.evidence("accepted.json")
        cp.record(self.root, 0, "passed", p)
        self.result.write_text("changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            cp.load_checked(self.root)
        self.result.write_text("synthetic QC artifact", encoding="utf-8")
        write(p, dict(note="changed"))
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            cp.load_checked(self.root)

    def test_manifest_changed(self):
        cp.init(self.root)
        self.task["seed"] = 99
        write(self.root / "task.json", self.task)
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            cp.load_checked(self.root)

    def test_reuse_and_skip_guards(self):
        cp.init(self.root)
        with self.assertRaises(ValueError):
            cp.record(self.root, 0, "reused", self.evidence("reuse.json", reuse_audit={}))
        with self.assertRaises(ValueError):
            cp.record(self.root, 0, "not_applicable", self.evidence("skip.json"))

    def test_state_history_mismatch(self):
        cp.init(self.root)
        state = cp.read(self.root / "state.json")
        state["stages"][0]["status"] = "passed"
        write(self.root / "state.json", state)
        with self.assertRaisesRegex(ValueError, "State/history mismatch"):
            cp.load_checked(self.root)

    def test_failed_requires_actual_exit_code(self):
        cp.init(self.root)
        with self.assertRaises(ValueError):
            cp.record(self.root, 0, "failed", self.evidence("badfail.json", exit_code=0))
        with self.assertRaises(ValueError):
            cp.record(self.root, -1, "running", self.evidence("badstage.json"))

    def test_lock_and_existing_state(self):
        cp.init(self.root)
        with self.assertRaises(ValueError):
            cp.init(self.root)
        with cp.locked(self.root):
            with self.assertRaises(FileExistsError):
                cp.record(self.root, 0, "passed", self.evidence("locked.json"))


if __name__ == "__main__":
    unittest.main()
