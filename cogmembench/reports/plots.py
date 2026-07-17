from __future__ import annotations

from pathlib import Path
from typing import Any


def write_task_success_svg(aggregate: dict[str, Any], path: Path) -> Path:
    rows = [(name, data["metrics"].get("task_success", {}).get("mean") or 0) for name, data in aggregate["conditions"].items()]
    width, height = 760, 80 + 55 * len(rows)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="20" y="30" font-family="sans-serif" font-size="18">CogMemBench task success</text>']
    for i, (name, value) in enumerate(rows):
        y = 55 + i * 55
        parts.append(f'<text x="20" y="{y + 22}" font-family="sans-serif" font-size="13">{name}</text>')
        parts.append(f'<rect x="190" y="{y}" width="{500 * value:.1f}" height="28" fill="#5267a8"/>')
        parts.append(f'<text x="{200 + 500 * value:.1f}" y="{y + 20}" font-family="sans-serif" font-size="12">{value:.3f}</text>')
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts))
    return path

