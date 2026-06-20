from datetime import datetime
from typing import Optional, List
from litestar.exceptions import ValidationException, NotFoundException

from app.database import (
    cloth_records_table, ClothRecordQuery,
    rewash_records_table, qc_records_table,
    customers_table, cloth_categories_table, washing_lines_table, work_teams_table,
    rewash_tasks_table, rewash_recheck_records_table, RewashTaskQuery, RewashRecheckQuery,
    RewashRecordQuery, users_table
)
from app.schemas import (
    ClothStatus, ClothRecordCreate, SortingRecordCreate, QcRecordCreate,
    RewashRecordCreate, CleanlinessLevel, DeliverySuggestion, DamageLevel,
    RewashTaskStatus, RewashFinalConclusion,
    RewashTaskCreate, RewashTaskComplete, RewashTaskRecheck
)
from app.config import settings


def now_str() -> str:
    return datetime.now().isoformat()


def get_cloth_record_or_404(record_id: int) -> dict:
    record = cloth_records_table.get(doc_id=record_id)
    if not record:
        raise NotFoundException(detail=f"布草记录 {record_id} 不存在")
    record["id"] = record_id
    return record


def validate_batch_unique(customer_id: int, batch_no: str, exclude_id: Optional[int] = None) -> None:
    query = (ClothRecordQuery.customer_id == customer_id) & (ClothRecordQuery.batch_no == batch_no)
    existing = cloth_records_table.search(query)
    if exclude_id:
        existing = [e for e in existing if e.doc_id != exclude_id]
    if existing:
        raise ValidationException(detail=f"同一客户同一批号 {batch_no} 不可重复入厂")


def create_cloth_record(data: ClothRecordCreate, sorter_id: int) -> dict:
    validate_batch_unique(data.customer_id, data.batch_no)

    customer = customers_table.get(doc_id=data.customer_id)
    if not customer:
        raise NotFoundException(detail="客户单位不存在")

    category = cloth_categories_table.get(doc_id=data.category_id)
    if not category:
        raise NotFoundException(detail="布草类别不存在")

    record = {
        "customer_id": data.customer_id,
        "category_id": data.category_id,
        "batch_no": data.batch_no,
        "quantity": data.quantity,
        "stain_level": data.stain_level,
        "status": ClothStatus.PENDING_SORT,
        "damage_description": data.damage_description,
        "remark": data.remark,
        "sorter_id": None,
        "sorting_line": None,
        "washing_batch_no": None,
        "washing_line_id": None,
        "work_team_id": None,
        "created_at": now_str(),
        "updated_at": now_str(),
        "sorted_at": None,
        "washing_completed_at": None,
        "qc_at": None
    }

    record_id = cloth_records_table.insert(record)
    record["id"] = record_id
    return record


def sort_cloth_record(record_id: int, data: SortingRecordCreate, sorter_id: int) -> dict:
    record = get_cloth_record_or_404(record_id)

    if record["status"] not in [ClothStatus.PENDING_SORT, ClothStatus.REWASHING]:
        raise ValidationException(detail=f"当前状态「{record['status']}」不可分拣，仅「待分拣」或「补洗中」可分拣")

    washing_line = washing_lines_table.get(doc_id=data.washing_line_id)
    if not washing_line:
        raise NotFoundException(detail="清洗线不存在")

    work_team = work_teams_table.get(doc_id=data.work_team_id)
    if not work_team:
        raise NotFoundException(detail="责任班组不存在")

    if not data.sorting_line or not data.sorting_line.strip():
        raise ValidationException(detail="分拣线不能为空")
    if not data.washing_batch_no or not data.washing_batch_no.strip():
        raise ValidationException(detail="清洗批号不能为空")

    updates = {
        "status": ClothStatus.WASHING,
        "sorter_id": sorter_id,
        "sorting_line": data.sorting_line,
        "washing_batch_no": data.washing_batch_no,
        "washing_line_id": data.washing_line_id,
        "work_team_id": data.work_team_id,
        "sorted_at": now_str(),
        "washing_completed_at": None,
        "updated_at": now_str()
    }

    cloth_records_table.update(updates, doc_ids=[record_id])
    updated = get_cloth_record_or_404(record_id)
    return updated


