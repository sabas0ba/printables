"""OpenSCADによるSTL生成と閉じたメッシュ・寸法の検査。追加依存なし。"""
from pathlib import Path
from collections import Counter
import hashlib
import argparse
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
PARTS = {"base": 1, "mast": 2, "splice": 1, "rail": 4, "holder": 8,
         "pin26": 16, "pin28": 4, "pin40": 2, "pin52": 4,
         "coupon04": 1, "coupon06": 1, "coupon08": 1}


def ground(path):
    """曲面分割による微小な底面浮きを除き、印刷物の最低点をZ=0にする。"""
    low = min(p[2] for p in vertices(path))
    if abs(low) > 1e-9:
        def move(match):
            return f"vertex {match[1]} {match[2]} {float(match[3])-low:.9g}"
        path.write_text(re.sub(r"vertex\s+([-\d.e+]+)\s+([-\d.e+]+)\s+([-\d.e+]+)",
                               move, path.read_text()))
    return low


def vertices(path):
    text = path.read_text()
    return [tuple(map(float, row)) for row in re.findall(
        r"vertex\s+([-\d.e+]+)\s+([-\d.e+]+)\s+([-\d.e+]+)", text)]


def inspect(path):
    points = vertices(path)
    assert points and len(points) % 3 == 0, path
    edges = Counter()
    adjacency = {}
    volume = 0.0
    for i in range(0, len(points), 3):
        a, b, c = points[i:i+3]
        volume += (a[0]*(b[1]*c[2]-b[2]*c[1]) +
                   a[1]*(b[2]*c[0]-b[0]*c[2]) +
                   a[2]*(b[0]*c[1]-b[1]*c[0])) / 6
        for u, v in [(a,b), (b,c), (c,a)]:
            edges[tuple(sorted((u,v)))] += 1
            adjacency.setdefault(u,set()).add(v)
            adjacency.setdefault(v,set()).add(u)
    assert all(n == 2 for n in edges.values()), f"開いたメッシュ: {path}"
    seen = set()
    todo = [points[0]]
    while todo:
        p = todo.pop()
        if p not in seen:
            seen.add(p)
            todo.extend(adjacency[p] - seen)
    assert len(seen) == len(adjacency), f"分離した部品: {path}"
    low = [min(p[k] for p in points) for k in range(3)]
    high = [max(p[k] for p in points) for k in range(3)]
    size = [round(b-a,3) for a,b in zip(low,high)]
    assert abs(low[2]) < .001, (path,low)
    assert all(a<=b for a,b in zip(size,[320,310,315])), (path,size)
    assert volume > 0, path
    return {"size_mm":size,"solid_volume_cm3":round(volume/1000,2),
            "triangles":len(points)//3,"watertight":True,"components":1,
            "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts",nargs="+",choices=list(PARTS),default=list(PARTS))
    parser.add_argument("--scenes",nargs="+",choices=["assembly","shoes","hardware","frame"],
                        default=["assembly","shoes","hardware","frame"])
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    (ROOT/".work").mkdir(exist_ok=True)
    report = {}
    for part,count in PARTS.items():
        target = OUT / f"{part}.stl"
        if part in args.parts:
            result = subprocess.run(["openscad","-o",str(target),"-D",f'part="{part}"',
                                     str(ROOT/"src/stand.scad")],capture_output=True,text=True)
            (ROOT/".work"/f"{part}.log").write_text(result.stdout+result.stderr)
            result.check_returncode()
        shift = ground(target)
        report[part] = {"quantity":count,"print_z_shift_mm":-shift,**inspect(target)}
        print(f"Validated: {part}",flush=True)
    for part in args.scenes:
        subprocess.run(["openscad","-o",str(OUT/f"{part}.stl"),"-D",f'part="{part}"',
                        str(ROOT/"src/stand.scad")],check=True,capture_output=True)
    for check in ["sole_interference", "pin_interference"]:
        target=ROOT/".work"/f"{check}.stl"
        target.unlink(missing_ok=True)
        collision = subprocess.run(["openscad", "-o", str(target),
                                    "-D", f'part="{check}"', str(ROOT/"src/stand.scad")],
                                   capture_output=True,text=True)
        (ROOT/".work"/f"{check}.log").write_text(collision.stderr)
        # かかとの接触線は許容し、面・体積を持つ交差は失敗にする。
        empty = "Current top level object is empty" in collision.stderr
        contact_only = (collision.returncode == 0 and target.exists() and
                        not vertices(target) and re.search(r"Facets:\s+0\b",collision.stderr))
        assert empty or contact_only, collision.stderr
        print(f"Passed: {check}",flush=True)
    report["assembly_checks"] = {"sole_interference":False,
                                 "installed_pin_interference":False,
                                 "nominal_hole_clearance_mm":float(re.search(
                                     r"clearance\s*=\s*([\d.]+)",
                                     (ROOT/"src/stand.scad").read_text())[1]),
                                 "vertical_shoe_gap_mm":10,
                                 "sole_inner_face_separation_mm":90,
                                 "loaded_height_mm":650}
    (OUT/"validation.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
