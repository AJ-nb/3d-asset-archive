"""Copy the main self-built production snapshots and the short-film deliverables."""
from pathlib import Path
import hashlib
import json
import shutil

BASE=Path(__file__).resolve().parent.parent
PROV=BASE/"provenance"
DEST=BASE/"06_自建工程与成片"
REGISTRY=json.loads((PROV/"process-history.json").read_text(encoding="utf8"))
CLIP=Path("D:/oc/output/dji-osmo-pocket-4p-cg15")
EXTRAS=["Pulse-15s.mp4","Pulse-contact.jpg","分镜剪辑表.csv","镜头数据.csv","15秒CG分镜脚本.md","15秒执行分镜.md","production/Pulse-score.wav","review/film-qc.json","review/reopen-final.json","review/browser-playback.json","review/decode-trial/desktop-first.json","review/decode-trial/browser-playback.json","review/previous-high-encode/browser-playback-retest.json"]
def sha(path):
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()
def copy(source,target,kind,version):
    target.parent.mkdir(parents=True,exist_ok=True)
    original=sha(source)
    if target.exists() and sha(target)!=original: raise RuntimeError(f"Conflict at {target}")
    if not target.exists(): shutil.copy2(source,target)
    if sha(target)!=original: raise RuntimeError(f"Copy mismatch at {target}")
    return dict(source_path=str(source),archive_path=target.relative_to(BASE).as_posix(),
                sha256=original,bytes=target.stat().st_size,kind=kind,version=version)
files=[]
for row in REGISTRY["original_editable_files"]:
    source=Path(row["source_path"])
    result=copy(source,DEST/source.parent.name/source.name,"editable_source",row["version"])
    assert row["sha256"]==result["sha256"]
    files.append(result)
for rel in EXTRAS:
    files.append(copy(CLIP/rel,DEST/CLIP.name/rel,"film" if rel.endswith(".mp4") else "film_support","CG15"))
(PROV/"editable-inputs.json").write_text(json.dumps(files,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print(f"Copied and verified {len(files)} assets.")
