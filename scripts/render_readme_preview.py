"""Render README.md with a GitHub-like stylesheet (light and dark side by side)
for layout/contrast checks. Run from the project root:

    python scripts/render_readme_preview.py

Writes readme-preview.html at the project root (safe to delete afterwards).
"""

from base64 import b64encode
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
md_text = (ROOT / "README.md").read_text(encoding="utf-8")

converted = markdown.markdown(
    md_text,
    extensions=["fenced_code", "tables", "sane_lists"],
    output_format="html5",
)

# The preview server serves only this file, so inline the diagram as a data URI.
png_b64 = b64encode((ROOT / "docs" / "architecture-diagram.png").read_bytes()).decode()
converted = converted.replace(
    'src="docs/architecture-diagram.png"',
    f'src="data:image/png;base64,{png_b64}"',
)

PANE_CSS = "max-width:892px; margin:0 auto; padding:32px 24px;"


def themed(bg: str, fg: str, border: str, code_bg: str, head_border: str, muted: str) -> str:
    inner = converted
    inner = inner.replace(
        "<blockquote>",
        f'<blockquote style="margin:0 0 16px; padding:0 1em; color:{muted}; '
        f'border-left:.25em solid {border}">',
    )
    inner = inner.replace(
        "<pre>",
        f'<pre style="background:{code_bg}; padding:16px; border-radius:6px; '
        f'overflow:auto; font-size:85%; line-height:1.45">',
    )
    inner = inner.replace(
        "<code>", "<code style='font-family:ui-monospace,SFMono-Regular,Consolas,monospace'>"
    )
    inner = inner.replace(
        "<table>",
        "<table style='border-collapse:collapse; display:block; width:max-content; "
        "max-width:100%; overflow:auto'>",
    )
    inner = inner.replace(
        "<th>",
        f"<th style='border:1px solid {border}; padding:6px 13px; background:{code_bg}'>",
    )
    inner = inner.replace("<td>", f"<td style='border:1px solid {border}; padding:6px 13px'>")
    inner = inner.replace("<li>", "<li style='margin-top:.25em'>")
    inner = inner.replace("<p>", "<p style='margin:0 0 16px'>")
    inner = inner.replace(
        "<h2>",
        f"<h2 style='font-size:1.5em; border-bottom:1px solid {head_border}; "
        f"padding-bottom:.3em; margin:24px 0 16px; font-weight:600'>",
    )
    inner = inner.replace(
        "<img ",
        f"<img style='max-width:100%; display:block; background:{bg}; "
        f"border:1px solid {border}; border-radius:6px' ",
    )
    return f"""
<section style="background:{bg}; color:{fg}; margin:0; padding:0;
    font-family:-apple-system,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif;
    font-size:16px; line-height:1.5;">
  <div style="{PANE_CSS}">
    <div style="color:{muted}; font-size:11px; letter-spacing:1px; text-transform:uppercase;
        margin-bottom:12px;">GitHub rendering simulation (bg {bg})</div>
    {inner}
  </div>
</section>"""


html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>README GitHub-style preview</title></head>
<body style="margin:0">
<div style="background:#8b949e; color:#0d1117; padding:6px; text-align:center; font:12px sans-serif;">
Local simulation of GitHub README rendering — light zone first, dark zone below</div>
{themed("#ffffff", "#1f2328", "#d1d9e0", "#f6f8fa", "#d1d9e0", "#59636e")}
{themed("#0d1117", "#c9d1d9", "#3d444d", "#151b23", "#3d444d", "#9198a1")}
</body></html>"""

out = ROOT / "readme-preview.html"
out.write_text(html, encoding="utf-8")
print(f"wrote {out} ({len(html)} bytes)")
