"""Render the exported parts, drawer mechanism and date wheels."""

import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from generate import BASE_HEIGHT, STACK_PITCH, TRAY_Y, TRAY_Z, DRAWER_Y, DRAWER_Z, DIALS


DIRECTORY = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "stl_renderer", DIRECTORY.parent / "mi-vacuum-cleaner-mini" / "render.py"
)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def mesh(name, offset=(0,0,0)):
    vertices, normals = renderer.read_binary_stl(DIRECTORY / f"{name}.stl")
    return vertices + np.array(offset), normals


def combine(parts):
    return np.concatenate([part[0] for part in parts]), np.concatenate([part[1] for part in parts])


def drawer_mesh(offset=(0,0,0)):
    parts = [mesh("basket")]
    for name, (x,y,_,_) in zip(("month-dial", "day-dial"), DIALS):
        parts += [mesh(name, (x,y,3.4)), mesh("dial-clip", (x,y,6.9))]
    vertices, normals = combine(parts)
    return vertices + np.array(offset), normals


def outline_top(image, vertices, normals, region, padding=42):
    """Visible CAD crease edges make coplanar-colored top features readable."""
    x0, y0, width, height = region
    projected = vertices[:,:,:2]
    lo, hi = projected.min(axis=(0,1)), projected.max(axis=(0,1))
    scale = min((width-2*padding)/(hi[0]-lo[0]),
                (height-2*padding-24)/(hi[1]-lo[1]))
    points = (projected-(lo+hi)/2)*scale
    points[:,:,0] += x0+width/2
    points[:,:,1] = y0+height/2-points[:,:,1]+12
    zbuffer = np.full((image.height,image.width), -np.inf)
    edges = {}
    for triangle, projected_triangle, normal in zip(vertices,points,normals):
        a,b,c = projected_triangle
        xmin,xmax = max(x0,int(np.floor(projected_triangle[:,0].min()))), min(x0+width-1,int(np.ceil(projected_triangle[:,0].max())))
        ymin,ymax = max(y0,int(np.floor(projected_triangle[:,1].min()))), min(y0+height-1,int(np.ceil(projected_triangle[:,1].max())))
        denominator = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(denominator) > 1e-8 and xmin <= xmax and ymin <= ymax:
            yy,xx = np.ogrid[ymin:ymax+1,xmin:xmax+1]
            wa = ((b[1]-c[1])*(xx+.5-c[0])+(c[0]-b[0])*(yy+.5-c[1]))/denominator
            wb = ((c[1]-a[1])*(xx+.5-c[0])+(a[0]-c[0])*(yy+.5-c[1]))/denominator
            wc = 1-wa-wb
            z = wa*triangle[0,2]+wb*triangle[1,2]+wc*triangle[2,2]
            patch = zbuffer[ymin:ymax+1,xmin:xmax+1]
            inside = (wa >= 0)&(wb >= 0)&(wc >= 0)
            patch[inside] = np.maximum(patch[inside],z[inside])
        for j,k in ((0,1),(1,2),(2,0)):
            key = tuple(sorted((tuple(triangle[j]),tuple(triangle[k]))))
            edges.setdefault(key, []).append(normal)
    pixels = image.load()
    for edge, adjacent in edges.items():
        if len(adjacent) > 1 and all(np.dot(adjacent[0],n) > .999 for n in adjacent[1:]):
            continue
        edge = np.array(edge)
        xy = (edge[:,:2]-(lo+hi)/2)*scale
        xy[:,0] += x0+width/2
        xy[:,1] = y0+height/2-xy[:,1]+12
        samples = max(2,int(np.linalg.norm(xy[1]-xy[0])*2)+1)
        for t in np.linspace(0,1,samples):
            point = xy[0]*(1-t)+xy[1]*t
            x,y = int(point[0]),int(point[1])
            z = edge[0,2]*(1-t)+edge[1,2]*t
            if x0 <= x < x0+width and y0 <= y < y0+height and z >= zbuffer[y,x]-.12:
                pixels[x,y] = (109,128,136)


