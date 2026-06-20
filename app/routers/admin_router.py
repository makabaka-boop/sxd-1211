from litestar.controller import Controller
from litestar import get, post, put, delete, Request, status_codes
from litestar.exceptions import NotFoundException, NotAuthorizedException
from litestar.di import Provide
from typing import List

from app.auth import get_current_user
from app.schemas import UserRole, Customer, CustomerCreate, ClothCategory, ClothCategoryCreate
from app.schemas import WashingLine, WashingLineCreate, BatchRule, BatchRuleCreate
from app.schemas import WorkTeam, WorkTeamCreate, QcStandard, QcStandardCreate
from app.database import (
    customers_table, CustomerQuery,
    cloth_categories_table, ClothCategoryQuery,
    washing_lines_table, WashingLineQuery,
    batch_rules_table, BatchRuleQuery,
    work_teams_table, WorkTeamQuery,
    qc_standards_table, QcStandardQuery
)


def check_role(current_user: dict, allowed_roles: list):
    if current_user["role"] not in allowed_roles:
        raise NotAuthorizedException(detail="权限不足")


class CustomerController(Controller):
    path = "/customers"
    tags = ["客户单位"]
    dependencies = {"current_user": Provide(get_current_user)}

    @get("/", summary="获取客户单位列表")
    async def list(self, current_user: dict) -> List[Customer]:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER, UserRole.INSPECTOR])
        items = customers_table.all()
        return [Customer(id=item.doc_id, **item) for item in items]

    @post("/", summary="创建客户单位")
    async def create(self, current_user: dict, data: CustomerCreate) -> Customer:
        check_role(current_user, [UserRole.ADMIN])
        item_id = customers_table.insert(data.model_dump())
        return Customer(id=item_id, **data.model_dump())

    @put("/{item_id:int}", summary="更新客户单位")
    async def update(self, current_user: dict, item_id: int, data: CustomerCreate) -> Customer:
        check_role(current_user, [UserRole.ADMIN])
        item = customers_table.get(doc_id=item_id)
        if not item:
            raise NotFoundException(detail="客户单位不存在")
        customers_table.update(data.model_dump(), doc_ids=[item_id])
        return Customer(id=item_id, **data.model_dump())

    @delete("/{item_id:int}", summary="删除客户单位", status_code=200)
    async def delete(self, current_user: dict, item_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN])
        customers_table.remove(doc_ids=[item_id])
        return {"message": "删除成功"}


class ClothCategoryController(Controller):
    path = "/cloth-categories"
    tags = ["布草类别"]
    dependencies = {"current_user": Provide(get_current_user)}

    @get("/", summary="获取布草类别列表")
    async def list(self, current_user: dict) -> List[ClothCategory]:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER, UserRole.INSPECTOR])
        items = cloth_categories_table.all()
        return [ClothCategory(id=item.doc_id, **item) for item in items]

    @post("/", summary="创建布草类别")
    async def create(self, current_user: dict, data: ClothCategoryCreate) -> ClothCategory:
        check_role(current_user, [UserRole.ADMIN])
        item_id = cloth_categories_table.insert(data.model_dump())
        return ClothCategory(id=item_id, **data.model_dump())

    @put("/{item_id:int}", summary="更新布草类别")
    async def update(self, current_user: dict, item_id: int, data: ClothCategoryCreate) -> ClothCategory:
        check_role(current_user, [UserRole.ADMIN])
        item = cloth_categories_table.get(doc_id=item_id)
        if not item:
            raise NotFoundException(detail="布草类别不存在")
        cloth_categories_table.update(data.model_dump(), doc_ids=[item_id])
        return ClothCategory(id=item_id, **data.model_dump())

    @delete("/{item_id:int}", summary="删除布草类别", status_code=200)
    async def delete(self, current_user: dict, item_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN])
        cloth_categories_table.remove(doc_ids=[item_id])
        return {"message": "删除成功"}


class WashingLineController(Controller):
    path = "/washing-lines"
    tags = ["清洗线"]
    dependencies = {"current_user": Provide(get_current_user)}

    @get("/", summary="获取清洗线列表")
    async def list(self, current_user: dict) -> List[WashingLine]:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER, UserRole.INSPECTOR])
        items = washing_lines_table.all()
        return [WashingLine(id=item.doc_id, **item) for item in items]

    @post("/", summary="创建清洗线")
    async def create(self, current_user: dict, data: WashingLineCreate) -> WashingLine:
        check_role(current_user, [UserRole.ADMIN])
        item_id = washing_lines_table.insert(data.model_dump())
        return WashingLine(id=item_id, **data.model_dump())

    @put("/{item_id:int}", summary="更新清洗线")
    async def update(self, current_user: dict, item_id: int, data: WashingLineCreate) -> WashingLine:
        check_role(current_user, [UserRole.ADMIN])
        item = washing_lines_table.get(doc_id=item_id)
        if not item:
            raise NotFoundException(detail="清洗线不存在")
        washing_lines_table.update(data.model_dump(), doc_ids=[item_id])
        return WashingLine(id=item_id, **data.model_dump())

    @delete("/{item_id:int}", summary="删除清洗线", status_code=200)
    async def delete(self, current_user: dict, item_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN])
        washing_lines_table.remove(doc_ids=[item_id])
        return {"message": "删除成功"}