def complete_washing(record_id: int, user_id: int) -> dict:
    record = get_cloth_record_or_404(record_id)

    if record["status"] not in [ClothStatus.WASHING, ClothStatus.REWASHING]:
        raise ValidationException(
            detail=f"当前状态「{record['status']}」不可完成清洗，仅「清洗中」或「补洗中」可完成清洗"
        )

    updates = {
        "status": ClothStatus.PENDING_QC,
        "washing_completed_at": now_str(),
        "updated_at": now_str()
    }
    cloth_records_table.update(updates, doc_ids=[record_id])

    updated = get_cloth_record_or_404(record_id)
    return updated


def request_rewash(record_id: int, reason: str, user_id: int) -> dict:
    record = get_cloth_record_or_404(record_id)

    if record["status"] not in [ClothStatus.PENDING_QC, ClothStatus.WASHING, ClothStatus.READY_FOR_DELIVERY]:
        raise ValidationException(
            detail=f"当前状态「{record['status']}」不可申请补洗，仅「待质检」「清洗中」「可出厂」可申请补洗"
        )

    rewash_count = len(rewash_records_table.search(
        lambda r: r["cloth_record_id"] == record_id
    ))

    rewash_data = {
        "cloth_record_id": record_id,
        "reason": reason,
        "rewash_count": rewash_count + 1,
        "created_at": now_str()
    }
    rewash_records_table.insert(rewash_data)

    updates = {
        "status": ClothStatus.REWASHING,
        "updated_at": now_str()
    }
    cloth_records_table.update(updates, doc_ids=[record_id])

    updated = get_cloth_record_or_404(record_id)
    return updated


def create_qc_record(record_id: int, data: QcRecordCreate, inspector_id: int) -> dict:
    record = get_cloth_record_or_404(record_id)

    if record["status"] != ClothStatus.PENDING_QC:
        raise ValidationException(
            detail=f"当前状态「{record['status']}」不可质检，仅「待质检」可质检，请先完成清洗"
        )

    qc_data = {
        "cloth_record_id": record_id,
        "inspector_id": inspector_id,
        "cleanliness": data.cleanliness,
        "damage_recheck": data.damage_recheck,
        "rewash_conclusion": data.rewash_conclusion,
        "delivery_suggestion": data.delivery_suggestion,
        "qc_remark": data.qc_remark,
        "created_at": now_str()
    }
    qc_id = qc_records_table.insert(qc_data)
    qc_data["id"] = qc_id

    if data.delivery_suggestion == DeliverySuggestion.APPROVE:
        new_status = ClothStatus.READY_FOR_DELIVERY
    elif data.delivery_suggestion == DeliverySuggestion.REWASH:
        new_status = ClothStatus.REWASHING
    elif data.delivery_suggestion == DeliverySuggestion.HOLD:
        new_status = ClothStatus.HOLD_DELIVERY
    else:
        new_status = record["status"]

    updates = {
        "status": new_status,
        "qc_at": now_str(),
        "updated_at": now_str()
    }
    cloth_records_table.update(updates, doc_ids=[record_id])

    return qc_data


def confirm_delivery(record_id: int, user_id: int) -> dict:
    record = get_cloth_record_or_404(record_id)

    if record["status"] != ClothStatus.READY_FOR_DELIVERY:
        raise ValidationException(
            detail=f"当前状态「{record['status']}」不可出厂确认，仅「可出厂」可确认出厂"
        )

    updates = {
        "status": "已出厂",
        "updated_at": now_str()
    }
    cloth_records_table.update(updates, doc_ids=[record_id])

    updated = get_cloth_record_or_404(record_id)
    return updated


def get_cloth_record(record_id: int) -> Optional[dict]:
    record = cloth_records_table.get(doc_id=record_id)
    if record:
        record["id"] = record_id
    return record


