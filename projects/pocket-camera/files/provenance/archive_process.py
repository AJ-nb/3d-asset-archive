"""Copy the existing process-evidence set with byte-level verification."""
from pathlib import Path
import hashlib
import json
import shutil

from PIL import Image

OUT = Path(__file__).resolve().parent.parent
ROOT = Path("D:/oc/output")
PROV = OUT / "provenance"
PHOTOS = OUT / "03_建模过程原片"
BASE = "dji-osmo-pocket-4p"
VERSIONS = {v: ROOT / (BASE + suffix) for v, suffix in [
    ("V1", ""), ("V2", "-v2"), ("V3", "-v3"), ("V4", "-v4"),
    ("V5", "-v5"), ("V6", "-v6"), ("V7", "-v7"), ("CG15", "-cg15")]}
SHOP = "https://se-cdn.djiits.com/tpc/uploads/sku/cover/9a749ee117fa62efd044b6163a035bb7@ultra.png"
ORIGIN = SHOP.replace("@ultra", "@origin")
ARM = "https://www-cdn.djiits.com/dps/26bd7b053062572541b9b99281f75616.jpg"
SOURCES = {
    "project": {"credit": "项目原始建模输出或基于模型计算的图表", "external": []},
    "reference": {"credit": "DJI 商店官方商品图，原项目裁去附件并保留透明通道", "external": [SHOP]},
    "front": {"credit": "图中含 DJI 商店商品正面参考或从该图测得的投影，模型与分析属本项目", "external": [SHOP]},
    "arm": {"credit": "左侧参考图来自 DJI 官网，V3 与 V4 对照为项目建模输出", "external": [ARM]},
    "controls": {"credit": "左列是 DJI 官网机身正斜侧和底部照片，中、右列是项目 V1、V2 模型", "external": ["https://www-cdn.djiits.com/dps/989fdacd9ada761ba9d9c872fc492a8c.jpg","https://www-cdn.djiits.com/dps/9bdc03324d8442a62df588b990ec53d2.jpg"]},
    "glass": {"credit": "左列为 DJI 商店官方图局部，右侧为项目模型", "external": [ORIGIN]},
    "display": {"credit": "整机为项目渲染；出现亮屏时屏内相册风景取自 DJI 商店图，裁切范围见屏显来源记录", "external": [ORIGIN]},
}
# Version, path, local filename, category, source credit, what the image documents.
PLATES = [
    ("V1", "references/dji-store-front-device-transparent.png", "01_参考_官方正面裁图.png", "比例参考", "reference", "照片读点与比例依据。单独引用需标注 DJI。"),
    ("V1", "previews/04-orthographic.png", "02_V1_整机五向正交.png", "初版形体", "project", "初版已生成的五个正交方向，具备机身、屏幕、云台和双镜头。"),
    ("V1", "previews/05-reference-fit.png", "03_V1_正面照片配准.png", "初版比例", "front", "正视渲染、参考图与投影差异。"),
    ("V2", "previews/06-wall-section.png", "04_V2_握把壁厚截面.png", "壁厚", "project", "握把实体截面和模型厚度读数。"),
    ("V2", "previews/07-detail-comparison.jpg", "05_V2_结构细节记录.jpg", "尺寸与细节", "controls", "官网、V1、V2 的屏肩、镜圈、按键与底部接口。"),
    ("V3", "previews/08-section-z112.png", "06_V3_Z112逐毫米截面.png", "模型切片", "front", "项目原有截面查看器在 Z112 的截面与版本对照，内含官方照片参考。"),
    ("V4", "previews/同机位正侧面对照.jpg", "07_V4_支臂正侧面改前改后.jpg", "云台重建", "project", "V3 与 V4 同机位，能直接看到支臂、后桥与镜头外壳相对位置。"),
    ("V4", "previews/连接结构对照.jpg", "08_V4_云台背斜视参考与改型.jpg", "云台重建", "arm", "DJI 后斜视与 V3、V4 同方向素模的遮挡关系。"),
    ("V5", "previews/六向灰模.jpg", "09_V5_整机六向灰模.jpg", "灰模", "project", "该版六方向统一灰色表面，检查肩线、底部和侧面。"),
    ("V5", "previews/clay-lens.png", "10_V5_双镜头单材质近景.png", "灰模", "project", "独立的镜头灰模原始视图。"),
    ("V5", "previews/镜头精修对照.jpg", "11_V5_镜头破面修复对照.jpg", "表面修复", "project", "两版镜头近景。正式色彩图的 V5 增加条形反射光，几何另有灰模检查。"),
    ("V6", "previews/四个活动接口.jpg", "12_V6_四个活动接口.jpg", "装配", "project", "云台与屏轴实切及分件色块，可说明支承或旋转接口。"),
    ("V6", "previews/俯仰干涉对照.png", "13_V6_俯仰干涉截面.png", "运动检查", "project", "V5 与 V6 的后壳和叉架切片，关系据模型计算。"),
    ("V6", "previews/线框与两种光照.jpg", "14_V6_线框和掠射光.jpg", "材质前检查", "project", "镜头前后、掠射光和局部网格同板。"),
    ("V7", "optics/正面造型与官网对照.jpg", "15_V7基线_双摄重新拟形.jpg", "镜口拟形", "glass", "官网、V6 与 V7 基线的双镜头轮廓。"),
    ("V7", "optics/广角保护窗双光照对照.jpg", "16_V7基线_广角保护窗双光照.jpg", "材质与布光", "glass", "保持 V7 镜片几何，改变灯的入射方向检查保护窗边、高光和镀膜观感。"),
    ("V7", "rig/validation/rig-poses.jpg", "17_V7_刚性关节动作灰模.jpg", "绑定验证", "project", "相同相机和中性表面的六个测试姿态。"),
    ("V7", "review/mesh-final/01-face-clay.png", "18_V7终版_镜头正面白模.png", "终版素模", "project", "双镜头正面，WorkBench 单一材质。"),
    ("V7", "review/mesh-final/01-face-wire.png", "19_V7终版_镜头正面线框.png", "终版求值线框", "project", "与正面素模同机位，叠加模型可见边。"),
    ("V7", "review/mesh-final/02-joint-clay.png", "20_V7终版_云台后侧白模.png", "终版素模", "project", "后桥、轴肩、握把侧面。"),
    ("V7", "review/mesh-final/02-joint-wire.png", "21_V7终版_云台后侧线框.png", "终版求值线框", "project", "与后侧素模同机位，叠加模型可见边。"),
    ("V7", "review/mesh-final/03-internal-clay.png", "22_V7终版_支承内构白模.png", "终版素模", "project", "隔离显示轴承支座与转轴。"),
    ("V7", "review/mesh-final/03-internal-wire.png", "23_V7终版_支承内构线框.png", "终版求值线框", "project", "与支承内构素模同机位，叠加模型可见边。"),
    ("V7", "rig/validation/final/casting-comparison.jpg", "24_V7终版_压铸支臂法线与材质回读.jpg", "材质回读", "project", "原生 Blender、GLB 回读、关闭法线图的局部布光比较。"),
    ("V7", "renders/渲染联系表.jpg", "25_V7终版_八机位成品联系表.jpg", "成品联系表", "display", "同一发布版的八个交付机位。"),
    ("CG15", "Pulse-contact.jpg", "26_15秒CG_成片联络表.jpg", "CG 应用", "display", "另行制作的 15 秒短片，抽取代表帧作为静帧交付之后的延伸。")
]
DOCS = {
    "V1":["build_pocket.py","build_gimbal.py","references/外观参考与坐标.md","建模校验.json"],
    "V2":["尺寸与官网校核.md","建模校验.json"],
    "V3":["1mm截面与修正记录.md","1mm截面对照.html","section-diff.csv","work/section-metrics.json"],
    "V4":["云台连接精修记录.md","side-profile-diff.csv","connector-z-1mm.csv"],
    "V5":["精修与复核记录.md"],
    "V6":["装配精修与验收.md","assembly/v6/逐件装配清单.csv"],
    "V7":["验收记录.md","optics/镜头正面核验.md","sections/整机三向逐毫米截面.html","optics/镜头组件逐毫米截面.html","review/Final线框素模核验.md","review/source-equivalence-views.json","review/render-evidence.json","rig/骨架与动作说明.md","rig/validation/poses.log","rig/validation/final/delivery.json","studio/display-source.json"],
    "CG15":["15秒执行分镜.md","镜头数据.csv","review/film-qc.json"]
}
MODELS = {"V1":["DJI-Osmo-Pocket-4P-Classic-Black.blend"], "V2":["DJI-Osmo-Pocket-4P-Classic-Black-V2.blend"], "V3":["DJI-Osmo-Pocket-4P-Classic-Black-V3.blend"], "V4":["DJI-Osmo-Pocket-4P-Classic-Black-V4.blend"], "V5":["DJI-Osmo-Pocket-4P-Classic-Black-V5.blend"], "V6":["DJI-Osmo-Pocket-4P-V6.blend"], "V7":["DJI-Osmo-Pocket-4P-V7.blend","DJI-Osmo-Pocket-4P-V7-Final.blend"], "CG15":["Pulse-15s.blend"]}

