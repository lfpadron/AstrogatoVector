# OpenAI Integration

The OpenAI integration exposes one encapsulated client used by the diagnostic call, candidate professional profile extraction, target jobs analysis and LinkedIn profile generation.

## Flow

```text
OpenAISettings
      ↓
OpenAIService
      ↓
responses.parse
      ↓
OpenAIDiagnosticResponse
      ↓
OpenAIDiagnosticResult
      ↓
Interfaz segura
```

## Configuration

OpenAI settings are read from environment variables and validated with Pydantic:

```env
OPENAI_API_KEY=
OPENAI_MODEL_FAST=
OPENAI_MODEL_QUALITY=
OPENAI_TIMEOUT_SECONDS=60
OPENAI_MAX_RETRIES=1
OPENAI_DIAGNOSTIC_ENABLED=true
```

Use model names available to the configured account. The fast model is used for diagnostics. The quality model is used for candidate extraction, target jobs analysis and LinkedIn profile generation.

## Responses API and Structured Outputs

The service uses the official `OpenAI` SDK client and the Responses API:

```python
client.responses.parse(
    model=model_name,
    input=[...],
    text_format=ExpectedPydanticModel,
)
```

The `text_format` argument receives a Pydantic model. The parsed object is read from `response.output_parsed`. The service rejects empty, unparsed or incorrectly typed structured outputs and does not attempt manual JSON repair.

## Timeout and Retries

The client is created with explicit values:

- `OPENAI_TIMEOUT_SECONDS`, default `60`, maximum `600`.
- `OPENAI_MAX_RETRIES`, default `1`, maximum `3`.

No manual retry loop is added. Retry behavior is limited to the SDK configuration.

## Error Handling

Known SDK errors are mapped to safe categories and user-facing messages:

- authentication;
- permission;
- model not found;
- rate limit;
- timeout;
- connection;
- invalid request;
- temporary server errors;
- unexpected errors.

The UI never displays stack traces, headers, request bodies or API keys.

## Privacy

The diagnostic sends only two fixed prompt files:

- `prompts/diagnostic_system.txt`
- `prompts/diagnostic_user.txt`

It does not send CV text, LinkedIn text, job descriptions, uploaded files, session state or user-entered content. Prompts and responses are not logged or stored in files.

The API key is read from the environment, held as a `SecretStr`, used only to construct the SDK client and never stored in Streamlit session state.

## Diagnostic vs Professional Processing

The sidebar diagnostic verifies:

- API key authentication;
- model availability;
- Responses API availability;
- Pydantic structured parsing;
- safe metadata capture.

The main `Procesar` button validates input, extracts documents, resolves links, builds `validated_input`, runs candidate extraction with `OPENAI_MODEL_QUALITY`, runs target jobs analysis with the same quality model, evaluates semantic compatibility and then generates the optimized LinkedIn profile.

The candidate extraction call sends the effective CV and optional LinkedIn profile. It does not send target job descriptions.

The target jobs analysis call sends only job indices, titles, optional companies, effective descriptions, source and optional URL. It does not send CV text, LinkedIn text or the extracted candidate profile.

The compatibility call sends only the audited `CandidateProfessionalProfile`, audited `TargetMarketAnalysis` and output language. It does not send the full CV, raw LinkedIn text, raw job descriptions, URLs, generated LinkedIn profile text or banner content. OpenAI classifies semantic coverage; final scores, bands and penalties are calculated locally.

The LinkedIn profile generation call sends only the audited `CandidateProfessionalProfile`, audited `TargetMarketAnalysis` and output language. It does not send the full CV, raw LinkedIn text, raw job descriptions, URLs, prompts, raw model responses or API metadata.

## CLI Diagnostic

Run:

```bash
uv run python scripts/openai_diagnostic.py
```

If configuration is missing, the script prints:

```text
OpenAI diagnostic: configuration incomplete
```

If configured and successful, it prints only safe metadata such as model, structured response validity and latency.
