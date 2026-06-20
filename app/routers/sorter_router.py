from litestar.controller import Controller
from litestar import get, post, Request
from litestar.exceptions import NotFoundException, NotAuthorizedException
from litestar.di import Provide
from typing import List, Optional

from app.auth import get_current_user
from app.schemas import (
    UserRole, ClothRecord, ClothRecordCreate, ClothRecordFilter,
    SortingRecordCreate, RewashRecordCreate, ClothStatus,
    RewashTaskComplete, RewashTaskStatus, DeliveryStage
)
from app.services.laundry_service import (
    create_cloth_record, sort_cloth_record, request_rewash, complete_washing,
    get_cloth_record, list_cloth_records,
    list_pending_rewash_tasks, list_rewash_tasks, get_rewash_task_or_404,
    start_rewash_task, complete_rewash_task, get_cloth_record_detail
)


def check_role(current_user: dict, allowed_roles: list):
    if current_user["role"] not in allowed_roles:
        raise NotAuthorizedException(detail="权限不足")


class SorterController(Controller):
    path = "/sorter"
    tags = ["分拣员"]
    dependencies = {"current_user": Provide(get_current_user)}

    @post("/cloth-records", summary="登记布草入厂")
    async def create_record(self, current_user: dict, data: ClothRecordCreate) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
        record = create_cloth_record(data, current_user["id"])
        return record

    @get("/cloth-records", summary="获取布草记录列表")
    async def list_records(
        self,
        current_user: dict,
        customer_id: Optional[int] = None,
        category_id: Optional[int] = None,
        washing_line_id: Optional[int] = None,
        work_team_id: Optional[int] = None,
        status: Optional[ClothStatus] = None,
        delivery_stage: Optional[DeliveryStage] = None,
        stain_level: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER, UserRole.INSPECTOR])
        filters = {
            "customer_id": customer_id,
            "category_id": category_id,
            "washing_line_id": washing_line_id,
            "work_team_id": work_team_id,
            "status": status.value if status else None,
            "delivery_stage": delivery_stage.value if delivery_stage else None,
            "stain_level": stain_level,
            "date_from": date_from,
            "date_to": date_to
        }
        records = list_cloth_records(filters)
        return records

    @get("/cloth-records/{record_id:int}", summary="获取布草记录详情")
    async def get_record(self, current_user: dict, record_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER, UserRole.INSPECTOR])
        record = get_cloth_record(record_id)
        if not record:
            raise NotFoundException(detail="布草记录不存在")
        return record

    @post("/cloth-records/{record_id:int}/sort", summary="分拣布草")
    async def sort_record(self, current_user: dict, record_id: int, data: SortingRecordCreate) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
        record = sort_cloth_record(record_id, data, current_user["id"])
        return record

    @post("/cloth-records/{record_id:int}/complete-washing", summary="完成清洗，流转至待质检")
    async def complete_washing_record(self, current_user: dict, record_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
        record = complete_washing(record_id, current_user["id"])
        return record

    @post("/cloth-records/{record_id:int}/rewash", summary="申请补洗")
    async def rewash_request(self, current_user: dict, record_id: int, data: RewashRecordCreate) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
        record = request_rewash(record_id, data.reason, current_user["id"])
        return record

    @get("/rewash-tasks/pending", summary="获取待补洗任务列表")
    async def list_pending_rewash(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
        tasks = list_pending_rewash_tasks()
        return tasks

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
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
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
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
        task = get_rewash_task_or_404(task_id)
        return task

    @post("/rewash-tasks/{task_id:int}/start", summary="启动补洗任务")
    async def start_rewash(self, current_user: dict, task_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
        task = start_rewash_task(task_id, current_user["id"])
        return task

    @post("/rewash-tasks/{task_id:int}/complete", summary="完成补洗任务")
    async def complete_rewash(self, current_user: dict, task_id: int, data: RewashTaskComplete) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
        task = complete_rewash_task(task_id, data, current_user["id"])
        return task

    @get("/cloth-records/{record_id:int}/detail", summary="获取布草记录详情（含补洗历史）")
    async def get_record_detail(self, current_user: dict, record_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER, UserRole.INSPECTOR])
        detail = get_cloth_record_detail(record_id)
        return detail


sorter_router_controllers = [SorterController]
