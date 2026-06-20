from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException
from litestar.connection import Request
from app.config import settings
from app.database import users_table, UserQuery
from app.schemas import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def get_user_by_username(username: str) -> Optional[dict]:
    result = users_table.search(UserQuery.username == username)
    if result:
        return result[0]
    return None


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def init_default_users():
    admin = get_user_by_username("admin")
    if not admin:
        users_table.insert({
            "username": "admin",
            "hashed_password": get_password_hash("admin123"),
            "role": UserRole.ADMIN,
            "full_name": "系统管理员"
        })

    sorter = get_user_by_username("sorter")
    if not sorter:
        users_table.insert({
            "username": "sorter",
            "hashed_password": get_password_hash("sorter123"),
            "role": UserRole.SORTER,
            "full_name": "分拣员张三"
        })

    inspector = get_user_by_username("inspector")
    if not inspector:
        users_table.insert({
            "username": "inspector",
            "hashed_password": get_password_hash("inspector123"),
            "role": UserRole.INSPECTOR,
            "full_name": "质检员李四"
        })


async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise NotAuthorizedException(detail="未提供认证令牌")

    if not auth_header.startswith("Bearer "):
        raise NotAuthorizedException(detail="认证令牌格式错误")

    token = auth_header[7:]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise NotAuthorizedException(detail="无效的令牌")
    except JWTError:
        raise NotAuthorizedException(detail="无效的令牌")

    user = get_user_by_username(username)
    if user is None:
        raise NotAuthorizedException(detail="用户不存在")

    return {
        "id": user.doc_id,
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"]
    }


def require_role(roles: list):
    def decorator(request: Request, current_user: dict) -> dict:
        if current_user["role"] not in roles:
            raise PermissionDeniedException(detail="权限不足")
        return current_user
    return decorator
