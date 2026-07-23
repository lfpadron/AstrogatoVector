# LinkedIn Profile Generation

This stage generates an editable LinkedIn profile proposal from two audited inputs:

```text
CandidateProfessionalProfile
              +
TargetMarketAnalysis
              ↓
Prompt delimitado
              ↓
Responses API
              ↓
LinkedInProfileOutput
              ↓
Auditoría de respaldo
              ↓
Contenido editable
```

## Purpose

The output is a textual LinkedIn profile proposal: banner copy, headline, About, rewritten experience, prioritized skills, ATS keywords and review notes.

The market can guide vocabulary and priority. It cannot prove that the candidate has a capability.

## Evidence vs Market

`CandidateProfessionalProfile` is the source of truth for jobs, responsibilities, achievements, skills, education, certifications, languages, leadership and industries.

`TargetMarketAnalysis` supplies terminology, role family, keywords, common requirements, tools and market priorities.

The generation call does not receive the full CV, files, raw job descriptions, URLs, prompts, raw model responses or previous API metadata.

## Banner Text

The banner section contains `primary_line`, `specialty_line`, optional `supporting_line`, `visual_concept` and `recommended_template`.

The allowed templates are:

- `professional_light`
- `professional_dark`
- `executive_blue`
- `technology_clean`

The PNG banner is rendered in the next local step from the editable banner text; it does not change `LinkedInProfileOutput`.

## Headline

The headline must stay within 220 characters, declare the exact character count and use only supported candidate capabilities as current strengths.

Market keywords can appear only when they are also supported by the candidate, or when they are clearly framed for future development outside current-capability text.

## About

The About text is editable, preserves paragraphs and is audited for first-person wording, sensitive data, unsupported tools, invented numbers and keyword stuffing.

If evidence is thin, the model should keep the About shorter and add review notes instead of filling with generic claims.

## Experience

One `RewrittenExperienceEntry` is required for every employment entry in the candidate profile. The audit checks employer correspondence, source role correspondence, seniority inflation, unsupported claims, numbers and unsupported market-only terms.

## Skills

Prioritized skills should be supported by the candidate. Inferred skills are allowed only cautiously and should appear after supported skills. Missing skills should not appear as prioritized skills.

## ATS Keywords

ATS keywords come from the target market. Each keyword marks whether the candidate supports it, the evidence status, frequency in jobs and recommended sections.

Missing keywords may remain visible as gaps, but must not be recommended for headline, About or experience as current capabilities.

## Local Audit

The deterministic audit validates:

- banner limits and templates;
- headline length, character count, keywords and cliches;
- About support, numbers, sensitive data and keyword use;
- one rewritten experience per source job;
- supported skills and ranking;
- ATS keyword frequency, support and placements;
- seniority consistency;
- review notes for conflicts and gaps.

Errors reject the generated output. Warnings remain visible for human review.

## Editable State

The audited object is stored separately from `linkedin_profile_edit_state`. Editing text areas and selections does not modify the audited model and does not trigger a new OpenAI call.

## Fingerprint

The fingerprint uses reduced candidate evidence, reduced market analysis, output language, model and prompt version. If unchanged, the app reuses the valid generated profile.

`Reprocesar perfil de LinkedIn` forces a fresh call and keeps the last valid output if the new attempt fails.

## Script

Run a fictitious-data smoke test:

```bash
uv run python scripts/test_linkedin_profile_generation.py
```

English:

```bash
uv run python scripts/test_linkedin_profile_generation.py --language en
```

If OpenAI configuration is missing, the script exits safely with:

```text
LinkedIn profile generation: configuration incomplete
```

## Limitations

This stage does not score compatibility, run final LinkedIn/ATS audits, create messages, cover letters, posts or general exports.