def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file,"sha256").hexdigest()

def archive(source, dest):
    if not source.is_file():
        raise FileNotFoundError(source)
    dest.parent.mkdir(parents=True,exist_ok=True)
    sha = digest(source)
    if dest.exists() and digest(dest) != sha:
        raise RuntimeError(f"Conflicting archived file: {dest}")
    if not dest.exists():
        shutil.copy2(source,dest)
    if digest(dest) != sha:
        raise ValueError(f"Unverified copy: {dest}")
    return {"source_path":str(source),"archive_path":dest.relative_to(OUT).as_posix(),"sha256":sha,"bytes":source.stat().st_size,"copy_verified":True}

def main():
    images=[]
    for v, rel, name, kind, credit, detail in PLATES:
        source=VERSIONS[v]/rel
        copied=archive(source,PHOTOS/name)
        with Image.open(source) as im:
            im.load()
            size=list(im.size)
        images.append({**copied,"version":v,"source_relative":rel,"category":kind,"width":size[0],"height":size[1],"detail":detail,"credits":SOURCES[credit],"recreated_for_this_archive":False,"role":("原项目保存的外部参考裁图" if credit=="reference" else "原项目保存的过程图或交付图"),"presentation_time":("终版复核时输出的同机位素模/线框" if "mesh-final/" in rel else "该版本过程或交付记录")})
    docs=[{**archive(VERSIONS[v]/p,PROV/"同期依据"/v/p),"version":v} for v, paths in DOCS.items() for p in paths]
    models=[{"version":v,"source_path":str(VERSIONS[v]/p),"sha256":digest(VERSIONS[v]/p),"bytes":(VERSIONS[v]/p).stat().st_size} for v, paths in MODELS.items() for p in paths]
    manifest={"schema_version":1,"source_scope":"V1–V7 与 CG15 原项目；各阶段可复核的代表原片，历史 4K 全量清单另见本包总目录。","how_to_verify":"source_path 与 archive_path 两端做 SHA-256，并检查像素尺寸。archive_path 相对整套归档根目录。","sequence_note":"文件编号是发布和阅读的讲解顺序。无从零建模实时录像，V1 清空场景起模由代码和初版保存文件佐证。终版素模在 V7 Final 检查时从已完工模型输出。","photos":images,"evidence_documents":docs,"original_editable_files":models}
    (PROV/"process-history.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Verified {len(images)} original images, {len(docs)} evidence documents, {len(models)} original editable files.")
if __name__=="__main__":
    main()
