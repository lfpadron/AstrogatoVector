# Astrogato Vector Data Contracts

Schema version: `1.0`

These contracts define the structured data that AI stages produce or consume. They are Pydantic v2 models, reject unknown fields and are designed to generate JSON Schema for Structured Outputs.

## Stage Flow

```text
CandidateInput
    ↓
CandidateProfessionalProfile
    ↓
CandidateExtractionResult + EvidenceAuditResult
    ↓
TargetMarketAnalysis
    ↓
JobAnalysisResult + JobAnalysisAuditResult
    ↓
LinkedInProfileOutput
    ↓
LinkedInProfileGenerationResult + LinkedInProfileAuditResult
    ↓
BannerRenderInput + BannerRenderResult + BannerAuditResult
    ↓
CompatibilityReport
    ↓
AuditReport
    ↓
FinalDeliverablePackage
    ↓
TargetedCV + TargetedCVGenerationResult + TargetedCVAuditResult + TargetedCVATSAudit
    ↓
ApplicationCommunicationKit + ApplicationCommunicationGenerationResult
    ↓
ProfessionalBrandPlan + EditorialPlanGenerationResult
    ↓
ApplicationResult
```

In the real implementation, some stages may run in parallel after the initial candidate extraction. The final audit only runs after the professional profile, market analysis, LinkedIn profile and compatibility report are validated.

## Model Purposes

- `CandidateInput`: normalized session-only input after CV extraction and controlled link reading.
- `CandidateProfessionalProfile`: evidence-based professional extraction from the CV and optional LinkedIn text.
- `CandidateExtractionResult`: safe metadata and accepted profile for the candidate extraction stage.
- `EvidenceAuditResult`: deterministic validation findings for evidence, figures and duplicated claims.
- `PrivacyFilterResult`: limited preventive redaction summary without original sensitive values.
- `TargetMarketAnalysis`: consolidated analysis of target jobs, requirements, seniority, skills and keywords.
- `JobAnalysisResult`: safe metadata and accepted market analysis for the target jobs stage.
- `JobAnalysisAuditResult`: deterministic validation findings for job correspondence, keywords, requirements and tools.
- `LinkedInProfileOutput`: textual LinkedIn profile proposal, including headline, about, rewritten experience, prioritized skills, ATS keywords and a textual banner concept.
- `LinkedInProfileGenerationResult`: safe metadata and accepted generated LinkedIn profile for the profile-generation stage.
- `LinkedInProfileAuditResult`: deterministic validation findings for generated headline, About, experience, skills, ATS keywords and banner text.
- `BannerRenderInput`: session-only editable banner text and selected visual template for local PNG rendering.
- `BannerRenderResult`: local in-memory PNG render summary. PNG bytes are excluded from serialization.
- `BannerAuditResult`: deterministic PNG validation for signature, dimensions, contrast, safe zone and overflow.
- `CompatibilityReport`: per-job score using fixed weighted dimensions plus requirement matches and recommended actions.
- `AuditReport`: local final audit for LinkedIn positioning and orientative ATS alignment, generated only from `CandidateProfessionalProfile`, `TargetMarketAnalysis`, `LinkedInProfileOutput` and `CompatibilityReport`.
- `FinalDeliverablePackage`: local export-ready package using validated results plus explicit LinkedIn edit state when available. It does not contain bytes or original source documents.
- `TargetedCV`: export-ready CV for one specific vacancy, generated only from `CandidateProfessionalProfile`, one `JobAnalysis`, one `JobCompatibility` and output language.
- `TargetedCVGenerationResult`: safe metadata and accepted generated CV for one vacancy.
- `TargetedCVAuditResult`: local evidence audit for targeted CV content, roles, dates, skills, keywords and metrics.
- `TargetedCVATSAudit`: local ATS-oriented score for one targeted CV using fixed explainable weights.
- `ApplicationCommunicationKit`: cover letter, recruiter message, application email and subjects for one vacancy, generated only from structured profile, job, compatibility, validated targeted CV and output language.
- `ApplicationCommunicationGenerationResult`: safe metadata and accepted communication kit for one vacancy.
- `ProfessionalBrandPlan`: four-week LinkedIn editorial plan with exactly twelve professional posts, generated only from structured profile, market, compatibility, final audit and output language.
- `EditorialPlanGenerationResult`: safe metadata and accepted professional brand plan.
- `CommunicationOutput`: headhunter messages and one cover letter per job.
- `FourWeekContentPlan`: legacy eight-post content suggestion contract kept for backward-compatible examples.
- `ApplicationResult`: top-level bundle for the complete future output. It must not include the full CV, HTML, files, API keys or Streamlit/session objects.

