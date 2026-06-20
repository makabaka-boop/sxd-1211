from litestar.controller import Controller
from litestar import get, post, Request
from litestar.exceptions import NotFoundException, NotAuthorizedException
from litestar.di import Provide
from typing import List, Optional

from app.auth import get_current_user
from app.schemas import UserRole, ClothRecord, ClothRecordCreate, ClothRecordFilter
from app.schemas import SortingRecordCreate, RewashRecordCreate, ClothStatus
from app.services.laundry_service import (
    create_cloth_record, sort_cloth_record, request_rewash,
    get_cloth_record, list_cloth_records
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

    @post("/cloth-records/{record_id:int}/rewash", summary="申请补洗")
    async def rewash_request(self, current_user: dict, record_id: int, data: RewashRecordCreate) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
        record = request_rewash(record_id, data.reason, current_user["id"])
        return record


sorter_router_controllers = [SorterController]
