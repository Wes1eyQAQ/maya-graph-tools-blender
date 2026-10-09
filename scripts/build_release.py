from pathlib import Path
import hashlib
import zipfile

root = Path(__file__).resolve().parents[1]
archive = root / "downloads" / "MayaGraphTools-1.26.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
    for name in ("__init__.py", "i18n.py"):
        output.write(root / "MayaGraphTools" / name, "MayaGraphTools/" + name)
    output.write(root / "LICENSE", "MayaGraphTools/LICENSE")
    output.write(root / "docs" / "USER_GUIDE.md", "MayaGraphTools/USER_GUIDE.md")
(root / "downloads" / "SHA256SUMS.txt").write_text(
    hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n", encoding="utf-8")
print(archive)
