from litestar.controller import Controller
from litestar import get, Request
from typing import Optional, List
from litestar.di import Provide
from litestar.exceptions import NotAuthorizedException

from app.auth import get_current_user
from app.schemas import UserRole
from app.services.analytics_service import (
    get_damage_high_risk_categories,
    get_rewash_todo_list,
    get_washing_line_pass_rates,
    get_all_anomalies,
    get_statistics_summary,
    detect_damage_rate_abnormal,
    detect_rewash_backlog,
    detect_qc_timeout,
    detect_washing_line_problems,
    detect_missing_delivery_conclusion
)


def check_role(current_user: dict, allowed_roles: list):
    if current_user["role"] not in allowed_roles:
        raise NotAuthorizedException(detail="权限不足")


class StatsController(Controller):
    path = "/stats"
    tags = ["统计分析"]
    dependencies = {"current_user": Provide(get_current_user)}

    @get("/summary", summary="统计摘要")
    async def stats_summary(self, current_user: dict) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER, UserRole.INSPECTOR])
        return get_statistics_summary()

    @get("/damage-high-risk", summary="破损高发类别")
    async def damage_high_risk(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        return get_damage_high_risk_categories()

    @get("/rewash-todo", summary="补洗待办")
    async def rewash_todo(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER, UserRole.INSPECTOR])
        return get_rewash_todo_list()

    @get("/washing-line-pass-rates", summary="清洗线合格率")
    async def washing_line_pass_rates(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        return get_washing_line_pass_rates()


class AnomalyController(Controller):
    path = "/anomalies"
    tags = ["异常检测"]
    dependencies = {"current_user": Provide(get_current_user)}

    @get("/", summary="所有异常")
    async def all_anomalies(self, current_user: dict) -> dict:
        check_role(current_user, [UserRole.ADMIN])
        return get_all_anomalies()

    @get("/damage-rate", summary="破损率异常")
    async def damage_rate_anomalies(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        return detect_damage_rate_abnormal()

    @get("/rewash-backlog", summary="补洗积压")
    async def rewash_backlog(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.SORTER])
        return detect_rewash_backlog()

    @get("/qc-timeout", summary="质检超期")
    async def qc_timeout(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        return detect_qc_timeout()

    @get("/washing-line-problems", summary="清洗线问题集中")
    async def washing_line_problems(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN])
        return detect_washing_line_problems()

    @get("/missing-delivery", summary="出厂结论缺失")
    async def missing_delivery(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        return detect_missing_delivery_conclusion()


stats_router_controllers = [StatsController, AnomalyController]
