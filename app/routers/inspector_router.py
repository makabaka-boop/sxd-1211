from litestar.controller import Controller
from litestar import get, post, Request
from litestar.exceptions import NotFoundException, NotAuthorizedException
from litestar.di import Provide
from typing import List, Optional

from app.auth import get_current_user
from app.schemas import UserRole, QcRecordCreate, QcRecord, ClothStatus
from app.services.laundry_service import create_qc_record, confirm_delivery, get_cloth_record, list_cloth_records
from app.database import qc_records_table, QcRecordQuery


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

    @post("/cloth-records/{record_id:int}/delivery", summary="出厂确认")
    async def confirm_deliver(self, current_user: dict, record_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        record = confirm_delivery(record_id, current_user["id"])
        return record

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
        records = list_cloth_records({"status": ClothStatus.WASHING.value})
        records += list_cloth_records({"status": ClothStatus.REWASHING.value})
        records.sort(key=lambda x: x["created_at"])
        return records


inspector_router_controllers = [InspectorController]
