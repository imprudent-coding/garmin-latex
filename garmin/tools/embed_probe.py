"""Esperimento: genera risorse jsonData con TUTTO il bundle, per verificare se
il compilatore Connect IQ accetta un .prg con gli appunti incorporati e quanto pesa.

Uso: python embed_probe.py notes-bundle.zip <cartella risorse di uscita>
"""
import json
import sys
import zipfile
from pathlib import Path

bundle, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
z = zipfile.ZipFile(bundle)
m = json.loads(z.read("manifest.json"))
xml = ["<resources>"]
total = 0
for i, (key, info) in enumerate(sorted(m["resources"].items())):
    data = json.loads(z.read(info["file"]))
    name = f"e{i}.json"
    text = json.dumps(data["chunks"], ensure_ascii=False)
    (out / name).write_text(text, encoding="utf-8")
    total += len(text.encode("utf-8"))
    xml.append(f'    <jsonData id="E{i}" filename="{name}" />')
xml.append("</resources>")
(out / "embedded.xml").write_text("\n".join(xml), encoding="utf-8")
print(f"risorse: {len(m['resources'])}, dati JSON: {total / 1024:.0f} KB")
