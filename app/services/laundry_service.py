from datetime import datetime
from typing import Optional, List
from litestar.exceptions import ValidationException, NotFoundException

from app.database import (
    cloth_records_table, ClothRecordQuery,
    rewash_records_table, qc_records_table,
    customers_table, cloth_categories_table, washing_lines_table, work_teams_table
)
from app.schemas import ClothStatus, ClothRecordCreate, SortingRecordCreate, QcRecordCreate
from app.schemas import RewashRecordCreate, CleanlinessLevel, DeliverySuggestion, DamageLevel
from app.config import settings


def now_str() -> str:
    return datetime.now().isoformat()


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
        "washing_line_id": None,
        "work_team_id": None,
        "created_at": now_str(),
        "updated_at": now_str(),
        "sorted_at": None,
        "qc_at": None
    }

    record_id = cloth_records_table.insert(record)
    record["id"] = record_id
    return record


def sort_cloth_record(record_id: int, data: SortingRecordCreate, sorter_id: int) -> dict:
    record = cloth_records_table.get(doc_id=record_id)
    if not record:
        raise NotFoundException(detail="布草记录不存在")

    if record["status"] not in [ClothStatus.PENDING_SORT, ClothStatus.REWASHING]:
        raise ValidationException(detail=f"当前状态 {record['status']} 不可分拣")

    washing_line = washing_lines_table.get(doc_id=data.washing_line_id)
    if not washing_line:
        raise NotFoundException(detail="清洗线不存在")

    work_team = work_teams_table.get(doc_id=data.work_team_id)
    if not work_team:
        raise NotFoundException(detail="责任班组不存在")

    updates = {
        "status": ClothStatus.WASHING,
        "sorter_id": sorter_id,
        "washing_line_id": data.washing_line_id,
        "work_team_id": data.work_team_id,
        "sorted_at": now_str(),
        "updated_at": now_str()
    }

    cloth_records_table.update(updates, doc_ids=[record_id])
    updated = cloth_records_table.get(doc_id=record_id)
    updated["id"] = record_id
    return updated


def request_rewash(record_id: int, reason: str, sorter_id: int) -> dict:
    record = cloth_records_table.get(doc_id=record_id)
    if not record:
        raise NotFoundException(detail="布草记录不存在")

    if record["status"] not in [ClothStatus.PENDING_SORT, ClothStatus.WASHING, ClothStatus.PENDING_QC]:
        raise ValidationException(detail=f"当前状态 {record['status']} 不可申请补洗")

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

    updated = cloth_records_table.get(doc_id=record_id)
    updated["id"] = record_id
    return updated


def create_qc_record(record_id: int, data: QcRecordCreate, inspector_id: int) -> dict:
    record = cloth_records_table.get(doc_id=record_id)
    if not record:
        raise NotFoundException(detail="布草记录不存在")

    if record["status"] not in [ClothStatus.WASHING, ClothStatus.REWASHING]:
        raise ValidationException(detail=f"当前状态 {record['status']} 不可质检")

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

    new_status = record["status"]
    if data.delivery_suggestion == DeliverySuggestion.APPROVE:
        new_status = ClothStatus.READY_FOR_DELIVERY
    elif data.delivery_suggestion == DeliverySuggestion.REWASH:
        new_status = ClothStatus.REWASHING
    elif data.delivery_suggestion == DeliverySuggestion.HOLD:
        new_status = ClothStatus.HOLD_DELIVERY

    updates = {
        "status": new_status,
        "qc_at": now_str(),
        "updated_at": now_str()
    }
    cloth_records_table.update(updates, doc_ids=[record_id])

    return qc_data


def confirm_delivery(record_id: int, user_id: int) -> dict:
    record = cloth_records_table.get(doc_id=record_id)
    if not record:
        raise NotFoundException(detail="布草记录不存在")

    if record["status"] != ClothStatus.READY_FOR_DELIVERY:
        raise ValidationException(detail=f"当前状态 {record['status']} 不可出厂确认")

    updates = {
        "status": "已出厂",
        "updated_at": now_str()
    }
    cloth_records_table.update(updates, doc_ids=[record_id])

    updated = cloth_records_table.get(doc_id=record_id)
    updated["id"] = record_id
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