## Evidence Status

- `SUPPORTED`: the claim is backed by at least one short `EvidenceReference`.
- `INFERRED`: the claim is plausible from the material but not directly stated.
- `MISSING`: the information was not found.
- `CONFLICT`: the material contains inconsistent information and `notes` must explain the conflict.

Future AI stages must not invent employers, dates, metrics, certifications, languages, education or years of experience. Numeric achievements should only appear when the source material supports them.

## Compatibility Score

Each `JobCompatibility` contains exactly six dimensions:

- `experience_responsibilities`: 0.30
- `skills_knowledge`: 0.25
- `tools_technologies`: 0.15
- `leadership_management`: 0.12
- `industry_business`: 0.10
- `education_certifications_languages`: 0.08

OpenAI only classifies semantic coverage. The local scoring engine converts coverage, evidence status, priority and required/preferred flags into requirement scores, then calculates dimensions and the final score.

Final score:

```text
score_before_penalties = sum(dimension_score * effective_dimension_weight)
final_score = max(0, min(100, score_before_penalties - penalties))
```

Original weights must sum to `1.0`. If a dimension is not requested by a job, it is not scored as zero; its weight is redistributed across evaluated dimensions. The score is orientative, is not a hiring probability and must be reviewed by a person.

See `docs/compatibility_scoring.md` for the full methodology.

## LinkedIn vs ATS Audit

`LinkedInPositioningAudit` evaluates clarity, keyword coverage, consistency, credibility, banner alignment and readability as an orientative positioning check. It does not claim to reproduce LinkedIn ranking.

`ATSAudit` estimates keyword, requirement, skills, experience, title and consistency alignment. It does not reproduce any specific ATS and does not guarantee automated screening outcomes.

Both audits use deterministic local scoring, explainable component weights, findings with evidence, Quick Wins and prioritized recommendations. They do not call OpenAI and do not generate recruiter messages, cover letters, posts or downloadable documents.

## Final Package Export

`FinalDeliverablePackage` consolidates validated profile, market, LinkedIn, compatibility and audit results. It may use explicit user edits from the LinkedIn edit state and marks the manifest as `user-edited` or `generated-and-audited`.

Binary exports are not part of the Pydantic model. Markdown, HTML, DOCX, PDF and ZIP bytes are generated in memory and audited separately before download.

## Targeted CV Export

`TargetedCV` produces one Markdown, DOCX and PDF CV per vacancy plus a ZIP package under `targeted-cvs/`.

The exported CV files must not contain scores, gaps, evidence excerpts, audit findings, prompts, raw responses, request IDs or tokens. Internal review information is kept in `review-summary.json` inside each ZIP vacancy folder.

The DOCX layout is one-column and ATS-friendly, without tables, images or visual chrome. PDF output uses selectable text.

## Professional Brand Editorial Plan

`ProfessionalBrandPlan` contains four `EditorialCalendarWeek` objects and exactly twelve `LinkedInPostPlan` items. The calendar uses only Monday, Wednesday and Friday slots and avoids absolute dates.

Each post includes hook, body, CTA, hashtags, keywords, evidence used, review claims and character count. Local audit validates length, diversity, evidence support, confidentiality, CTA quality and hashtag safety.

Exports are generated in memory as Markdown, HTML, DOCX, PDF and `linkedin-editorial-plan.zip`. The ZIP contains README, manifest, calendar files and folders `week01` to `week04`. It must not contain images, videos, carousels, raw source documents, prompts, raw model responses, LinkedIn API integrations, tracking or auto-publishing artifacts.

## Structured Outputs Readiness

The main models generate JSON Schema through `model_json_schema()`. Banner render bytes are excluded and are not intended for OpenAI Structured Outputs. Use:

```bash
uv run python scripts/export_schemas.py
```

The script writes schemas to `generated_schemas/`. That directory is intentionally ignored in `.gitignore` because schemas are reproducible build artifacts and should not contain user data.

## Safety Boundaries

The contracts must not contain:

- complete CV text inside final generated results;
- HTML;
- document bytes;
- API keys or credentials;
- cookies;
- Streamlit objects;
- session state objects;
- sensitive personal data not explicitly required for professional positioning.

All generated text must keep review notes or placeholders when personalization or evidence is missing.
