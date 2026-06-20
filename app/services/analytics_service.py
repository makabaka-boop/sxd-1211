from datetime import datetime, timedelta
from typing import List, Dict
from collections import defaultdict

from app.database import (
    cloth_records_table, qc_records_table, rewash_records_table,
    cloth_categories_table, washing_lines_table, work_teams_table
)
from app.schemas import ClothStatus, DamageLevel, DeliverySuggestion
from app.config import settings
from app.services.laundry_service import list_cloth_records


def now() -> datetime:
    return datetime.now()


def detect_damage_rate_abnormal() -> List[dict]:
    """检测破损率异常的布草类别"""
    all_records = list_cloth_records()
    category_stats = defaultdict(lambda: {"total": 0, "damaged": 0, "category_name": ""})

    categories = {c.doc_id: c["name"] for c in cloth_categories_table.all()}

    for record in all_records:
        cat_id = record["category_id"]
        category_stats[cat_id]["total"] += record["quantity"]
        category_stats[cat_id]["category_name"] = categories.get(cat_id, "未知")

        if record.get("damage_description"):
            category_stats[cat_id]["damaged"] += record["quantity"]

        qc_list = qc_records_table.search(lambda q: q["cloth_record_id"] == record["id"])
        for qc in qc_list:
            if qc["damage_recheck"] in [DamageLevel.MINOR, DamageLevel.MODERATE, DamageLevel.SEVERE]:
                category_stats[cat_id]["damaged"] += record["quantity"]
                break

    abnormal_categories = []
    for cat_id, stats in category_stats.items():
        if stats["total"] > 0:
            damage_rate = stats["damaged"] / stats["total"]
            if damage_rate >= settings.DAMAGE_RATE_THRESHOLD:
                abnormal_categories.append({
                    "category_id": cat_id,
                    "category_name": stats["category_name"],
                    "total_quantity": stats["total"],
                    "damaged_quantity": stats["damaged"],
                    "damage_rate": round(damage_rate * 100, 2),
                    "threshold": settings.DAMAGE_RATE_THRESHOLD * 100
                })

    abnormal_categories.sort(key=lambda x: x["damage_rate"], reverse=True)
    return abnormal_categories


def detect_rewash_backlog() -> List[dict]:
    """检测补洗积压"""
    rewashing_records = list_cloth_records({"status": ClothStatus.REWASHING.value})
    backlog = []

    if len(rewashing_records) >= settings.REWASH_BACKLOG_THRESHOLD:
        for record in rewashing_records:
            rewash_count = len(rewash_records_table.search(
                lambda r: r["cloth_record_id"] == record["id"]
            ))
            backlog.append({
                "record_id": record["id"],
                "batch_no": record["batch_no"],
                "customer_id": record["customer_id"],
                "quantity": record["quantity"],
                "rewash_count": rewash_count
            })

    return backlog


def detect_qc_timeout() -> List[dict]:
    """检测质检超期"""
    timeout_hours = settings.QC_TIMEOUT_HOURS
    timeout_threshold = now() - timedelta(hours=timeout_hours)

    pending_qc = list_cloth_records({"status": ClothStatus.WASHING.value})
    pending_qc += list_cloth_records({"status": ClothStatus.REWASHING.value})

    timeout_records = []
    for record in pending_qc:
        sorted_at = record.get("sorted_at") or record.get("created_at")
        if sorted_at:
            try:
                sorted_time = datetime.fromisoformat(sorted_at)
                if sorted_time < timeout_threshold:
                    hours_passed = (now() - sorted_time).total_seconds() / 3600
                    timeout_records.append({
                        "record_id": record["id"],
                        "batch_no": record["batch_no"],
                        "status": record["status"],
                        "sorted_at": sorted_at,
                        "hours_passed": round(hours_passed, 1),
                        "timeout_hours": timeout_hours
                    })
            except (ValueError, TypeError):
                pass

    timeout_records.sort(key=lambda x: x["hours_passed"], reverse=True)
    return timeout_records


def detect_washing_line_problems() -> List[dict]:
    """检测清洗线问题集中"""
    all_records = list_cloth_records()
    line_stats = defaultdict(lambda: {
        "total": 0,
        "rewash_count": 0,
        "qc_fail_count": 0,
        "line_name": ""
    })

    lines = {l.doc_id: l["name"] for l in washing_lines_table.all()}

    for record in all_records:
        line_id = record.get("washing_line_id")
        if not line_id:
            continue
        line_stats[line_id]["total"] += 1
        line_stats[line_id]["line_name"] = lines.get(line_id, "未知")

        rewash_count = len(rewash_records_table.search(
            lambda r: r["cloth_record_id"] == record["id"]
        ))
        if rewash_count > 0:
            line_stats[line_id]["rewash_count"] += 1

        qc_list = qc_records_table.search(lambda q: q["cloth_record_id"] == record["id"])
        for qc in qc_list:
            if qc["delivery_suggestion"] in [DeliverySuggestion.REWASH, DeliverySuggestion.HOLD]:
                line_stats[line_id]["qc_fail_count"] += 1
                break

    problematic_lines = []
    for line_id, stats in line_stats.items():
        if stats["total"] > 0:
            problem_rate = (stats["rewash_count"] + stats["qc_fail_count"]) / stats["total"]
            if problem_rate >= 0.1:
                problematic_lines.append({
                    "line_id": line_id,
                    "line_name": stats["line_name"],
                    "total_batches": stats["total"],
                    "rewash_count": stats["rewash_count"],
                    "qc_fail_count": stats["qc_fail_count"],
                    "problem_rate": round(problem_rate * 100, 2)
                })

    problematic_lines.sort(key=lambda x: x["problem_rate"], reverse=True)
    return problematic_lines


