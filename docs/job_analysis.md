# Job Analysis

This stage analyzes two to six target job postings and consolidates the selected market language, responsibilities, requirements, skills, tools and keywords.

It describes the market. It does not describe the candidate.

## Flow

```text
2–6 vacantes
      ↓
Normalización
      ↓
Prompt delimitado
      ↓
Responses API
      ↓
TargetMarketAnalysis
      ↓
Auditoría local
      ↓
Mercado objetivo aceptado o rechazado
```

## Candidate Separation

The OpenAI call for this stage receives only:

- output language;
- job index;
- job title;
- optional company;
- effective job description;
- optional URL as reference text.

It does not receive CV text, LinkedIn text, `CandidateProfessionalProfile`, candidate skills, employment history or evidence references.

## Individual Analysis

Each `JobAnalysis` preserves the input `job_index`, title and company. It extracts role summary, inferred seniority, responsibilities, requirements, technical skills, soft skills, leadership skills, tools, industries, education, language and certification requirements, and exact keywords.

## Consolidated Analysis

`TargetMarketAnalysis` consolidates the full set into:

- target role family;
- suggested target titles;
- dominant seniority;
- market summary;
- common responsibilities;
- common requirements;
- recurrent keywords and frequency;
- technical, leadership and business skills;
- tools and technologies;
- industries;
- differentiators.

Common elements should be backed by more than one vacancy. Items found in only one posting can appear as differentiators, but should not be presented as common. Because vacancy wording is often paraphrased or terse, weak lexical support for common elements is shown as a warning instead of blocking the whole analysis.

## Required vs Desirable

`required=true` should be used only when the job text contains clear signals such as `required`, `must`, `se requiere`, `mínimo`, `essential` or similar wording.

Signals such as `preferred`, `nice to have`, `plus`, `deseable` or `valorado` should usually remain desirable.

When the deterministic audit cannot confirm mandatory wording, it records a warning for human review. It does not reject the entire market analysis only because a requirement was marked as required.

## Keywords and Frequency

Keywords preserve market wording while also providing a normalized form. Frequency means the number of unique job postings where the concept appears. `job_indices` must match the postings supporting that keyword.

## Seniority

Seniority is inferred from title, scope, leadership, autonomy, organizational level and explicit years or requirements. It does not use the candidate’s age or profile.

## Local Audit

The deterministic audit checks:

- every input job has one analysis;
- there are no extra or duplicate indices;
- titles and companies correspond;
- keyword frequencies and job indices are consistent;
- keywords and tools are backed by descriptions;
- required requirements have mandatory-language support, reported as warnings when wording is weak;
- common responsibilities and requirements appear in at least two jobs, reported as warnings when support is weak;
- seniority is not absurd for obvious title signals.

Critical errors reject the result. Warnings remain visible for review. The audit is intentionally stricter for concrete keywords, tools, missing job analyses, duplicate indices and impossible frequencies than for broad requirement/responsibility phrasing.

## Size Control

Descriptions are normalized and consecutive duplicate lines are removed. Long descriptions are reduced explicitly by keeping beginning and end with:

```text
[... CONTENIDO INTERMEDIO OMITIDO POR LÍMITE TÉCNICO ...]
```

When truncation happens, the result includes a warning.

## Privacy

Job postings normally do not contain the user’s personal data, but the same limited preventive redaction filter is applied to obvious sensitive patterns. Company names, locations, roles and technologies are preserved.

## Fingerprint

The session fingerprint uses job index, title, company, effective description, URL, source, output language, model and prompt version. It never includes CV or LinkedIn data.

If the fingerprint did not change and a valid result exists, the app reuses it. `Reprocesar vacantes` forces a fresh call and keeps the last valid market analysis if the new attempt fails.

## Script

Run a fictitious-data job analysis test:

```bash
uv run python scripts/test_job_analysis.py
```

If OpenAI configuration is missing, the script exits safely with:

```text
Job analysis: configuration incomplete
```
