#!/usr/bin/env python3
"""Build the site's real ONS England/Wales map paths and row avatars.

One-off dependency: python -m pip install 'shapely>=2,<3'
Run: python scripts/build_maps.py

Maps use British National Grid (EPSG:27700), preserve the same national
orientation in every avatar and are decorative, simplified boundary diagrams.
The crime refresh does not need to regenerate geography every month.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

from shapely import make_valid
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data"
MAPS = ROOT / "public" / "maps"
CACHE = ROOT / ".cache" / "geography"
BASE = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
SOURCES = {
    "forces": {
        "title": "Police Force Areas (December 2024) Boundaries EW BGC",
        "url": BASE + "Police_Force_Areas_Dec_2024_EW_BGC/FeatureServer/0",
        "catalogue": "https://www.data.gov.uk/dataset/977aac4f-29f6-4d63-8b8e-b5815038bc19/police-force-areas-december-2024-boundaries-ew-bgc",
        "codeField": "PFA24CD",
        "nameField": "PFA24NM",
    },
    "regions": {
        "title": "Regions (December 2024) Boundaries EN BGC",
        "url": BASE + "Regions_December_2024_Boundaries_EN_BGC/FeatureServer/0",
        "catalogue": "https://www.arcgis.com/home/item.html?id=125a1e3fca4940e5941d85c585b96aba",
        "codeField": "RGN24CD",
        "nameField": "RGN24NM",
    },
}
QUERY = {
    "f": "geojson",
    "where": "1=1",
    "outFields": "*",
    "outSR": "27700",
    "maxAllowableOffset": "300",
}
WIDTH, HEIGHT, PADDING = 300, 360, 9


def download(key: str, refresh: bool) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (key + ".geojson")
    if refresh or not path.exists():
        url = SOURCES[key]["url"] + "/query?" + urllib.parse.urlencode(QUERY)
        request = urllib.request.Request(url, headers={"User-Agent": "CrimeCompareGeography/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.load(response)
        if "features" not in payload or "error" in payload:
            raise RuntimeError(f"ONS {key} download did not return features")
        path.write_text(json.dumps(payload), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def polygon_parts(geometry):
    if geometry.geom_type == "Polygon":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for component in geometry.geoms:
            yield from polygon_parts(component)


def simplify(geometry, outline=False):
    # Keep meaningful offshore islands (including the Isles of Scilly), but
    # omit sub-pixel coastal rocks. Preserve the City of London, itself 2.9 km².
    # Dissolving separately generalised boundaries creates thin seams. National
    # and Welsh silhouettes show exterior coastline only, so those cannot turn
    # into spurious inland holes. Other areas keep meaningful holes such as the
    # City of London within the Metropolitan force.
    parts = [
        Polygon(p.exterior, [] if outline else [r for r in p.interiors if Polygon(r).area >= 1_000_000])
        for p in polygon_parts(make_valid(geometry)) if p.area >= 1_000_000
    ]
    return make_valid(unary_union(parts).simplify(650, preserve_topology=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Redownload ONS boundaries")
    args = parser.parse_args()

    source_data = {key: download(key, args.refresh) for key in SOURCES}
    assert len(source_data["forces"]["features"]) == 43, "Expected all 43 E&W territorial police forces"
    assert len(source_data["regions"]["features"]) == 9, "Expected nine English regions"

    geometries = {}
    metadata = {}
    for group, collection in source_data.items():
        fields = SOURCES[group]
        for feature in collection["features"]:
            properties = feature["properties"]
            code = properties[fields["codeField"]]
            geometries[code] = make_valid(shape(feature["geometry"]))
            metadata[code] = {
                "name": properties[fields["nameField"]],
                "type": "force" if group == "forces" else "region",
            }

    forces = [geometry for code, geometry in geometries.items() if metadata[code]["type"] == "force"]
    # Dissolve actual force boundaries to create Wales and the national outline.
    geometries["W92000004"] = unary_union([g for code, g in geometries.items() if code.startswith("W15")])
    metadata["W92000004"] = {"name": "Wales", "type": "region"}
    geometries["K04000001"] = unary_union(forces)
    metadata["K04000001"] = {"name": "England and Wales", "type": "nation"}

    min_x, min_y, max_x, max_y = geometries["K04000001"].bounds
    scale = min((WIDTH - 2 * PADDING) / (max_x - min_x), (HEIGHT - 2 * PADDING) / (max_y - min_y))
    offset_x = (WIDTH - (max_x - min_x) * scale) / 2
    offset_y = (HEIGHT - (max_y - min_y) * scale) / 2

    def project(x, y):
        return round(offset_x + (x - min_x) * scale, 2), round(offset_y + (max_y - y) * scale, 2)

    def svg_path(geometry, outline=False):
        paths = []
        for polygon in polygon_parts(simplify(geometry, outline=outline)):
            for ring in [polygon.exterior, *polygon.interiors]:
                points = [project(x, y) for x, y in ring.coords]
                paths.append("M" + "L".join(f"{x:g},{y:g}" for x, y in points) + "Z")
        return "".join(paths)

    outline = svg_path(geometries["K04000001"], outline=True)
    areas = {}
    for code, geometry in geometries.items():
        center = geometry.representative_point()
        areas[code] = {
            **metadata[code],
            "path": svg_path(geometry, outline=code in ["W92000004", "K04000001"]),
            "centroid": list(project(center.x, center.y)),
            "map": "/maps/" + code + ".svg",
        }
        assert areas[code]["path"], f"Missing path for {code}"
    assert len(areas) == 54

    DATA.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)
    document = {
        "viewBox": f"0 0 {WIDTH} {HEIGHT}",
        "projection": "EPSG:27700",
        "boundaryDate": "2024-12",
        "outline": outline,
        "areas": areas,
    }
    (DATA / "geography.json").write_text(json.dumps(document, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")

    attribution = "Source: Office for National Statistics licensed under the Open Government Licence v.3.0. Contains OS data © Crown copyright and database right 2024."
    for code, area in areas.items():
        # City of London's actual shape is below one avatar pixel. A small
        # locator ring keeps it findable without enlarging its real boundary.
        locator = ""
        if code == "E23000034":
            cx, cy = area["centroid"]
            locator = f'<circle cx="{cx}" cy="{cy}" r="4" fill="none" stroke="#0a3fb7" stroke-width="1.8"/>'
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{document["viewBox"]}" role="img" aria-labelledby="title">'
            f'<title id="title">{escape(area["name"])} within England and Wales</title>'
            f'<desc>{escape(attribution)} Boundaries simplified for display.</desc>'
            f'<path d="{outline}" fill="#e8ecf2" stroke="#aab6c6" stroke-width="0.8" fill-rule="evenodd"/>'
            f'<path d="{area["path"]}" fill="#0a3fb7" fill-rule="evenodd"/>'
            f'{locator}</svg>\n'
        )
        (MAPS / (code + ".svg")).write_text(svg, encoding="utf-8")

    sources = {
        "publisher": "Office for National Statistics",
        "boundaryDate": "2024-12",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "licence": "Open Government Licence v3.0",
        "licenceUrl": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        "licensingGuidance": "https://www.ons.gov.uk/methodology/geography/licences",
        "attribution": attribution,
        "sources": [{"title": s["title"], "url": s["url"], "catalogueUrl": s["catalogue"]} for s in SOURCES.values()],
        "query": QUERY,
        "processing": "ONS December 2024 BGC boundaries queried in British National Grid at 300m maximum allowable offset; polygons made valid, coastal components and holes below 1 km² removed, topology-preserving 650m simplification, projected uniformly into a 300 × 360 SVG viewBox. Wales and England/Wales outlines dissolved from police force polygons with all interior holes removed to prevent seams between independently generalised polygons. The City of London SVG adds a locator ring around its true shaded boundary because it is smaller than one avatar pixel.",
        "purpose": "Visual orientation only. These simplified paths must not be used to assign crimes or addresses to areas.",
    }
    (DATA / "geography-sources.json").write_text(json.dumps(sources, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {len(areas)} maps and geography.json ({(DATA / 'geography.json').stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