def detect_missing_delivery_conclusion() -> List[dict]:
    """检测出厂结论缺失"""
    ready_records = list_cloth_records({"status": ClothStatus.READY_FOR_DELIVERY.value})
    missing = []

    for record in ready_records:
        qc_list = qc_records_table.search(lambda q: q["cloth_record_id"] == record["id"])
        has_delivery = any(
            qc["delivery_suggestion"] == DeliverySuggestion.APPROVE
            for qc in qc_list
        )
        if not has_delivery:
            missing.append({
                "record_id": record["id"],
                "batch_no": record["batch_no"],
                "customer_id": record["customer_id"],
                "quantity": record["quantity"],
                "status": record["status"]
            })

    return missing


def get_damage_high_risk_categories() -> List[dict]:
    """统计破损高发类别"""
    all_records = list_cloth_records()
    category_stats = defaultdict(lambda: {"total": 0, "damaged": 0, "category_name": ""})

    categories = {c.doc_id: c["name"] for c in cloth_categories_table.all()}

    for record in all_records:
        cat_id = record["category_id"]
        category_stats[cat_id]["total"] += record["quantity"]
        category_stats[cat_id]["category_name"] = categories.get(cat_id, "未知")

        if record.get("damage_description"):
            category_stats[cat_id]["damaged"] += 1

        qc_list = qc_records_table.search(lambda q: q["cloth_record_id"] == record["id"])
        for qc in qc_list:
            if qc["damage_recheck"] != DamageLevel.NONE:
                category_stats[cat_id]["damaged"] += 1
                break

    result = []
    for cat_id, stats in category_stats.items():
        if stats["total"] > 0:
            damage_rate = stats["damaged"] / stats["total"] * 100
            result.append({
                "category_id": cat_id,
                "category_name": stats["category_name"],
                "total_quantity": stats["total"],
                "damaged_count": stats["damaged"],
                "damage_rate": round(damage_rate, 2)
            })

    result.sort(key=lambda x: x["damage_rate"], reverse=True)
    return result


def get_rewash_todo_list() -> List[dict]:
    """补洗待办统计"""
    rewashing_records = list_cloth_records({"status": ClothStatus.REWASHING.value})

    todo_list = []
    for record in rewashing_records:
        rewash_list = rewash_records_table.search(
            lambda r: r["cloth_record_id"] == record["id"]
        )
        latest_rewash = rewash_list[-1] if rewash_list else None
        todo_list.append({
            "record_id": record["id"],
            "batch_no": record["batch_no"],
            "customer_id": record["customer_id"],
            "category_id": record["category_id"],
            "quantity": record["quantity"],
            "rewash_count": len(rewash_list),
            "latest_rewash_at": latest_rewash["created_at"] if latest_rewash else None,
            "reason": latest_rewash["reason"] if latest_rewash else ""
        })

    todo_list.sort(key=lambda x: x["rewash_count"], reverse=True)
    return todo_list


def get_washing_line_pass_rates() -> List[dict]:
    """清洗线合格率统计"""
    all_records = list_cloth_records()
    line_stats = defaultdict(lambda: {
        "total_batches": 0,
        "passed_batches": 0,
        "line_name": ""
    })

    lines = {l.doc_id: l["name"] for l in washing_lines_table.all()}

    for record in all_records:
        line_id = record.get("washing_line_id")
        if not line_id:
            continue

        line_stats[line_id]["total_batches"] += 1
        line_stats[line_id]["line_name"] = lines.get(line_id, "未知")

        if record["status"] in [ClothStatus.READY_FOR_DELIVERY.value, "已出厂"]:
            qc_list = qc_records_table.search(lambda q: q["cloth_record_id"] == record["id"])
            if any(qc["delivery_suggestion"] == DeliverySuggestion.APPROVE for qc in qc_list):
                line_stats[line_id]["passed_batches"] += 1

    result = []
    for line_id, stats in line_stats.items():
        if stats["total_batches"] > 0:
            pass_rate = stats["passed_batches"] / stats["total_batches"] * 100
            result.append({
                "line_id": line_id,
                "line_name": stats["line_name"],
                "total_batches": stats["total_batches"],
                "passed_batches": stats["passed_batches"],
                "pass_rate": round(pass_rate, 2)
            })

    result.sort(key=lambda x: x["pass_rate"], reverse=True)
    return result


def get_all_anomalies() -> dict:
    """获取所有异常检测结果"""
    return {
        "damage_rate_abnormal": detect_damage_rate_abnormal(),
        "rewash_backlog": detect_rewash_backlog(),
        "qc_timeout": detect_qc_timeout(),
        "washing_line_problems": detect_washing_line_problems(),
        "missing_delivery_conclusion": detect_missing_delivery_conclusion()
    }


def get_statistics_summary() -> dict:
    """获取统计摘要"""
    all_records = list_cloth_records()

    status_counts = defaultdict(int)
    for record in all_records:
        status_counts[record["status"]] += 1

    total_quantity = sum(r["quantity"] for r in all_records)

    return {
        "total_records": len(all_records),
        "total_quantity": total_quantity,
        "status_counts": dict(status_counts),
        "damage_high_risk_categories": get_damage_high_risk_categories(),
        "rewash_todo_list": get_rewash_todo_list(),
        "washing_line_pass_rates": get_washing_line_pass_rates()
    }
