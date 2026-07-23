# Candidate Extraction

This stage extracts a structured professional profile from the effective CV and, when available, the current LinkedIn profile text.

It does not analyze target jobs. Job descriptions are intentionally excluded from this OpenAI call so requirements from vacancies cannot be attributed to the candidate.

## Flow

```text
CV + perfil opcional
        ↓
Filtro de privacidad
        ↓
Prompt delimitado
        ↓
Responses API
        ↓
CandidateProfessionalProfile
        ↓
Auditoría local
        ↓
Perfil aceptado o rechazado
```

## Sources

The CV is the main professional source. LinkedIn is complementary. If both sources differ, the extraction should preserve the contradiction instead of silently overriding the CV.

The user message is delimited with `<ASTROGATO_VECTOR_INPUT>`, `<CV>` and `<LINKEDIN_PROFILE>`. Vacancy text is never included in this payload.

## Evidence States

- `SUPPORTED`: explicit source evidence exists and must include a short reference.
- `INFERRED`: reasonable inference that must remain cautious.
- `MISSING`: useful information that is absent or not demonstrable.
- `CONFLICT`: contradictory or incompatible source information.

References use a `source_section` and a short `source_excerpt`. Excerpts stay in the original source language.

## Confidence

Confidence is an internal review aid, not a scientific probability:

- `1.0`: direct and clear textual evidence.
- `0.75-0.99`: direct evidence with minor normalization.
- `0.50-0.74`: reasonable inference.
- Below `0.50`: should not be classified as `SUPPORTED`.

## Privacy Filter

Before the OpenAI call, the app applies a limited preventive filter for evident sensitive patterns such as CURP, RFC, account-like numbers, payment-card-like numbers, official IDs and declared passwords.

This filter is not full anonymization and does not guarantee that every sensitive datum is detected. It preserves professional names, companies, roles, cities, technologies and career context.

## Structured Outputs

The extraction uses the official OpenAI SDK, Responses API and `responses.parse` with `text_format=CandidateProfessionalProfile`. The app does not request free-form JSON and does not repair invalid JSON manually.

## Local Audit

After Pydantic validation, a deterministic audit checks references, duplicate skills, duplicate employment entries, unsupported figures, confidence ranges, missing evidence and unreasonable total years.

Errors reject the result. Warnings remain visible for human review.

## Fingerprint

The Streamlit session stores a SHA-256 fingerprint built from the effective CV, LinkedIn profile, output language, prompt version and model. If the sources did not change and a valid result exists, the app reuses the result to avoid duplicate calls.

`Reprocesar perfil` forces a fresh call. If that attempt fails, the last valid profile remains visible and the failed attempt is reported.

## Limitations

This stage does not generate headline, About, optimized experience, compatibility scores, market keywords, audits, messages, posts, exports or banner assets.

The evidence audit is deterministic and conservative. It can catch obvious unsupported references and figures, but it is not a substitute for human review.

## Script

Run a fictitious-data extraction test:

```bash
uv run python scripts/test_candidate_extraction.py
```

If OpenAI configuration is missing, the script exits safely with:

```text
Candidate extraction: configuration incomplete
```