def main():
    vertices, normals = combine([mesh("rack"), drawer_mesh((0,DRAWER_Y,DRAWER_Z))])
    views = Image.new("RGB", (1600, 1200), "#e9eef0")
    for region, u, v, depth, label in (
        ((24, 24, 960, 560), (1, 0, 0), (0, 1, 0), (0, 0, 1),
         "TOP | Module: 220 x 198 mm incl. date handle"),
        ((24, 608, 960, 360), (1, 0, 0), (0, 0, 1), (0, -1, 0),
         "FRONT | 220 x 79.5 mm"),
        ((1008, 24, 568, 944), (0, 1, 0), (0, 0, 1), (1, 0, 0),
         "END | 198 x 79.5 mm"),
    ):
        renderer.draw_view(views, vertices, normals, region, u, v, depth, label)
    outline_top(views, vertices, normals, (24,24,960,560))
    draw = ImageDraw.Draw(views)
    for index, line in enumerate((
        "Frame: 220 x 140 x 79.5 | Basket incl. handle: 190 x 195 x 12 mm",
        "Stack pitch: 75 | Rail top: Z=5 | Basket rim top (installed): Z=17 mm",
        "8 V lanes, 22 mm pitch | Two 2.4 mm wide support stations | Mesh: 4 x 4 mm",
        "Printed date wheels: month 1-12 / day 1-31 | Snap-fit clips: prototype",
    )):
        draw.text((40, 994 + index * 46), line, fill="#25333c", font=renderer.font(23))
    views.save(DIRECTORY / "views.png", optimize=True)
    u, v, depth = (0.866, -0.5, 0), (0.25, 0.433, 0.866), (-0.433, -0.75, 0.5)
    preview = Image.new("RGB", (1400, 1050), "#e9eef0")
    pulled = combine([mesh("rack"), drawer_mesh((0,DRAWER_Y-70,DRAWER_Z))])
    renderer.draw_view(preview, *pulled, (24,24,1352,1002), u,v,depth,
                       "SLIDING DRYING BASKET | 8 V lanes + harvest date", padding=65)
    preview.save(DIRECTORY / "preview.png", optimize=True)
    assembly = Image.new("RGB", (1400, 1400), "#e9eef0")
    base_v, base_n = mesh("base")
    tray_v, tray_n = mesh("drip-tray")
    parts = [mesh("base"), mesh("drip-tray", (0,TRAY_Y,TRAY_Z))]
    for i in range(3):
        height = BASE_HEIGHT + STACK_PITCH*i
        parts += [mesh("rack",(0,0,height)), drawer_mesh((0,DRAWER_Y,height+DRAWER_Z))]
    renderer.draw_view(assembly, *combine(parts), (24,24,1352,1352), u,v,depth,
                       "THREE TIERS | Independent baskets and drip tray", padding=70)
    assembly.save(DIRECTORY / "assembly.png", optimize=True)
    drawer = Image.new("RGB", (1400, 1100), "#e9eef0")
    pulled = combine([mesh("rack", (0,0,BASE_HEIGHT)), mesh("base"),
                      drawer_mesh((0,DRAWER_Y,BASE_HEIGHT+DRAWER_Z)),
                      mesh("drip-tray", (0,TRAY_Y-85,TRAY_Z))])
    renderer.draw_view(drawer, *pulled, (24,24,1352,1052), u,v,depth,
                       "DRIP TRAY | Pull forward to empty", padding=70)
    drawer.save(DIRECTORY / "drawer.png", optimize=True)
    detail = Image.new("RGB", (1500, 1150), "#e9eef0")
    renderer.draw_view(detail, *drawer_mesh(), (24,24,920,1102),
                       (1,0,0),(0,1,0),(0,0,1), "BASKET TOP | 190 x 195 mm", padding=55)
    detail_vertices, detail_normals = drawer_mesh()
    outline_top(detail, detail_vertices, detail_normals, (24,24,920,1102), padding=55)
    exploded = [mesh("basket")]
    for name, (x,y,_,_) in zip(("month-dial", "day-dial"), DIALS):
        exploded += [mesh(name, (x,y,20)), mesh("dial-clip", (x,y,33))]
    ev, en = combine(exploded)
    # Crop geometry to handle for the exploded assembly detail.
    selected = np.max(ev[:,:,1], axis=1) < -61
    renderer.draw_view(detail, ev[selected], en[selected], (960,24,516,800),
                       u,v,depth,"DATE WHEELS | Exploded", padding=45)
    draw = ImageDraw.Draw(detail)
    for i, line in enumerate(("Left: month / Right: day", "Wheel over head, clip into neck",
                               "Arrow indicates selected value", "No detent: check date after moving",
                               "Clip flex/holding force untested")):
        draw.text((975,860+i*45),line,fill="#25333c",font=renderer.font(20))
    detail.save(DIRECTORY / "basket-detail.png", optimize=True)
    accessory = Image.new("RGB", (1600, 1180), "#e9eef0")
    for part_vertices, face_normals, region, u2, v2, d2, label in (
        (base_v, base_n, (24, 24, 764, 480), (1, 0, 0), (0, 1, 0), (0, 0, 1),
         "BASE TOP | 244 x 164 mm"),
        (base_v, base_n, (24, 528, 764, 300), (1, 0, 0), (0, 0, 1), (0, -1, 0),
         "BASE FRONT | Height 42.5 mm"),
        (tray_v, tray_n, (812, 24, 764, 480), (1, 0, 0), (0, 1, 0), (0, 0, 1),
         "TRAY TOP | 228 x 168 mm incl. grip"),
        (tray_v, tray_n, (812, 528, 764, 300), (0, 1, 0), (0, 0, 1), (1, 0, 0),
         "TRAY END | Height 12 mm"),
    ):
        renderer.draw_view(accessory, part_vertices, face_normals, region, u2, v2, d2, label)
    draw = ImageDraw.Draw(accessory)
    for index, line in enumerate((
        "Base: basket seat Z=38 | Tray rails Z=3 | Inward supports: 45 degrees",
        "Tray body: 228 x 156 x 12 mm | Floor / walls: 2.4 mm | No drain holes",
        "Installed tray center Y=-2 | Basket bottom to tray rim: 23 mm",
        "3 tiers with base: 267.5 mm | 4 tiers with base: 342.5 mm",
        "Fit/withdrawal checked in CAD. Printed watertightness and load capacity untested.",
    )):
        draw.text((40, 868 + index * 48), line, fill="#25333c", font=renderer.font(23))
    accessory.save(DIRECTORY / "accessories.png", optimize=True)


if __name__ == "__main__":
    main()
