"""Prepare independent product briefs from a JSON queue. Uses only the standard library."""

import argparse
from collections import Counter
import json
from pathlib import Path, PureWindowsPath
import re
import sys


RESERVED = re.compile(r"(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", re.I)
FIELDS = {"id", "mode", "brief", "references", "source", "deliverables", "resolution", "acceptance", "review"}


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


def make_brief(product, base):
    extra = set(product) - FIELDS
    if extra:
        raise ValueError(f"未知字段：{sorted(extra)}")
    key, mode = product["id"], product.get("mode")
    if mode not in ("create", "revise") or not nonempty_text(product.get("brief")):
        raise ValueError("需要 mode=create/revise 并填写 brief")
    refs = product.get("references", [])
    if not isinstance(refs, list):
        raise ValueError("references 需要文件路径数组")
    inputs = ["- 参考资料：" + checked_input(item, base) for item in refs]
    if mode == "revise":
        inputs.insert(0, "- 接手工程：" + checked_input(product.get("source"), base))
    elif "source" in product:
        raise ValueError("接手现有源工程时请设置 mode=revise；只用于参照的文件列入 references")
    resolution = product.get("resolution")
    if not isinstance(resolution, list) or len(resolution) != 2 or not all(
        type(v) is int and v > 0 for v in resolution
    ):
        raise ValueError("resolution 需要 [宽, 高] 两个正整数像素值")
    route = "从零建模" if mode == "create" else "接手现有工程，在副本上修复"
    review = text_list(product, "review") if "review" in product else ""
    return "\n".join([
        f"# {key} 制作工单", "", f"{route}。目标画幅 {resolution[0]} × {resolution[1]} px。",
        "", "## 产品简报", "", product["brief"].strip(),
        "", "## 输入", "", *(inputs or ["- 依据本工单的文字概念进行原创设计。"]),
        *([f"- 输入文件基准目录：{base}"] if inputs else []),
        "", "## 交付物", "", text_list(product, "deliverables"),
        "", "## 模型复核与重渲", "",
        "1. 标明尺寸来源、单位和装配基准。按部件登记接合对象、支承和各组倒角，量取壁厚与缝隙。",
        "2. 在有尺度的基准上沿三轴每 1 mm 取截面，给偏差标注部件和站位。缺少对照的特征列为待证。",
        "3. 修回源模型，复跑同截面与保留视角。运动件实绑，检查默认、常用、极限和连续组合动作。",
        "4. 冻结已复验版本，重渲受影响镜头，检查整套联系表、原寸细节和实际版位。交付证据与剩余未知项。",
        *(["", "本款专项核对项", "", review] if review else []),
        "", "## 验收", "", text_list(product, "acceptance"), "",
    ])


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
            brief = make_brief(product, manifest.parent)
            folder = out / key
            folder.mkdir()
            with (folder / "brief.md").open("x", encoding="utf-8") as handle:
                handle.write(brief)
            row.update(status="ready", brief=f"{key}/brief.md")
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
