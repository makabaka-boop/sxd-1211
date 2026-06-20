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
    detect_missing_delivery_conclusion,
    get_rewash_stats_by_customer,
    get_rewash_stats_by_category,
    get_rewash_stats_by_washing_line,
    get_rewash_stats_by_work_team,
    get_abnormal_rewash_ranking,
    get_rewash_overview_stats
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


class RewashStatsController(Controller):
    path = "/stats/rewash"
    tags = ["补洗统计分析"]
    dependencies = {"current_user": Provide(get_current_user)}

    @get("/overview", summary="补洗概览统计")
    async def rewash_overview(self, current_user: dict) -> dict:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        return get_rewash_overview_stats()

    @get("/by-customer", summary="按客户维度补洗统计")
    async def rewash_by_customer(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        return get_rewash_stats_by_customer()

    @get("/by-category", summary="按布草类别维度补洗统计")
    async def rewash_by_category(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        return get_rewash_stats_by_category()

    @get("/by-washing-line", summary="按清洗线维度补洗统计")
    async def rewash_by_washing_line(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        return get_rewash_stats_by_washing_line()

    @get("/by-work-team", summary="按班组维度补洗统计")
    async def rewash_by_work_team(self, current_user: dict) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        return get_rewash_stats_by_work_team()

    @get("/abnormal-ranking", summary="异常补洗排行")
    async def rewash_abnormal_ranking(self, current_user: dict, top_n: Optional[int] = 10) -> List[dict]:
        check_role(current_user, [UserRole.ADMIN, UserRole.INSPECTOR])
        return get_abnormal_rewash_ranking(top_n)


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


stats_router_controllers = [StatsController, RewashStatsController, AnomalyController]
