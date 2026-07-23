# Compatibility scoring

This stage calculates an explainable compatibility score per target job.

The score expresses alignment between available professional evidence and the requirements identified in the selected jobs. It is not a hiring probability and does not guarantee results in a selection process.

## Flow

```text
CandidateProfessionalProfile
              +
TargetMarketAnalysis
              ↓
Evaluación semántica
              ↓
RequirementMatch
              ↓
Motor de scoring local
              ↓
Auditoría matemática
              ↓
CompatibilityReport
```

## Inputs

Compatibility uses only:

- audited `CandidateProfessionalProfile`;
- audited `TargetMarketAnalysis`;
- `OutputLanguage`.

It does not receive the full CV, raw LinkedIn text, files, HTML, URLs, raw job descriptions, generated LinkedIn profile text or banner content.

## Semantic evaluation

OpenAI generates `CompatibilitySemanticEvaluation`. It classifies each requirement as:

- `full`;
- `partial`;
- `indirect`;
- `missing`;
- `conflict`;
- `not_applicable`.

OpenAI does not calculate the final score. The final score is calculated locally.

## Dimensions and MVP weights

- Experience and responsibilities: `0.30`.
- Skills and knowledge: `0.25`.
- Tools and technologies: `0.15`.
- Leadership and management: `0.12`.
- Industry and business context: `0.10`.
- Education, certifications and languages: `0.08`.

Weights are fixed for this MVP and are not editable from the UI.

## Requirement formula

Coverage points:

- full: `1.00`;
- partial: `0.65`;
- indirect: `0.35`;
- missing: `0.00`;
- conflict: `0.00`;
- not applicable: excluded.

Evidence factors:

- `SUPPORTED`: `1.00`;
- `INFERRED`: `0.75`;
- `MISSING`: `0.00`;
- `CONFLICT`: `0.00`.

Requirement score:

```text
coverage_points × evidence_status_factor
```

Requirement weight:

```text
priority_weight × required_multiplier
```

Priority weights:

- critical: `1.50`;
- high: `1.25`;
- medium: `1.00`;
- low: `0.75`.

Required requirements use multiplier `1.20`; preferred requirements use `1.00`.

## Dimension formula

```text
sum(requirement_score × requirement_weight)
──────────────────────────────────────────── × 100
sum(requirement_weight)
```

Dimensions without requirements are not scored as zero. Their original weight is redistributed across evaluated dimensions while preserving relative proportions.

## Penalties

Only these penalties exist in methodology version `1.0`:

- Critical required missing or conflict: `5.0` points per requirement, max `20.0`.
- Seniority gap of at least two levels: `5.0`.
- Mandatory language missing: `5.0`, once per vacancy.

No penalty is applied for desirable certifications, desirable tools, generic keywords or ambiguous requirements.

## Final score

```text
score_before_penalties =
Σ(dimension_score × effective_dimension_weight)

final_score =
max(0, min(100, score_before_penalties - penalties))
```

The score is rounded to one decimal.

## Bands

- `85.0–100.0`: Very high / Muy alta.
- `70.0–84.9`: High / Alta.
- `55.0–69.9`: Moderate / Moderada.
- `40.0–54.9`: Low / Baja.
- `0.0–39.9`: Very low / Muy baja.

Band labels must not imply hiring probability.

## Confidence

Job confidence is a weighted average of requirement confidence values. It is an evidence-quality signal, not a statistical probability.

## Audit

The local audit validates:

- every job index is present once;
- required requirements are evaluated;
- no invented requirement is accepted;
- candidate evidence exists in `CandidateProfessionalProfile`;
- `FULL` requires `SUPPORTED` evidence;
- missing and conflict states are consistent;
- weights and effective weights are mathematically valid;
- penalties are allowed and capped;
- final scores, averages and bands match the formula.

## Fingerprint

The fingerprint uses reduced candidate evidence, reduced job analysis, language, model, prompt version, methodology version, dimension weights and scoring constants.

If nothing changes, the app reuses the existing valid compatibility report.

`Reprocesar compatibilidad` ignores the fingerprint, repeats semantic evaluation and scoring, and preserves the last valid report if the new attempt fails.

## Numeric example

Two requirements with the same weight:

```text
FULL + SUPPORTED = 1.00
PARTIAL + SUPPORTED = 0.65

Dimension score = ((1.00 + 0.65) / 2) × 100 = 82.5
```

Indirect inferred:

```text
INDIRECT + INFERRED = 0.35 × 0.75 = 0.2625
```

## Limitations

This stage does not predict hiring, benchmark against other candidates, run final LinkedIn/ATS audits, write messages, generate cover letters, create posts, export documents or store history.

## Script

```bash
uv run python scripts/test_compatibility_analysis.py
uv run python scripts/test_compatibility_analysis.py --show-details
```
