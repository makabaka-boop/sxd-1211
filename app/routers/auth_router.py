from litestar import Router, post, get, Request
from litestar.controller import Controller
from litestar.exceptions import NotAuthorizedException, NotFoundException
from litestar.di import Provide
from datetime import timedelta
from app.auth import authenticate_user, create_access_token, get_user_by_username, get_password_hash, users_table, UserQuery, get_current_user
from app.schemas import User, UserCreate, Token, UserRole
from app.config import settings
from typing import List


class AuthController(Controller):
    path = "/auth"
    tags = ["认证"]

    @post("/login", summary="用户登录")
    async def login(self, data: dict) -> Token:
        username = data.get("username")
        password = data.get("password")
        if not username or not password:
            raise NotAuthorizedException(detail="请输入用户名和密码")

        user = authenticate_user(username, password)
        if not user:
            raise NotAuthorizedException(detail="用户名或密码错误")

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"], "role": user["role"]},
            expires_delta=access_token_expires
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            user=User(
                id=user.doc_id,
                username=user["username"],
                role=user["role"],
                full_name=user["full_name"]
            )
        )

    @get("/me", summary="获取当前用户信息", dependencies={"current_user": Provide(get_current_user)})
    async def get_me(self, current_user: dict) -> User:
        return User(**current_user)


class UserController(Controller):
    path = "/users"
    tags = ["用户管理"]
    dependencies = {"current_user": Provide(get_current_user)}

    @get("/", summary="获取用户列表")
    async def list_users(self, current_user: dict) -> List[User]:
        if current_user["role"] != UserRole.ADMIN:
            raise NotAuthorizedException(detail="权限不足")
        users = users_table.all()
        return [User(
            id=u.doc_id,
            username=u["username"],
            role=u["role"],
            full_name=u["full_name"]
        ) for u in users]

    @post("/", summary="创建用户")
    async def create_user(self, current_user: dict, data: UserCreate) -> User:
        if current_user["role"] != UserRole.ADMIN:
            raise NotAuthorizedException(detail="权限不足")
        existing = get_user_by_username(data.username)
        if existing:
            raise ValueError(f"用户名 {data.username} 已存在")

        user_id = users_table.insert({
            "username": data.username,
            "hashed_password": get_password_hash(data.password),
            "role": data.role,
            "full_name": data.full_name
        })

        return User(
            id=user_id,
            username=data.username,
            role=data.role,
            full_name=data.full_name
        )


auth_router = Router(path="", route_handlers=[AuthController, UserController])