def list_cloth_records(filters: Optional[dict] = None) -> List[dict]:
    records = cloth_records_table.all()

    if filters:
        if filters.get("customer_id"):
            records = [r for r in records if r["customer_id"] == filters["customer_id"]]
        if filters.get("category_id"):
            records = [r for r in records if r["category_id"] == filters["category_id"]]
        if filters.get("washing_line_id"):
            records = [r for r in records if r.get("washing_line_id") == filters["washing_line_id"]]
        if filters.get("work_team_id"):
            records = [r for r in records if r.get("work_team_id") == filters["work_team_id"]]
        if filters.get("status"):
            records = [r for r in records if r["status"] == filters["status"]]
        if filters.get("stain_level"):
            records = [r for r in records if r["stain_level"] == filters["stain_level"]]
        if filters.get("date_from"):
            records = [r for r in records if r["created_at"] >= filters["date_from"]]
        if filters.get("date_to"):
            records = [r for r in records if r["created_at"] <= filters["date_to"] + "T23:59:59"]

    result = []
    for r in records:
        item = dict(r)
        item["id"] = r.doc_id
        result.append(item)

    result.sort(key=lambda x: x["created_at"], reverse=True)
    return result


def get_rewash_task_or_404(task_id: int) -> dict:
    task = rewash_tasks_table.get(doc_id=task_id)
    if not task:
        raise NotFoundException(detail=f"补洗任务 {task_id} 不存在")
    task["id"] = task_id
    return task


def create_rewash_task(record_id: int, data: RewashTaskCreate, creator_id: int) -> dict:
    record = get_cloth_record_or_404(record_id)

    if record["status"] not in [ClothStatus.PENDING_QC, ClothStatus.WASHING, ClothStatus.READY_FOR_DELIVERY, ClothStatus.REWASHING]:
        raise ValidationException(
            detail=f"当前状态「{record['status']}」不可创建补洗任务"
        )

    washing_line = washing_lines_table.get(doc_id=data.responsible_washing_line_id)
    if not washing_line:
        raise NotFoundException(detail="责任清洗线不存在")

    work_team = work_teams_table.get(doc_id=data.responsible_work_team_id)
    if not work_team:
        raise NotFoundException(detail="责任班组不存在")

    existing_rewash_count = len(rewash_tasks_table.search(
        RewashTaskQuery.cloth_record_id == record_id
    ))

    task_data = {
        "cloth_record_id": record_id,
        "creator_id": creator_id,
        "reason": data.reason,
        "severity": data.severity,
        "expected_completion_time": data.expected_completion_time,
        "responsible_washing_line_id": data.responsible_washing_line_id,
        "responsible_work_team_id": data.responsible_work_team_id,
        "status": RewashTaskStatus.PENDING,
        "rewash_count": existing_rewash_count + 1,
        "remark": data.remark,
        "created_at": now_str(),
        "updated_at": now_str(),
        "started_at": None,
        "completed_at": None,
        "rechecked_at": None,
        "completer_id": None,
        "completion_remark": None,
        "rechecker_id": None,
        "recheck_cleanliness": None,
        "recheck_damage": None,
        "final_conclusion": None,
        "recheck_remark": None
    }

    task_id = rewash_tasks_table.insert(task_data)
    task_data["id"] = task_id

    rewash_records_table.insert({
        "cloth_record_id": record_id,
        "reason": data.reason,
        "rewash_count": existing_rewash_count + 1,
        "created_at": now_str()
    })

    cloth_records_table.update({
        "status": ClothStatus.REWASHING,
        "updated_at": now_str()
    }, doc_ids=[record_id])

    return task_data


def list_rewash_tasks(filters: Optional[dict] = None) -> List[dict]:
    tasks = rewash_tasks_table.all()

    if filters:
        if filters.get("cloth_record_id"):
            tasks = [t for t in tasks if t["cloth_record_id"] == filters["cloth_record_id"]]
        if filters.get("status"):
            tasks = [t for t in tasks if t["status"] == filters["status"]]
        if filters.get("responsible_washing_line_id"):
            tasks = [t for t in tasks if t["responsible_washing_line_id"] == filters["responsible_washing_line_id"]]
        if filters.get("responsible_work_team_id"):
            tasks = [t for t in tasks if t["responsible_work_team_id"] == filters["responsible_work_team_id"]]
        if filters.get("severity"):
            tasks = [t for t in tasks if t["severity"] == filters["severity"]]

    result = []
    for t in tasks:
        item = dict(t)
        item["id"] = t.doc_id
        result.append(item)

    result.sort(key=lambda x: x["created_at"], reverse=True)
    return result


