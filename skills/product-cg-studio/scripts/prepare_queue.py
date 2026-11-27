"""Prepare independent product briefs from a JSON queue. Uses only the standard library."""

import argparse
from collections import Counter
import json
from pathlib import Path, PureWindowsPath
import re
import sys
from tempfile import TemporaryDirectory


RESERVED = re.compile(r"(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", re.I)
FIELDS = {"id", "mode", "brief", "references", "source", "deliverables", "resolution",
          "acceptance", "review", "question_overrides"}
GEOMETRY_FORMATS = {".blend", ".step", ".stp", ".iges", ".igs", ".3dm", ".brep", ".x_t",
                    ".obj", ".fbx", ".stl", ".glb", ".gltf", ".usd", ".usda", ".usdc", ".usdz"}
INTERVIEW_GUIDE = Path(__file__).resolve().parents[1] / "references" / "concept-intake.md"


def nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def checked_input(relative, base):
    if not nonempty_text(relative) or PureWindowsPath(relative).anchor:
        raise ValueError(f"输入文件需要相对路径：{relative!r}")
    parts = relative.split("/")
    if any(part in ("", ".", "..") or RESERVED.fullmatch(part) or part.endswith((" ", "."))
           or re.search(r'[\\<>:"|?*\x00-\x1f]', part) for part in parts):
        raise ValueError(f"输入路径不符合可移植文件名格式：{relative!r}")
    actual = base.joinpath(*parts).resolve()
    if base not in actual.parents or not actual.is_file():
        raise ValueError(f"找不到清单目录以内的输入文件：{relative}")
    return relative


def text_list(product, key):
    values = product.get(key)
    if not isinstance(values, list) or not values or not all(nonempty_text(v) for v in values):
        raise ValueError(f"{key} 需要至少一条非空文本")
    return "\n".join(f"- {value.strip()}" for value in values)


