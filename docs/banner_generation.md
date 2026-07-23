# LinkedIn Banner PNG Generation

This stage renders a programmatic LinkedIn banner PNG from the editable banner text already produced by `LinkedInProfileOutput`.

```text
Contenido textual editable
          ↓
Validación
          ↓
Plantilla visual
          ↓
Layout tipográfico
          ↓
Pillow
          ↓
Auditoría PNG
          ↓
Preview y descarga
```

## Dimensions

The renderer always produces an in-memory PNG of `1584 x 396` pixels using `LINKEDIN_BANNER_FORMAT = "PNG"`.

The download filename is fixed as:

```text
astrogato-vector-linkedin-banner.png
```

## Safe Zone

The conservative profile photo exclusion area is:

```python
{"x": 0, "y": 150, "width": 420, "height": 246}
```

The text block starts at `x = 500`, with top, right and bottom margins. The renderer calculates text bounding boxes and rejects any layout that intersects the safe zone or leaves the canvas.

## Templates

Four templates are available:

- `professional_light`: light background, dark blue text, orange accent and subtle geometric lines.
- `professional_dark`: navy background, white text, pale secondary text and quiet abstract shapes.
- `executive_blue`: deep blue gradient, white text, small orange accent and subtle executive lines.
- `technology_clean`: blue-gray background, clear text and restrained node/grid decoration.

No logo, mascot, watermark, external image, remote background or AI image generation is used.

## Fonts

`services/font_service.py` searches common system fonts in this order of preference: Segoe UI, Arial, Calibri, Verdana, DejaVu Sans, Liberation Sans, Noto Sans and Helvetica.

If no TrueType font is available, Pillow's fallback font is used and the render result includes a warning instead of failing the whole application.

## Text Layout

The renderer uses a deterministic layout algorithm:

1. start from template font sizes;
2. wrap by words and manual line breaks;
3. measure real pixel bounds with Pillow;
4. reduce font sizes gradually;
5. accept the first readable layout within limits;
6. reject content that still overflows at minimum sizes.

It does not split words, silently truncate text or insert ellipses. The hierarchy is primary line, specialty line and optional supporting line, with a maximum of six total rendered lines.

## Validation

Before rendering, the service normalizes repeated spaces, trims fields, validates required lines, validates the template and blocks obvious sensitive data such as email, phone, RFC and CURP. URLs produce a warning.

The renderer validates:

- dimensions;
- contrast;
- safe zone;
- overflow;
- PNG signature;
- basic Pillow integrity.

## Fingerprint

`BANNER_RENDERER_VERSION = "1.0"` participates in the fingerprint with the editable banner text, selected template, dimensions and visual concept.

Streamlit stores only the latest transient values in session state:

- `banner_render_fingerprint`
- `banner_render_result`
- `banner_image_bytes`
- `banner_last_render`

If the fingerprint has not changed, the UI reuses the existing PNG bytes in memory. Editing text or changing the style marks the preview as stale until the user presses `Regenerar banner PNG`.

## Streamlit Flow

The banner section shows editable text fields, `Estilo visual`, `Generar banner PNG` or `Regenerar banner PNG`, a preview with `st.image`, a validation block and `Descargar banner PNG` only when the render and audit pass.

The main `Procesar` flow still ends at `LinkedInProfileOutput`. The PNG is generated only after the user explicitly presses the banner button.

## Script

Run a safe fictitious-data smoke test:

```bash
uv run python scripts/test_banner_generation.py
```

Save local diagnostic previews only with:

```bash
uv run python scripts/test_banner_generation.py --save-preview
```

Previews are written to `tmp/banner_previews/`, which is ignored by Git and must not be used with real personal data.

## Limitations

This stage does not implement compatibility scoring, final LinkedIn/ATS audits, messages, cover letters, posts, general DOCX exports, persistence, history, uploaded backgrounds, logos, profile photos or image generation APIs.
