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
CommunicationOutput
    ↓
FourWeekContentPlan
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
- `CommunicationOutput`: headhunter messages and one cover letter per job.
- `FourWeekContentPlan`: eight LinkedIn post suggestions, exactly two per week for four weeks.
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
