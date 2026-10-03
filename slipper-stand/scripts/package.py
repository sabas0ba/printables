"""再現用ソースと試作成果物を一つの配布ZIPにまとめる。"""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import zipfile
import numpy
import matplotlib
from build import ROOT, OUT

binary = Path(shutil.which("openscad"))
environment = {
    "openscad_version": subprocess.run([str(binary),"--version"],capture_output=True,text=True).stderr.strip(),
    "openscad_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    "python_version":platform.python_version(),
    "numpy_version":numpy.__version__,
    "matplotlib_version":matplotlib.__version__,
    "nix_environment_verified":False,
}
(OUT/"environment.json").write_text(json.dumps(environment,indent=2)+"\n")
with zipfile.ZipFile(OUT/"slipper-stand-prototype-v03.zip","w",zipfile.ZIP_DEFLATED) as archive:
    for folder in [ROOT/"src",ROOT/"scripts",ROOT/"docs",OUT]:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix not in [".zip",".pyc"]:
                archive.write(path,path.relative_to(ROOT))
    archive.write(ROOT/"README.md","README.md")
    archive.write(ROOT/".gitignore",".gitignore")
print(OUT/"slipper-stand-prototype-v03.zip")
