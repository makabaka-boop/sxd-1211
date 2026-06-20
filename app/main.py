from litestar import Litestar
from litestar.config.cors import CORSConfig

from app.auth import init_default_users
from app.routers.auth_router import auth_router
from app.routers.admin_router import admin_router_controllers
from app.routers.sorter_router import sorter_router_controllers
from app.routers.inspector_router import inspector_router_controllers
from app.routers.stats_router import stats_router_controllers


cors_config = CORSConfig(
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_app() -> Litestar:
    init_default_users()

    all_controllers = (
        admin_router_controllers +
        sorter_router_controllers +
        inspector_router_controllers +
        stats_router_controllers
    )

    app = Litestar(
        route_handlers=[auth_router] + all_controllers,
        cors_config=cors_config,
        debug=True,
    )

    return app


app = create_app()
