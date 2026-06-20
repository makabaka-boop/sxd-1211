from datetime import datetime, timedelta
from typing import List, Dict
from collections import defaultdict

from app.database import (
    cloth_records_table, qc_records_table, rewash_records_table,
    cloth_categories_table, washing_lines_table, work_teams_table,
    customers_table, rewash_tasks_table, rewash_recheck_records_table,
    delivery_records_table
)
from app.schemas import ClothStatus, DamageLevel, DeliverySuggestion, RewashTaskStatus, RewashFinalConclusion
from app.config import settings
from app.services.laundry_service import list_cloth_records, list_rewash_tasks


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

        is_damaged = False
        if record.get("damage_description"):
            is_damaged = True

        if not is_damaged:
            qc_list = qc_records_table.search(lambda q: q["cloth_record_id"] == record["id"])
            for qc in qc_list:
                if qc["damage_recheck"] in [DamageLevel.MINOR, DamageLevel.MODERATE, DamageLevel.SEVERE]:
                    is_damaged = True
                    break

        if is_damaged:
            category_stats[cat_id]["damaged"] += record["quantity"]

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

    pending_qc = list_cloth_records({"status": ClothStatus.PENDING_QC.value})

    timeout_records = []
    for record in pending_qc:
        reference_time = record.get("washing_completed_at") or record.get("sorted_at") or record.get("created_at")
        if reference_time:
            try:
                ref_datetime = datetime.fromisoformat(reference_time)
                if ref_datetime < timeout_threshold:
                    hours_passed = (now() - ref_datetime).total_seconds() / 3600
                    timeout_records.append({
                        "record_id": record["id"],
                        "batch_no": record["batch_no"],
                        "status": record["status"],
                        "washing_completed_at": reference_time,
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

        is_damaged = False
        if record.get("damage_description"):
            is_damaged = True

        if not is_damaged:
            qc_list = qc_records_table.search(lambda q: q["cloth_record_id"] == record["id"])
            for qc in qc_list:
                if qc["damage_recheck"] != DamageLevel.NONE:
                    is_damaged = True
                    break

        if is_damaged:
            category_stats[cat_id]["damaged"] += 1

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

        if record["status"] in [ClothStatus.READY_FOR_DELIVERY.value, ClothStatus.DELIVERED.value]:
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

    pending_handover_count = 0
    pending_handover_quantity = 0
    completed_handover_count = 0
    completed_handover_quantity = 0
    for record in all_records:
        if record["status"] == ClothStatus.READY_FOR_DELIVERY.value:
            pending_handover_count += 1
            pending_handover_quantity += record["quantity"]
        elif record["status"] == ClothStatus.DELIVERED.value:
            completed_handover_count += 1
            completed_handover_quantity += record["quantity"]

    delivery_total = pending_handover_count + completed_handover_count
    handover_completion_rate = round(
        completed_handover_count / delivery_total * 100, 2
    ) if delivery_total > 0 else 0

    return {
        "total_records": len(all_records),
        "total_quantity": total_quantity,
        "status_counts": dict(status_counts),
        "delivery": {
            "pending_handover_count": pending_handover_count,
            "pending_handover_quantity": pending_handover_quantity,
            "completed_handover_count": completed_handover_count,
            "completed_handover_quantity": completed_handover_quantity,
            "handover_completion_rate": handover_completion_rate
        },
        "damage_high_risk_categories": get_damage_high_risk_categories(),
        "rewash_todo_list": get_rewash_todo_list(),
        "washing_line_pass_rates": get_washing_line_pass_rates()
    }


def get_rewash_stats_by_customer() -> List[dict]:
    """按客户维度统计补洗情况"""
    all_tasks = list_rewash_tasks()
    customers = {c.doc_id: c["name"] for c in customers_table.all()}
    records_map = {r.doc_id: dict(r) for r in cloth_records_table.all()}

    customer_stats = defaultdict(lambda: {
        "customer_id": 0,
        "customer_name": "",
        "total_rewash_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "in_progress_count": 0,
        "completed_pending_recheck_count": 0,
        "total_quantity": 0
    })

    for task in all_tasks:
        record = records_map.get(task["cloth_record_id"])
        if not record:
            continue
        customer_id = record["customer_id"]
        customer_stats[customer_id]["customer_id"] = customer_id
        customer_stats[customer_id]["customer_name"] = customers.get(customer_id, "未知")
        customer_stats[customer_id]["total_rewash_count"] += 1
        customer_stats[customer_id]["total_quantity"] += record["quantity"]

        if task["status"] == RewashTaskStatus.PASSED:
            customer_stats[customer_id]["passed_count"] += 1
        elif task["status"] == RewashTaskStatus.FAILED:
            customer_stats[customer_id]["failed_count"] += 1
        elif task["status"] == RewashTaskStatus.PENDING:
            customer_stats[customer_id]["pending_count"] += 1
        elif task["status"] == RewashTaskStatus.IN_PROGRESS:
            customer_stats[customer_id]["in_progress_count"] += 1
        elif task["status"] == RewashTaskStatus.COMPLETED:
            customer_stats[customer_id]["completed_pending_recheck_count"] += 1

    result = []
    for customer_id, stats in customer_stats.items():
        total_completed = stats["passed_count"] + stats["failed_count"]
        pass_rate = round(stats["passed_count"] / total_completed * 100, 2) if total_completed > 0 else 0
        stats["pass_rate"] = pass_rate
        stats["unfinished_count"] = stats["pending_count"] + stats["in_progress_count"] + stats["completed_pending_recheck_count"]
        result.append(stats)

    result.sort(key=lambda x: x["total_rewash_count"], reverse=True)
    return result


def get_rewash_stats_by_category() -> List[dict]:
    """按布草类别维度统计补洗情况"""
    all_tasks = list_rewash_tasks()
    categories = {c.doc_id: c["name"] for c in cloth_categories_table.all()}
    records_map = {r.doc_id: dict(r) for r in cloth_records_table.all()}

    category_stats = defaultdict(lambda: {
        "category_id": 0,
        "category_name": "",
        "total_rewash_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "in_progress_count": 0,
        "completed_pending_recheck_count": 0,
        "total_quantity": 0
    })

    for task in all_tasks:
        record = records_map.get(task["cloth_record_id"])
        if not record:
            continue
        category_id = record["category_id"]
        category_stats[category_id]["category_id"] = category_id
        category_stats[category_id]["category_name"] = categories.get(category_id, "未知")
        category_stats[category_id]["total_rewash_count"] += 1
        category_stats[category_id]["total_quantity"] += record["quantity"]

        if task["status"] == RewashTaskStatus.PASSED:
            category_stats[category_id]["passed_count"] += 1
        elif task["status"] == RewashTaskStatus.FAILED:
            category_stats[category_id]["failed_count"] += 1
        elif task["status"] == RewashTaskStatus.PENDING:
            category_stats[category_id]["pending_count"] += 1
        elif task["status"] == RewashTaskStatus.IN_PROGRESS:
            category_stats[category_id]["in_progress_count"] += 1
        elif task["status"] == RewashTaskStatus.COMPLETED:
            category_stats[category_id]["completed_pending_recheck_count"] += 1

    result = []
    for category_id, stats in category_stats.items():
        total_completed = stats["passed_count"] + stats["failed_count"]
        pass_rate = round(stats["passed_count"] / total_completed * 100, 2) if total_completed > 0 else 0
        stats["pass_rate"] = pass_rate
        stats["unfinished_count"] = stats["pending_count"] + stats["in_progress_count"] + stats["completed_pending_recheck_count"]
        result.append(stats)

    result.sort(key=lambda x: x["total_rewash_count"], reverse=True)
    return result


def get_rewash_stats_by_washing_line() -> List[dict]:
    """按清洗线维度统计补洗情况"""
    all_tasks = list_rewash_tasks()
    lines = {l.doc_id: l["name"] for l in washing_lines_table.all()}
    records_map = {r.doc_id: dict(r) for r in cloth_records_table.all()}

    line_stats = defaultdict(lambda: {
        "washing_line_id": 0,
        "washing_line_name": "",
        "total_rewash_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "in_progress_count": 0,
        "completed_pending_recheck_count": 0,
        "total_quantity": 0
    })

    for task in all_tasks:
        line_id = task["responsible_washing_line_id"]
        record = records_map.get(task["cloth_record_id"])
        line_stats[line_id]["washing_line_id"] = line_id
        line_stats[line_id]["washing_line_name"] = lines.get(line_id, "未知")
        line_stats[line_id]["total_rewash_count"] += 1
        if record:
            line_stats[line_id]["total_quantity"] += record["quantity"]

        if task["status"] == RewashTaskStatus.PASSED:
            line_stats[line_id]["passed_count"] += 1
        elif task["status"] == RewashTaskStatus.FAILED:
            line_stats[line_id]["failed_count"] += 1
        elif task["status"] == RewashTaskStatus.PENDING:
            line_stats[line_id]["pending_count"] += 1
        elif task["status"] == RewashTaskStatus.IN_PROGRESS:
            line_stats[line_id]["in_progress_count"] += 1
        elif task["status"] == RewashTaskStatus.COMPLETED:
            line_stats[line_id]["completed_pending_recheck_count"] += 1

    result = []
    for line_id, stats in line_stats.items():
        total_completed = stats["passed_count"] + stats["failed_count"]
        pass_rate = round(stats["passed_count"] / total_completed * 100, 2) if total_completed > 0 else 0
        stats["pass_rate"] = pass_rate
        stats["unfinished_count"] = stats["pending_count"] + stats["in_progress_count"] + stats["completed_pending_recheck_count"]
        result.append(stats)

    result.sort(key=lambda x: x["total_rewash_count"], reverse=True)
    return result


def get_rewash_stats_by_work_team() -> List[dict]:
    """按班组维度统计补洗情况"""
    all_tasks = list_rewash_tasks()
    teams = {t.doc_id: t["name"] for t in work_teams_table.all()}
    records_map = {r.doc_id: dict(r) for r in cloth_records_table.all()}

    team_stats = defaultdict(lambda: {
        "work_team_id": 0,
        "work_team_name": "",
        "total_rewash_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "in_progress_count": 0,
        "completed_pending_recheck_count": 0,
        "total_quantity": 0
    })

    for task in all_tasks:
        team_id = task["responsible_work_team_id"]
        record = records_map.get(task["cloth_record_id"])
        team_stats[team_id]["work_team_id"] = team_id
        team_stats[team_id]["work_team_name"] = teams.get(team_id, "未知")
        team_stats[team_id]["total_rewash_count"] += 1
        if record:
            team_stats[team_id]["total_quantity"] += record["quantity"]

        if task["status"] == RewashTaskStatus.PASSED:
            team_stats[team_id]["passed_count"] += 1
        elif task["status"] == RewashTaskStatus.FAILED:
            team_stats[team_id]["failed_count"] += 1
        elif task["status"] == RewashTaskStatus.PENDING:
            team_stats[team_id]["pending_count"] += 1
        elif task["status"] == RewashTaskStatus.IN_PROGRESS:
            team_stats[team_id]["in_progress_count"] += 1
        elif task["status"] == RewashTaskStatus.COMPLETED:
            team_stats[team_id]["completed_pending_recheck_count"] += 1

    result = []
    for team_id, stats in team_stats.items():
        total_completed = stats["passed_count"] + stats["failed_count"]
        pass_rate = round(stats["passed_count"] / total_completed * 100, 2) if total_completed > 0 else 0
        stats["pass_rate"] = pass_rate
        stats["unfinished_count"] = stats["pending_count"] + stats["in_progress_count"] + stats["completed_pending_recheck_count"]
        result.append(stats)

    result.sort(key=lambda x: x["total_rewash_count"], reverse=True)
    return result


def get_abnormal_rewash_ranking(top_n: int = 10) -> List[dict]:
    """异常补洗排行（补洗次数超过阈值的记录）"""
    all_tasks = list_rewash_tasks()
    records_map = {r.doc_id: dict(r) for r in cloth_records_table.all()}
    customers = {c.doc_id: c["name"] for c in customers_table.all()}
    categories = {c.doc_id: c["name"] for c in cloth_categories_table.all()}

    record_rewash_counts = defaultdict(int)
    record_failed_counts = defaultdict(int)
    for task in all_tasks:
        record_rewash_counts[task["cloth_record_id"]] += 1
        if task["status"] == RewashTaskStatus.FAILED:
            record_failed_counts[task["cloth_record_id"]] += 1

    ranking = []
    for record_id, total_count in record_rewash_counts.items():
        if total_count >= 2:
            record = records_map.get(record_id)
            if not record:
                continue
            ranking.append({
                "record_id": record_id,
                "batch_no": record["batch_no"],
                "customer_id": record["customer_id"],
                "customer_name": customers.get(record["customer_id"], "未知"),
                "category_id": record["category_id"],
                "category_name": categories.get(record["category_id"], "未知"),
                "quantity": record["quantity"],
                "total_rewash_count": total_count,
                "failed_count": record_failed_counts[record_id],
                "status": record["status"]
            })

    ranking.sort(key=lambda x: (x["total_rewash_count"], x["failed_count"]), reverse=True)
    return ranking[:top_n]


def get_rewash_overview_stats() -> dict:
    """补洗概览统计"""
    all_tasks = list_rewash_tasks()

    status_counts = defaultdict(int)
    for task in all_tasks:
        status_counts[task["status"]] += 1

    total_tasks = len(all_tasks)
    passed_count = status_counts.get(RewashTaskStatus.PASSED, 0)
    failed_count = status_counts.get(RewashTaskStatus.FAILED, 0)
    total_completed = passed_count + failed_count
    pass_rate = round(passed_count / total_completed * 100, 2) if total_completed > 0 else 0

    pending_count = status_counts.get(RewashTaskStatus.PENDING, 0)
    in_progress_count = status_counts.get(RewashTaskStatus.IN_PROGRESS, 0)
    completed_pending_recheck = status_counts.get(RewashTaskStatus.COMPLETED, 0)
    unfinished_count = pending_count + in_progress_count + completed_pending_recheck

    return {
        "total_rewash_tasks": total_tasks,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pending_count": pending_count,
        "in_progress_count": in_progress_count,
        "completed_pending_recheck_count": completed_pending_recheck,
        "unfinished_count": unfinished_count,
        "pass_rate": pass_rate,
        "status_counts": dict(status_counts)
    }


def get_delivery_overview_stats() -> dict:
    """出厂交接概览统计，区分可出厂待交接与已完成交接"""
    all_records = list_cloth_records()

    pending_handover_count = 0
    pending_handover_quantity = 0
    completed_handover_count = 0
    completed_handover_quantity = 0
    delivered_quantity = 0

    for record in all_records:
        if record["status"] == ClothStatus.READY_FOR_DELIVERY.value:
            pending_handover_count += 1
            pending_handover_quantity += record["quantity"]
        elif record["status"] == ClothStatus.DELIVERED.value:
            completed_handover_count += 1
            completed_handover_quantity += record["quantity"]

    delivered_records = delivery_records_table.all()
    for d in delivered_records:
        delivered_quantity += d["delivery_quantity"]

    delivery_total = pending_handover_count + completed_handover_count
    handover_completion_rate = round(
        completed_handover_count / delivery_total * 100, 2
    ) if delivery_total > 0 else 0

    return {
        "pending_handover_count": pending_handover_count,
        "pending_handover_quantity": pending_handover_quantity,
        "completed_handover_count": completed_handover_count,
        "completed_handover_quantity": completed_handover_quantity,
        "delivered_quantity": delivered_quantity,
        "handover_completion_rate": handover_completion_rate,
        "total_delivery_records": len(delivered_records)
    }


def get_delivery_stats_by_customer() -> List[dict]:
    """按客户维度统计出厂交接情况，区分可出厂待交接与已完成交接"""
    all_records = list_cloth_records()
    customers = {c.doc_id: c["name"] for c in customers_table.all()}
    delivery_records = delivery_records_table.all()
    delivered_quantity_by_record = defaultdict(int)
    for d in delivery_records:
        delivered_quantity_by_record[d["cloth_record_id"]] += d["delivery_quantity"]

    customer_stats = defaultdict(lambda: {
        "customer_id": 0,
        "customer_name": "",
        "ready_count": 0,
        "delivered_count": 0,
        "pending_handover_count": 0,
        "completed_handover_count": 0,
        "pending_handover_quantity": 0,
        "completed_handover_quantity": 0,
        "delivered_quantity": 0,
        "total_quantity": 0
    })

    for record in all_records:
        customer_id = record["customer_id"]
        customer_stats[customer_id]["customer_id"] = customer_id
        customer_stats[customer_id]["customer_name"] = customers.get(customer_id, "未知")
        customer_stats[customer_id]["total_quantity"] += record["quantity"]

        if record["status"] == ClothStatus.READY_FOR_DELIVERY.value:
            customer_stats[customer_id]["ready_count"] += 1
            customer_stats[customer_id]["pending_handover_count"] += 1
            customer_stats[customer_id]["pending_handover_quantity"] += record["quantity"]
        elif record["status"] == ClothStatus.DELIVERED.value:
            customer_stats[customer_id]["delivered_count"] += 1
            customer_stats[customer_id]["completed_handover_count"] += 1
            customer_stats[customer_id]["completed_handover_quantity"] += record["quantity"]
            customer_stats[customer_id]["delivered_quantity"] += delivered_quantity_by_record.get(record["id"], record["quantity"])

    result = []
    for customer_id, stats in customer_stats.items():
        delivery_total = stats["pending_handover_count"] + stats["completed_handover_count"]
        stats["handover_completion_rate"] = round(
            stats["completed_handover_count"] / delivery_total * 100, 2
        ) if delivery_total > 0 else 0
        result.append(stats)

    result.sort(key=lambda x: (x["pending_handover_count"] + x["completed_handover_count"]), reverse=True)
    return result
