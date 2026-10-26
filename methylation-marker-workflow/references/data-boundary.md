# Data boundary and raw-count checks

For every sample, record `sample_id`, `donor_id` when independently supported, source cohort, source file, technical-replicate group, split and fold. A shared accession may have several region measurements; these are not new biological replicates. An unknown donor or repeat link cannot be certified absent. Known identities must not cross train, calibration, validation and test boundaries.

Record genome build and coordinate system for every panel and data source. PAT CpG ordinal coordinates, mHap base-pair endpoints and panel region IDs need an explicit per-CpG mapping. A matching interval endpoint alone does not certify a matched CpG set. Reject coordinate/build mismatch and preserve the original extraction configuration and source hashes.

Raw pattern counts require an explicit alphabet (`012` or `01?`), unobserved-state meaning and positive integer multiplicities. Reject duplicate sample-region keys, ambiguous repeated pattern rows, nonpositive/noninteger counts, missing rows and count/summary mismatch. If a historical extractor emits repeated two-column pattern rows, sum them only under a documented, explicitly selected protocol. Never set every read count to one or discard rare patterns to make a file pass.

To claim **refit**, start with extracted raw pattern counts, rebuild pattern statistics, fit the model, aggregate regions and score held-out samples. Frozen predictions can be a comparison target but cannot replace fitting. Keep the model implementation, configuration, inputs and outputs hashed, with observed exit codes and logs. Distinguish component numerical replay, coordinate-chain checks, donor-boundary certification, and complete model validation.

If the host project lacks a bounded raw-count fixture or source-backed identity map, report the minimum missing files and stop at the component scope. Do not trigger a genome-wide extraction to repair a small acceptance gap.
