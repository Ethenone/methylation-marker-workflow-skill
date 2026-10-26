# Methylation marker workflow Skill

This repository contains a Codex Skill for recording, checking, and resuming DNA methylation marker selection and sample-scoring experiments. The first public release provides a portable experiment contract, a checkpoint manager, and a reviewed local command runner. It does **not** include a genome-wide discovery engine, sequencing preprocessors, the original research data, or a validated clinical classifier.

## Install

Copy `methylation-marker-workflow/` into your Codex skills directory (for example, `~/.codex/skills/`), then invoke `$methylation-marker-workflow` in a project that contains your own data, model implementations, and research protocol. Python 3 is needed for the bundled scripts; the core scripts use the standard library.

```text
python methylation-marker-workflow/scripts/test_checkpoint.py
python methylation-marker-workflow/scripts/checkpoint.py --help
python methylation-marker-workflow/scripts/executor.py --help
```

Copy the files under `assets/` into a new experiment directory and complete their missing fields. Read `SKILL.md` and the linked contracts before initializing a checkpoint. The runner accepts only locally reviewed commands and is **not a security sandbox**.

## Scope and evidence

The project source at local revision `bc4a588` passed 13 checkpoint tests and 13 data-boundary tests on 2026-10-26. Its V3 acceptance covered a three-region raw-count refit and bounded coordinate/extraction checks. Those results do not validate a full discovery-to-classification run, donor-independent performance, all 15 regions, or all model families. The original project-specific reports, raw PAT/mHap data, server paths, and model implementations are not redistributed here.

The Skill can register built-in and researcher-supplied model **adapters**. It does not discover or download models automatically. A user model must provide its own code, dependencies, model card, and a small expected-output fixture. Missing donor identity stays unknown. A fixed-panel out-of-fold estimate does not include the uncertainty from earlier marker selection. A score or percentile is not automatically a cancer probability.

## Repository layout

- `methylation-marker-workflow/SKILL.md`: invocation guidance and scientific boundaries.
- `methylation-marker-workflow/references/`: contracts, stages, execution and data-boundary rules.
- `methylation-marker-workflow/scripts/`: checkpoint manager, reviewed executor, and focused tests.
- `methylation-marker-workflow/assets/`: blank task, model, sample, registry, and evidence templates.

## Development status

This is a reusable **workflow-control core**, not a ready-to-run methylation analysis package. Integrating a new data source or statistical model requires an explicit adapter and validation against that source's coordinate, missingness, count, and leakage semantics. The original 110 cancer tissue samples were development-only and were not used to select the model. No clinically trustworthy cancer probability is claimed.

## License

MIT. See [LICENSE](LICENSE).