def start_rewash_task(task_id: int, user_id: int) -> dict:
    task = get_rewash_task_or_404(task_id)

    if task["status"] != RewashTaskStatus.PENDING:
        raise ValidationException(
            detail=f"当前补洗任务状态「{task['status']}」不可启动，仅「待补洗」可启动"
        )

    updates = {
        "status": RewashTaskStatus.IN_PROGRESS,
        "started_at": now_str(),
        "updated_at": now_str()
    }
    rewash_tasks_table.update(updates, doc_ids=[task_id])

    record = get_cloth_record_or_404(task["cloth_record_id"])
    cloth_records_table.update({
        "status": ClothStatus.REWASHING,
        "updated_at": now_str()
    }, doc_ids=[task["cloth_record_id"]])

    return get_rewash_task_or_404(task_id)


def complete_rewash_task(task_id: int, data: RewashTaskComplete, user_id: int) -> dict:
    task = get_rewash_task_or_404(task_id)

    if task["status"] not in [RewashTaskStatus.PENDING, RewashTaskStatus.IN_PROGRESS]:
        raise ValidationException(
            detail=f"当前补洗任务状态「{task['status']}」不可完成，仅「待补洗」或「补洗中」可完成"
        )

    updates = {
        "status": RewashTaskStatus.COMPLETED,
        "completed_at": now_str(),
        "completer_id": user_id,
        "completion_remark": data.completion_remark,
        "updated_at": now_str()
    }
    rewash_tasks_table.update(updates, doc_ids=[task_id])

    cloth_records_table.update({
        "status": ClothStatus.PENDING_QC,
        "updated_at": now_str()
    }, doc_ids=[task["cloth_record_id"]])

    return get_rewash_task_or_404(task_id)


def recheck_rewash_task(task_id: int, data: RewashTaskRecheck, user_id: int) -> dict:
    task = get_rewash_task_or_404(task_id)

    if task["status"] != RewashTaskStatus.COMPLETED:
        raise ValidationException(
            detail=f"当前补洗任务状态「{task['status']}」不可复检，仅「补洗完成待复检」可复检"
        )

    recheck_data = {
        "rewash_task_id": task_id,
        "cloth_record_id": task["cloth_record_id"],
        "rechecker_id": user_id,
        "cleanliness": data.cleanliness,
        "damage_recheck": data.damage_recheck,
        "final_conclusion": data.final_conclusion,
        "recheck_remark": data.recheck_remark,
        "created_at": now_str()
    }
    recheck_id = rewash_recheck_records_table.insert(recheck_data)
    recheck_data["id"] = recheck_id

    if data.final_conclusion == RewashFinalConclusion.DELIVERY:
        new_task_status = RewashTaskStatus.PASSED
        new_cloth_status = ClothStatus.READY_FOR_DELIVERY
    elif data.final_conclusion == RewashFinalConclusion.CONTINUE_REWASH:
        new_task_status = RewashTaskStatus.FAILED
        new_cloth_status = ClothStatus.REWASHING
    elif data.final_conclusion == RewashFinalConclusion.HOLD:
        new_task_status = RewashTaskStatus.PASSED
        new_cloth_status = ClothStatus.HOLD_DELIVERY
    else:
        new_task_status = task["status"]
        new_cloth_status = None

    task_updates = {
        "status": new_task_status,
        "rechecked_at": now_str(),
        "rechecker_id": user_id,
        "recheck_cleanliness": data.cleanliness,
        "recheck_damage": data.damage_recheck,
        "final_conclusion": data.final_conclusion,
        "recheck_remark": data.recheck_remark,
        "updated_at": now_str()
    }
    rewash_tasks_table.update(task_updates, doc_ids=[task_id])

    if new_cloth_status:
        cloth_records_table.update({
            "status": new_cloth_status,
            "qc_at": now_str(),
            "updated_at": now_str()
        }, doc_ids=[task["cloth_record_id"]])

    return recheck_data


