from litestar.controller import Controller
from litestar import get, post, Request
from litestar.exceptions import NotFoundException, NotAuthorizedException
from litestar.di import Provide
from typing import List, Optional

from app.auth import get_current_user
from app.schemas import (
    UserRole, QcRecordCreate, QcRecord, ClothStatus,
    RewashTaskCreate, RewashTaskRecheck, RewashTaskStatus,
    DeliveryHandoverCreate, DeliveryStage
)
from app.services.laundry_service import (
    create_qc_record, confirm_delivery, get_cloth_record, list_cloth_records,
    create_rewash_task, list_rewash_tasks, get_rewash_task_or_404,
    recheck_rewash_task, get_cloth_record_detail
)
from app.database import (
    qc_records_table, QcRecordQuery, rewash_recheck_records_table, RewashRecheckQuery
)


def check_role(current_user: dict, allowed_roles: list):
    if current_user["role"] not in allowed_roles:
        raise NotAuthorizedException(detail="权限不足")


class InspectorController(Controller):
    path = "/inspector"
    tags = ["质检员"]
    dependencies = {"current_user": Provide(get_current_user)}

    @post("/cloth-records/{record_id:int}/qc", summary="质检记录")
    async def create_qc(self, current_user: dict, record_id: int, data: QcRecordCreate) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        qc = create_qc_record(record_id, data, current_user["id"])
        return qc

    @post("/cloth-records/{record_id:int}/delivery", summary="出厂交接确认")
    async def confirm_deliver(self, current_user: dict, record_id: int, data: DeliveryHandoverCreate) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        record = confirm_delivery(record_id, data, current_user["id"])
        return record

    @get("/cloth-records/ready-for-delivery", summary="获取可出厂待交接列表")
    async def list_ready_for_delivery(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        records = list_cloth_records({"delivery_stage": DeliveryStage.PENDING_HANDOVER.value})
        records.sort(key=lambda x: x.get("qc_at") or x["created_at"])
        return records

    @get("/cloth-records/delivered", summary="获取已完成交接列表")
    async def list_delivered(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        records = list_cloth_records({"delivery_stage": DeliveryStage.COMPLETED_HANDOVER.value})
        records.sort(key=lambda x: x.get("delivered_at") or x["updated_at"], reverse=True)
        return records

    @get("/cloth-records/{record_id:int}/qc", summary="获取布草的质检记录")
    async def get_qc_records(self, current_user: dict, record_id: int) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        record = get_cloth_record(record_id)
        if not record:
            raise NotFoundException(detail="布草记录不存在")

        qc_list = qc_records_table.search(QcRecordQuery.cloth_record_id == record_id)
        result = []
        for qc in qc_list:
            item = dict(qc)
            item["id"] = qc.doc_id
            result.append(item)
        return result

    @get("/pending-qc", summary="获取待质检列表")
    async def list_pending_qc(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        records = list_cloth_records({"status": ClothStatus.PENDING_QC.value})
        records.sort(key=lambda x: x.get("washing_completed_at") or x["created_at"])
        return records

    @post("/cloth-records/{record_id:int}/rewash-tasks", summary="创建补洗任务")
    async def create_rewash(self, current_user: dict, record_id: int, data: RewashTaskCreate) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        task = create_rewash_task(record_id, data, current_user["id"])
        return task

    @get("/rewash-tasks", summary="获取补洗任务列表")
    async def list_rewash(
        self,
        current_user: dict,
        cloth_record_id: Optional[int] = None,
        status: Optional[RewashTaskStatus] = None,
        responsible_washing_line_id: Optional[int] = None,
        responsible_work_team_id: Optional[int] = None,
        severity: Optional[str] = None
    ) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        filters = {
            "cloth_record_id": cloth_record_id,
            "status": status.value if status else None,
            "responsible_washing_line_id": responsible_washing_line_id,
            "responsible_work_team_id": responsible_work_team_id,
            "severity": severity
        }
        tasks = list_rewash_tasks(filters)
        return tasks

    @get("/rewash-tasks/{task_id:int}", summary="获取补洗任务详情")
    async def get_rewash(self, current_user: dict, task_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        task = get_rewash_task_or_404(task_id)
        return task

    @post("/rewash-tasks/{task_id:int}/recheck", summary="复检补洗任务")
    async def recheck_rewash(self, current_user: dict, task_id: int, data: RewashTaskRecheck) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        recheck = recheck_rewash_task(task_id, data, current_user["id"])
        return recheck

    @get("/cloth-records/{record_id:int}/detail", summary="获取布草记录详情（含补洗历史）")
    async def get_record_detail(self, current_user: dict, record_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        detail = get_cloth_record_detail(record_id)
        return detail

    @get("/rewash-tasks/{task_id:int}/rechecks", summary="获取补洗任务的复检记录")
    async def get_rewash_rechecks(self, current_user: dict, task_id: int) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        task = get_rewash_task_or_404(task_id)
        recheck_list = rewash_recheck_records_table.search(RewashRecheckQuery.rewash_task_id == task_id)
        result = []
        for r in recheck_list:
            item = dict(r)
            item["id"] = r.doc_id
            result.append(item)
        return result


inspector_router_controllers = [InspectorController]
