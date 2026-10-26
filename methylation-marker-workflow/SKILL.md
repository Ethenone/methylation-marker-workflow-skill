---
name: methylation-marker-workflow
description: Record, validate, and resume DNA methylation marker-selection and sample-scoring experiments with explicit data boundaries and model cards. Use for fixed-panel comparisons or bounded discovery plans; requires project-specific data and model adapters.
---

# Methylation marker and sample-scoring workflow

This Skill manages research protocols and local checkpoints. It does not implement sequencing preprocessing or genome-wide discovery. Locate the host project's protocol, data guide, source code, and evaluation plan before running an experiment. Never infer a statistical definition from a variable name.

## Define the task

Declare whether the task is tissue-source identification, tumor/normal classification, low-fraction cfDNA detection, or multicancer source attribution. Distinguish raw evidence, source fraction, percentile, and calibrated probability. Choose `fixed_panel` for an existing frozen region set; choose `discovery` only with a declared candidate universe, label-use history, split and compute budget.

Read [contracts](references/contracts.md) and copy `assets/task.json`, `samples.csv`, `model-card.json`, `registry.json`, and `evidence.json` into a new experiment directory. Complete fields using evidence, not guessed donor identities or statistical semantics. Hash small source/configuration files; keep large raw data at their governed location. Unknown donor or technical-repeat relationships remain unknown and limit independence claims.

## Preserve statistical meaning

Read [data boundaries and raw-count refit](references/data-boundary.md) when working from patterns or evaluating new data. In `0/1/2` and `0/1/?`, `2/?` means an unobserved CpG, never a third biological methylation state. PAT `C/T/.` maps to `1/0/?`. Preserve read multiplicity, coverage conditions, smoothing, log base, numerator/denominator, pooling, and aggregation from the actual implementation. Do not interchange conditional logLR, EM logLR, evidence scores, source fractions, and probabilities.

All panel selection, fitting, preprocessing, thresholds and calibration belong inside the training boundary. Keep technical repeats and known donors together across folds. For an unknown identity link, report the limitation rather than certifying independence. Fixed-panel OOF excludes the uncertainty of upstream marker selection. External labels are used only for evaluation under a frozen protocol.

## Register models and run small checks

Both built-in and user models use the same model-card contract. Register the real code path and hash, input/output semantics, training and pretraining data, overlap audit, dependency versions, limits and a small expected-output fixture. An entry in a registry is not evidence of successful execution. Automatic model search and remote API adapters are outside this release.

Read [controlled execution](references/executor.md) before using `scripts/executor.py`. It records local attempts, timeout, terminal receipt, hashes and failures; it is not a security sandbox. Use only reviewed, trusted adapters. A receipt does not replace scientific QC. Do not run a default wrapper that silently launches a full cohort or genome-wide task.

## Checkpoint and resume

Read [stages](references/stages.md). From the installed Skill directory:

```text
python scripts/checkpoint.py init <experiment_dir>
python scripts/checkpoint.py check <experiment_dir>
python scripts/checkpoint.py status <experiment_dir>
python scripts/checkpoint.py record <experiment_dir> <stage_0_to_9> running <evidence.json>
python scripts/checkpoint.py record <experiment_dir> <stage_0_to_9> passed <evidence.json>
```

Before continuing, run `check` and `status`, inspect the last accepted evidence, and advance one stage at a time. A running job requires log/process/receipt reconciliation before any retry. Keep failed, blocked and rejected cases and their reasons. Do not hand-edit accepted state or evidence to bypass a failed check. Historical work can be marked `reused` only after input, code, configuration and statistical-semantics matching.

Report sample IDs, known donor/cohort, panel/model versions, raw score meaning, coverage, failures and refusal reasons. Classifier metrics require an appropriate held-out design; report unavailable metrics with reasons. Use donor/patient-level uncertainty only when identity is evidenced. Do not turn a development score or percentile into a trustworthy cancer probability.
