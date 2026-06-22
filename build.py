#!/usr/bin/env python3
"""Build script para GitHub Actions: genera sitios estáticos a partir de master.json"""

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from web_generator import UltraWebGenerator

SITES_DIR = Path("sites")
DIST_DIR = Path("dist")

def main():
    gen = UltraWebGenerator()
    DIST_DIR.mkdir(exist_ok=True)

    for master_path in SITES_DIR.glob("*/master.json"):
        slug = master_path.parent.name
        print(f"🔨 Generando sitio: {slug}")

        with open(master_path, encoding="utf-8") as f:
            payload = json.load(f)

        result = gen.generate(payload)
        if not result["valid"]:
            print(f"❌ Error en {slug}: {result['errors']}")
            continue

        src = Path(result["path"])
        dst = DIST_DIR / slug
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

        # Copiar también a la raíz del repositorio
        index_dst = Path("index.html")
        shutil.copy2(dst / "index.html", index_dst)
        shutil.copy2(dst / "style.css", Path("style.css"))
        shutil.copy2(dst / "script.js", Path("script.js"))

        print(f"✅ {slug} generado")

if __name__ == "__main__":
    main()