def get_cloth_record_detail(record_id: int) -> dict:
    record = get_cloth_record_or_404(record_id)

    rewash_tasks = rewash_tasks_table.search(RewashTaskQuery.cloth_record_id == record_id)
    rewash_tasks_list = []
    for t in rewash_tasks:
        item = dict(t)
        item["id"] = t.doc_id
        washing_line = washing_lines_table.get(doc_id=t["responsible_washing_line_id"])
        item["responsible_washing_line_name"] = washing_line["name"] if washing_line else None
        work_team = work_teams_table.get(doc_id=t["responsible_work_team_id"])
        item["responsible_work_team_name"] = work_team["name"] if work_team else None
        creator = users_table.get(doc_id=t["creator_id"])
        item["creator_name"] = creator["full_name"] if creator else None
        if t.get("completer_id"):
            completer = users_table.get(doc_id=t["completer_id"])
            item["completer_name"] = completer["full_name"] if completer else None
        if t.get("rechecker_id"):
            rechecker = users_table.get(doc_id=t["rechecker_id"])
            item["rechecker_name"] = rechecker["full_name"] if rechecker else None
        rewash_tasks_list.append(item)

    rewash_history = rewash_records_table.search(RewashRecordQuery.cloth_record_id == record_id)
    rewash_history_list = []
    for r in rewash_history:
        item = dict(r)
        item["id"] = r.doc_id
        rewash_history_list.append(item)

    recheck_history = rewash_recheck_records_table.search(RewashRecheckQuery.cloth_record_id == record_id)
    recheck_history_list = []
    for r in recheck_history:
        item = dict(r)
        item["id"] = r.doc_id
        rechecker = users_table.get(doc_id=r["rechecker_id"])
        item["rechecker_name"] = rechecker["full_name"] if rechecker else None
        recheck_history_list.append(item)

    active_tasks = [t for t in rewash_tasks_list if t["status"] in [
        RewashTaskStatus.PENDING, RewashTaskStatus.IN_PROGRESS, RewashTaskStatus.COMPLETED
    ]]
    current_rewash_status = active_tasks[0]["status"] if active_tasks else None

    detail = dict(record)
    detail["rewash_tasks"] = rewash_tasks_list
    detail["rewash_history"] = rewash_history_list
    detail["recheck_history"] = recheck_history_list
    detail["current_rewash_status"] = current_rewash_status
    detail["total_rewash_count"] = len(rewash_tasks_list)

    return detail


def list_pending_rewash_tasks() -> List[dict]:
    pending_statuses = [RewashTaskStatus.PENDING, RewashTaskStatus.IN_PROGRESS, RewashTaskStatus.COMPLETED]
    all_tasks = list_rewash_tasks()
    result = []
    for task in all_tasks:
        if task["status"] in pending_statuses:
            record = cloth_records_table.get(doc_id=task["cloth_record_id"])
            if record:
                task["batch_no"] = record["batch_no"]
                task["customer_id"] = record["customer_id"]
                task["category_id"] = record["category_id"]
                task["quantity"] = record["quantity"]
                customer = customers_table.get(doc_id=record["customer_id"])
                task["customer_name"] = customer["name"] if customer else None
                category = cloth_categories_table.get(doc_id=record["category_id"])
                task["category_name"] = category["name"] if category else None
            washing_line = washing_lines_table.get(doc_id=task["responsible_washing_line_id"])
            task["responsible_washing_line_name"] = washing_line["name"] if washing_line else None
            work_team = work_teams_table.get(doc_id=task["responsible_work_team_id"])
            task["responsible_work_team_name"] = work_team["name"] if work_team else None
            result.append(task)
    result.sort(key=lambda x: x["expected_completion_time"])
    return result
