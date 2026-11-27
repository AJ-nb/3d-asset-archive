"""Summarize product delivery records and reopen shots affected by model revisions."""

import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit


def new_delivery(next_step):
    return {
        "stage": "production" if next_step == "production" else "intake",
        "owner": "", "blocker": "", "revisions": [], "shot_reviews": {}, "approval": None,
    }


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def label(value):
    return isinstance(value, str) and bool(value.strip())


def evidence_ref(value, folder):
    if not label(value):
        raise ValueError("验收记录需要证据文件的相对路径或 https 链接")
    if value.startswith("https://") and urlsplit(value).netloc:
        return value
    path = Path(value.partition("#")[0])
    if not path.is_absolute() and (folder / path).is_file():
        return value
    raise ValueError(f"验收证据文件缺失或路径不可移植：{value}")


def summarize(data, folder):
    if not isinstance(data, dict) or set(data) != set(new_delivery("production")):
        raise ValueError("delivery.json 需要 stage, owner, blocker, revisions, shot_reviews, approval")
    stage = data["stage"]
    if stage not in ("intake", "design", "production", "review"):
        raise ValueError("stage 请选择 intake、design、production 或 review")
    owner, blocker = data["owner"], data["blocker"]
    if not isinstance(owner, str) or not isinstance(blocker, str):
        raise ValueError("owner 和 blocker 需要文本")
    revisions, reviews = data["revisions"], data["shot_reviews"]
    if not isinstance(revisions, list) or not isinstance(reviews, dict):
        raise ValueError("revisions 需要按顺序列版本，shot_reviews 需要按镜头编号登记")
    versions, required = [], {}
    for revision in revisions:
        if not isinstance(revision, dict) or set(revision) != {"version", "affected_shots"}:
            raise ValueError("每次修订需要 version 与 affected_shots")
        version, shots = revision["version"], revision["affected_shots"]
        if not label(version) or version in versions:
            raise ValueError("修订版本须非空且唯一")
        if not isinstance(shots, list) or not all(label(shot) for shot in shots) or len(set(shots)) != len(shots):
            raise ValueError(f"{version} 的 affected_shots 需要不重复的镜头 ID")
        versions.append(version)
        for shot in shots:
            required[shot] = version

    open_shots = dict(required)
    evidence = []
    for shot, review in reviews.items():
        if shot not in required or not isinstance(review, dict) or set(review) != {"version", "evidence"}:
            raise ValueError(f"未登记的镜头或无效复核记录：{shot}")
        if review["version"] not in versions:
            raise ValueError(f"{shot} 使用了未知版本")
        proof = evidence_ref(review["evidence"], folder)
        if versions.index(review["version"]) >= versions.index(required[shot]):
            del open_shots[shot]
            evidence.append(proof)

    current = versions[-1] if versions else None
    approval = data["approval"]
    decision = "待签收"
    if approval is not None:
        if (not isinstance(approval, dict) or set(approval) != {"version", "by", "evidence"}
                or approval["version"] not in versions or not label(approval["by"])):
            raise ValueError("签收需要已登记的版本、批准人和证据")
        evidence.append(evidence_ref(approval["evidence"], folder))
        if approval["version"] != current:
            decision = "新版待签"
        elif blocker.strip() or open_shots:
            decision = "签收待复核"
        else:
            decision = "已签收"
    return {"stage": stage, "model_version": current, "owner": owner, "blocker": blocker,
            "open_shots": open_shots, "decision": decision, "approval": approval,
            "evidence": list(dict.fromkeys(evidence))}


def read_orders(root, only, init_missing):
    rows = load(root / "queue-report.json")["products"]
    if not isinstance(rows, list):
        raise ValueError("无效的工单报告")
    results = []
    for row in rows:
        key = row["id"]
        if only and key != only:
            continue
        entry = {"id": key}
        try:
            if row["status"] != "ready":
                entry.update(stage="工单失败", reason=row.get("reason"))
            else:
                folder = (root / key).resolve()
                if folder.parent != root or not folder.is_dir():
                    raise ValueError("产品目录缺失或位于工单目录以外")
                record = folder / "delivery.json"
                if init_missing and not record.exists():
                    with record.open("x", encoding="utf-8") as handle:
                        json.dump(new_delivery(row.get("next_step")), handle, ensure_ascii=False, indent=2)
                        handle.write("\n")
                if record.is_file():
                    entry.update(summarize(load(record), folder))
                else:
                    entry["stage"] = "未登记"
        except (OSError, ValueError, TypeError, KeyError) as error:
            entry.update(stage="记录有误", reason=str(error))
        results.append(entry)
    if only and not results:
        raise ValueError(f"工单中找不到产品：{only}")
    return results


def print_table(rows):
    print("| 产品 | 制作阶段 | 模型版本 | 阻塞 / 负责人 | 待重出或复核的镜头 | 签收 | 证据 |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for row in rows:
        approval = row.get("approval") or {}
        decision = " ".join(filter(None, [row.get("decision"), approval.get("version"), approval.get("by")]))
        pending = ", ".join(f"{shot}@{version}" for shot, version in row.get("open_shots", {}).items())
        cells = [row["id"], row["stage"], row.get("model_version"),
                 " / ".join(filter(None, [row.get("blocker") or row.get("reason"), row.get("owner")])),
                 pending, decision, ", ".join(row.get("evidence", []))]
        print("| " + " | ".join(str(cell or "—").replace("|", "\\|").replace("\n", " ") for cell in cells) + " |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path, help="directory containing queue-report.json")
    parser.add_argument("--only", metavar="PRODUCT_ID")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--init-missing", action="store_true", help="add delivery.json to older prepared orders")
    args = parser.parse_args()
    try:
        rows = read_orders(args.queue.resolve(), args.only, args.init_missing)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            print_table(rows)
        return int(any(row["stage"] in ("记录有误", "工单失败") for row in rows))
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
