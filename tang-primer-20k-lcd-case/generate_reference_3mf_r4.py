#!/usr/bin/env python3
"""Create an interactive, color-separated 3MF reference assembly.

The file is for spatial inspection, not direct slicing: it includes the LCD
and the official Dock+Core (envelope box, or a STEP-derived mesh when one is
given) as non-printable reference objects.
"""

from __future__ import annotations

import argparse
import html
import tempfile
import zipfile
from pathlib import Path

from assembly_r4 import Part, assembled_parts


ARCHIVE_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""
RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def indexed_mesh(part: Part):
    vertices: list[tuple[float, float, float]] = []
    lookup: dict[tuple[float, float, float], int] = {}
    triangles: list[tuple[int, int, int]] = []
    for tri in part.triangles:
        indices = []
        for point in tri:
            key = tuple(round(value, 5) for value in point)
            if key not in lookup:
                lookup[key] = len(vertices)
                vertices.append(key)
            indices.append(lookup[key])
        triangles.append(tuple(indices))
    return vertices, triangles


def generate(output: Path, input_dir: Path, dock_stl: Path | None, spec_key: str) -> None:
    parts = assembled_parts(input_dir, dock_stl, spec_key)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".model", delete=False) as stream:
        model_path = Path(stream.name)
        stream.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        stream.write('<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n')
        stream.write(f' <metadata name="Title">Tang Primer 20K R4 {spec_key} reference assembly - DO NOT SLICE</metadata>\n')
        stream.write(' <metadata name="Description">Color-separated assembled inspection model; LCD and official hardware are reference objects.</metadata>\n')
        stream.write(' <resources>\n')
        stream.write('  <basematerials id="1">\n')
        for part in parts:
            rgba = part.color.lstrip("#") + f"{round(part.alpha * 255):02X}"
            stream.write(f'   <base name="{html.escape(part.name)}" displaycolor="#{rgba}"/>\n')
        stream.write('  </basematerials>\n')
        for index, part in enumerate(parts, start=2):
            vertices, triangles = indexed_mesh(part)
            object_type = "other" if ("LCD" in part.name and "retainer" not in part.name) or "Official Dock" in part.name else "model"
            stream.write(f'  <object id="{index}" name="{html.escape(part.name)}" type="{object_type}" pid="1" pindex="{index - 2}">\n')
            stream.write('   <mesh><vertices>\n')
            for x, y, z in vertices:
                stream.write(f'    <vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>\n')
            stream.write('   </vertices><triangles>\n')
            for a, b, c in triangles:
                stream.write(f'    <triangle v1="{a}" v2="{b}" v3="{c}"/>\n')
            stream.write('   </triangles></mesh>\n  </object>\n')
        stream.write(' </resources>\n <build>\n')
        for index in range(2, len(parts) + 2):
            stream.write(f'  <item objectid="{index}"/>\n')
        stream.write(' </build>\n</model>\n')
    try:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            # Fixed entry timestamps keep the package byte-reproducible.
            for name, data in (
                ("[Content_Types].xml", CONTENT_TYPES.encode("utf-8")),
                ("_rels/.rels", RELATIONSHIPS.encode("utf-8")),
                ("3D/3dmodel.model", model_path.read_bytes()),
            ):
                info = zipfile.ZipInfo(name, ARCHIVE_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data, compresslevel=9)
    finally:
        model_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("output/release"))
    parser.add_argument("--dock-step-stl", type=Path,
                        help="STEP-derived Dock mesh; default: the Dock envelope box")
    parser.add_argument("--spec", choices=("43", "50"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(args.output, args.input, args.dock_step_stl, args.spec)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