class BatchRuleController(Controller):
    path = "/batch-rules"
    tags = ["批次规则"]
    dependencies = {"current_user": Provide(get_current_user)}

    @get("/", summary="获取批次规则列表")
    async def list(self, current_user: dict) -> List[BatchRule]:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
        items = batch_rules_table.all()
        return [BatchRule(id=item.doc_id, **item) for item in items]

    @post("/", summary="创建批次规则")
    async def create(self, current_user: dict, data: BatchRuleCreate) -> BatchRule:
        check_role(current_user, [UserRole.ADMIN])
        item_id = batch_rules_table.insert(data.model_dump())
        return BatchRule(id=item_id, **data.model_dump())

    @put("/{item_id:int}", summary="更新批次规则")
    async def update(self, current_user: dict, item_id: int, data: BatchRuleCreate) -> BatchRule:
        check_role(current_user, [UserRole.ADMIN])
        item = batch_rules_table.get(doc_id=item_id)
        if not item:
            raise NotFoundException(detail="批次规则不存在")
        batch_rules_table.update(data.model_dump(), doc_ids=[item_id])
        return BatchRule(id=item_id, **data.model_dump())

    @delete("/{item_id:int}", summary="删除批次规则", status_code=200)
    async def delete(self, current_user: dict, item_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN])
        batch_rules_table.remove(doc_ids=[item_id])
        return {"message": "删除成功"}


class WorkTeamController(Controller):
    path = "/work-teams"
    tags = ["责任班组"]
    dependencies = {"current_user": Provide(get_current_user)}

    @get("/", summary="获取责任班组列表")
    async def list(self, current_user: dict) -> List[WorkTeam]:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER, UserRole.INSPECTOR])
        items = work_teams_table.all()
        return [WorkTeam(id=item.doc_id, **item) for item in items]

    @post("/", summary="创建责任班组")
    async def create(self, current_user: dict, data: WorkTeamCreate) -> WorkTeam:
        check_role(current_user, [UserRole.ADMIN])
        item_id = work_teams_table.insert(data.model_dump())
        return WorkTeam(id=item_id, **data.model_dump())

    @put("/{item_id:int}", summary="更新责任班组")
    async def update(self, current_user: dict, item_id: int, data: WorkTeamCreate) -> WorkTeam:
        check_role(current_user, [UserRole.ADMIN])
        item = work_teams_table.get(doc_id=item_id)
        if not item:
            raise NotFoundException(detail="责任班组不存在")
        work_teams_table.update(data.model_dump(), doc_ids=[item_id])
        return WorkTeam(id=item_id, **data.model_dump())

    @delete("/{item_id:int}", summary="删除责任班组", status_code=200)
    async def delete(self, current_user: dict, item_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN])
        work_teams_table.remove(doc_ids=[item_id])
        return {"message": "删除成功"}


class QcStandardController(Controller):
    path = "/qc-standards"
    tags = ["质检标准"]
    dependencies = {"current_user": Provide(get_current_user)}

    @get("/", summary="获取质检标准列表")
    async def list(self, current_user: dict) -> List[QcStandard]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        items = qc_standards_table.all()
        return [QcStandard(id=item.doc_id, **item) for item in items]

    @post("/", summary="创建质检标准")
    async def create(self, current_user: dict, data: QcStandardCreate) -> QcStandard:
        check_role(current_user, [UserRole.ADMIN])
        item_id = qc_standards_table.insert(data.model_dump())
        return QcStandard(id=item_id, **data.model_dump())

    @put("/{item_id:int}", summary="更新质检标准")
    async def update(self, current_user: dict, item_id: int, data: QcStandardCreate) -> QcStandard:
        check_role(current_user, [UserRole.ADMIN])
        item = qc_standards_table.get(doc_id=item_id)
        if not item:
            raise NotFoundException(detail="质检标准不存在")
        qc_standards_table.update(data.model_dump(), doc_ids=[item_id])
        return QcStandard(id=item_id, **data.model_dump())

    @delete("/{item_id:int}", summary="删除质检标准", status_code=200)
    async def delete(self, current_user: dict, item_id: int) -> dict:
        check_role(current_user, [UserRole.ADMIN])
        qc_standards_table.remove(doc_ids=[item_id])
        return {"message": "删除成功"}


admin_router_controllers = [
    CustomerController,
    ClothCategoryController,
    WashingLineController,
    BatchRuleController,
    WorkTeamController,
    QcStandardController
]
