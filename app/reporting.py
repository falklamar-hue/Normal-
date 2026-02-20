from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models import Article, SavedSearch


def render_report_html(report_name: str, period_label: str, search_infos: list[SavedSearch], articles: list[Article]) -> str:
    rows = "\n".join(
        f"<tr><td>{a.published_at.strftime('%Y-%m-%d %H:%M')}</td><td>{a.source}</td><td>{a.title}</td><td><a href='{a.url}'>{a.url}</a></td></tr>"
        for a in articles
    )
    if not rows:
        rows = "<tr><td colspan='4'>Ingen treff.</td></tr>"

    search_list = "".join(
        f"<li><b>{s.name}</b>: inkluder [{s.include_terms}] / ekskluder [{s.exclude_terms or '-'}]</li>"
        for s in search_infos
    )

    return f"""
<html><head><meta charset='utf-8'><style>
body {{ font-family: Segoe UI, Arial, sans-serif; color:#222; }}
table {{ border-collapse: collapse; width:100%; }}
th, td {{ border:1px solid #d0d0d0; padding:8px; text-align:left; vertical-align:top; }}
th {{ background:#f3f3f3; }}
a {{ color:#004b95; }}
</style></head><body>
<h2>{report_name}</h2>
<p><b>Periode:</b> {period_label}</p>
<h3>Søkekriterier</h3>
<ul>{search_list}</ul>
<h3>Treff</h3>
<table><thead><tr><th>Dato</th><th>Kilde</th><th>Tittel</th><th>Link</th></tr></thead><tbody>{rows}</tbody></table>
</body></html>
"""


def export_report_html(file_path: Path, html: str) -> None:
    file_path.write_text(html, encoding="utf-8")


def default_report_filename(prefix: str = "rapport") -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"{prefix}_{timestamp}.html")
