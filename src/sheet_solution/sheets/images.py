"""Sheet Solution — embedded-image extraction (xlsx).

When a check is marked for human review and the sheet cell references an
image (passport photo, etc.), the tool extracts the embedded image so the
reviewer can confirm it visually. Extraction is deterministic and offline.

xlsx stores images under `xl/media/` inside the zip. We pull them out by
their relationship ids; no network, no model.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractedImage:
    rid: str            # relationship id, e.g. "rId5"
    source_path: str    # relative zip path, e.g. "xl/media/image1.png"
    out_path: str       # where it was written
    bytes: int


def extract_images(xlsx_path: Path, out_dir: Path) -> list[ExtractedImage]:
    """Extract every embedded image from an .xlsx into out_dir/media/."""
    out_dir.mkdir(parents=True, exist_ok=True)
    media_dir = out_dir / "media"
    media_dir.mkdir(exist_ok=True)
    found: list[ExtractedImage] = []
    with zipfile.ZipFile(xlsx_path) as zf:
        names = zf.namelist()
        media = [n for n in names if n.startswith("xl/media/")]
        for name in sorted(media):
            data = zf.read(name)
            fname = Path(name).name
            (media_dir / fname).write_bytes(data)
            rid = re.sub(r"\W", "", Path(name).stem) or "media"
            found.append(ExtractedImage(
                rid=f"rId{rid}", source_path=name,
                out_path=str(media_dir / fname), bytes=len(data)))
    return found