def interview_questions(overrides):
    guide = INTERVIEW_GUIDE.read_text(encoding="utf-8-sig")
    block = re.search(r"<!-- client-questions:start -->(.*?)<!-- client-questions:end -->", guide, re.S)
    if not block:
        raise ValueError("技能缺少概念访谈题库，请复制完整技能目录")
    rows = re.findall(r"^(\d+)\. (\S[^\n]*)$", block[1], re.M)
    if len(rows) < 10 or [int(n) for n, _ in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("概念访谈题库需包含至少 10 条连续编号的问题")
    questions = dict(rows)
    if not isinstance(overrides, dict) or any(
        key not in questions or not nonempty_text(value) or len(value.strip().splitlines()) != 1
        for key, value in overrides.items()
    ):
        raise ValueError("question_overrides 的键应为已有题号，值应为单行非空问题")
    questions.update(overrides)
    texts = [text.strip() for text in questions.values()]
    if len({re.sub(r"[\s？?。]+", "", q).casefold() for q in texts}) != len(texts):
        raise ValueError("概念访谈中的问题重复，请将它们分别用于不同的设计决定")
    return texts


def concept_materials(product):
    questions = interview_questions(product.get("question_overrides", {}))
    interview = [
        f"# {product['id']} · 概念访谈", "", "目前收到的构想", "", product["brief"].strip(), "",
        "欢迎按题号回答。有图时也可以直接画箭头、圈部位。未定的地方可填“请提方案”。", "",
    ]
    for idx, question in enumerate(questions, 1):
        interview.extend([f"{idx}. {question}", "", "   答：", ""])
    record = [
        f"# {product['id']} · 设计决定", "", "## 草图与回答", "",
        "按题号记录客户原话。有草图时补上图号、视角和相关轮廓。对不一致的地方列出可区分两种解释的下一次观察。", "",
        "| 来源（原话、题号或草图） | 客户确认或委托的决定 | 仍待判断／暂用的假设 | 影响的部件、动作或镜头 |",
        "| --- | --- | --- | --- |", "", "## 相似案例与取舍", "",
        "在当前资料上先搜索并核对真实案例。每条记录一个具体可借鉴或应避开的设计决定，给客户可比较的方向。", "",
        "| 案例编号、名称与原始链接 | 已观察到的特征 | 对本案的建模／渲染用途 | 客户选择、排除或暂缓及理由 |",
        "| --- | --- | --- | --- |", "", "## 回填建模简报", "",
        "把客户已选或授权代定的方案写回同目录 brief.md，并注明依据。待确认处保留假设，记录低成本白模能回答什么。", "",
        "| 项目 | 已定内容与依据 | 下一次检查 |", "| --- | --- | --- |",
        "| 用途、尺寸与观察角度 | | |", "| 主要部件、支撑、连接或解剖关系 | | |",
        "| 材料与表面处理、动作或姿态 | | |", "| 交付物、镜头与验收条件 | | |", "",
    ]
    return {"client-interview.md": "\n".join(interview), "design-decisions.md": "\n".join(record)}


def make_brief(product, base):
    extra = set(product) - FIELDS
    if extra:
        raise ValueError(f"未知字段：{sorted(extra)}")
    key, mode = product["id"], product.get("mode")
    if mode not in ("concept", "create", "revise") or not nonempty_text(product.get("brief")):
        raise ValueError("需要 mode=concept/create/revise 并填写 brief")
    refs = product.get("references", [])
    if not isinstance(refs, list):
        raise ValueError("references 需要文件路径数组")
    inputs = ["- 参考资料：" + checked_input(item, base) for item in refs]
    if mode == "revise":
        inputs.insert(0, "- 接手工程：" + checked_input(product.get("source"), base))
        if "question_overrides" in product:
            raise ValueError("question_overrides 用于 concept 或 create 的概念访谈")
    elif "source" in product:
        raise ValueError("接手现有源工程时请设置 mode=revise；只用于参照的文件列入 references")
    resolution = product.get("resolution")
    if mode == "concept" and "resolution" not in product:
        frame = "目标画幅待客户说明用途后确定。"
    else:
        if not isinstance(resolution, list) or len(resolution) != 2 or not all(
            type(v) is int and v > 0 for v in resolution
        ):
            raise ValueError("resolution 需要 [宽, 高] 两个正整数像素值")
        frame = f"目标画幅 {resolution[0]} × {resolution[1]} px。"
    route = {"concept": "从概念或草图开始", "create": "从零建模",
             "revise": "接手现有工程，在副本上修复"}[mode]
    pending = "- 待访谈后写入。"
    outputs = pending if mode == "concept" and "deliverables" not in product else text_list(product, "deliverables")
    acceptance = pending if mode == "concept" and "acceptance" not in product else text_list(product, "acceptance")
    # File extensions can identify geometry, but cannot distinguish a photo from a sketch.
    has_geometry = any(Path(path).suffix.lower() in GEOMETRY_FORMATS for path in refs)
    use_intake = mode == "concept" or (mode == "create" and ("question_overrides" in product or not has_geometry))
    files = concept_materials(product) if use_intake else {}
    next_step = "production"
    intake = []
    if use_intake:
        next_step = "concept_intake" if mode == "concept" else "inspect_inputs"
        route_note = ("按概念流程执行。" if mode == "concept" else
                      "先读实物资料、草图或文字。若仍在构思，执行下述访谈；规格已定时按既有依据制作。")
        intake = [
            "", "## 概念访谈与找样", "", route_note,
            "先整理客户原话和待定项，有图时逐张读图。把[客户访谈稿](client-interview.md)改成针对这款对象的至少 10 个有效问题，实际向客户提问。对已知信息改问仍会影响结果的决定。",
            "根据现有线索主动查找相似案例，核对原始来源，向客户展示结构、造型、材质或镜头各自可借鉴之处及可选方向。",
            "将客户原话、参考编号、取舍和待证假设记入[设计决定](design-decisions.md)。依据确认或授权的范围更新下方简报、交付与验收，继续白模与结构验证。",
        ]
    review = text_list(product, "review") if "review" in product else ""
    files["brief.md"] = "\n".join([
        f"# {key} 制作工单", "", f"{route}。{frame}",
        "", "## 产品简报", "", product["brief"].strip(),
        "", "## 输入", "", *(inputs or ["- 依据本工单的文字概念进行原创设计。"]),
        *([f"- 输入文件基准目录：{base}"] if inputs else []),
        *intake, "", "## 交付物", "", outputs,
        "", "## 模型复核与重渲", "",
        "1. 标明尺寸来源、单位和基准。核对硬件的支承、接头、倒角、壁厚与缝隙。对布偶等柔性对象，核对缝合或解剖连接、受压轮廓、填充体积或软组织形态。",
        "2. 有真实尺度时沿三轴每 1 mm 取截面，记录部件和站位。与有尺度的参考对齐后量差。只有构想时，先检查轮廓与内部连续性，记下待核尺寸。",
        "3. 修回源模型，复跑同截面与保留视角。如需运动或可绑定交付，实绑检查默认、常用、极限和连续组合动作。静态对象复验支撑和接触。",
        "4. 冻结已复验版本，重渲受影响镜头，检查整套联系表、原寸细节和实际版位。交付证据与剩余未知项。",
        *(["", "本款专项核对项", "", review] if review else []),
        "", "## 验收", "", acceptance, "",
    ])
    return files, next_step


def prepare(manifest, out):
    manifest = manifest.resolve(strict=True)
    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or set(data) != {"version", "products"} or type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("清单需要 version: 1 和 products")
    products = data["products"]
    if not isinstance(products, list) or not products:
        raise ValueError("products 需要至少一个产品")
    ids = [p.get("id") if isinstance(p, dict) else None for p in products]
    counts = Counter(key for key in ids if isinstance(key, str))
    out.mkdir(parents=True, exist_ok=False)
    report = []
    for position, (product, key) in enumerate(zip(products, ids), start=1):
        row = {"row": position, "id": key}
        try:
            if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", key) or RESERVED.fullmatch(key):
                raise ValueError("id 需要 1–64 位小写字母、数字、短横线或下划线，首位为字母或数字，避开系统保留名")
            if counts[key] > 1:
                raise ValueError(f"重复的产品 id：{key}")
            files, next_step = make_brief(product, manifest.parent)
            with TemporaryDirectory(dir=out) as temp:
                folder = Path(temp) / key
                folder.mkdir()
                for filename, content in files.items():
                    (folder / filename).write_text(content, encoding="utf-8")
                folder.rename(out / key)
            row.update(status="ready", brief=f"{key}/brief.md", next_step=next_step)
        except (OSError, ValueError, RuntimeError) as error:
            row.update(status="failed", reason=str(error))
        report.append(row)
    with (out / "queue-report.json").open("x", encoding="utf-8") as handle:
        json.dump({"products": report}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    ready = sum(p["status"] == "ready" for p in report)
    print(f"{ready}/{len(report)} ready | {out / 'queue-report.json'}")
    return 0 if ready == len(report) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", required=True, type=Path, help="New output directory")
    args = parser.parse_args()
    try:
        return prepare(args.manifest, args.out)
    except (OSError, ValueError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
