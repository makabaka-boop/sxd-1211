from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    SORTER = "sorter"
    INSPECTOR = "inspector"


class ClothStatus(str, Enum):
    PENDING_SORT = "待分拣"
    WASHING = "清洗中"
    PENDING_QC = "待质检"
    REWASHING = "补洗中"
    READY_FOR_DELIVERY = "可出厂"
    HOLD_DELIVERY = "暂停出厂"


class StainLevel(str, Enum):
    LIGHT = "轻"
    MEDIUM = "中"
    HEAVY = "重"


class DamageLevel(str, Enum):
    NONE = "无"
    MINOR = "轻微"
    MODERATE = "中度"
    SEVERE = "严重"


class CleanlinessLevel(str, Enum):
    EXCELLENT = "优"
    GOOD = "良"
    FAIR = "中"
    POOR = "差"


class DeliverySuggestion(str, Enum):
    APPROVE = "同意出厂"
    REWASH = "补洗"
    HOLD = "暂停出厂"


class UserBase(BaseModel):
    username: str
    role: UserRole
    full_name: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: User


class CustomerBase(BaseModel):
    name: str
    contact: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class Customer(CustomerBase):
    id: int


class ClothCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None


class ClothCategoryCreate(ClothCategoryBase):
    pass


class ClothCategory(ClothCategoryBase):
    id: int


class WashingLineBase(BaseModel):
    name: str
    description: Optional[str] = None
    capacity: Optional[int] = None


class WashingLineCreate(WashingLineBase):
    pass


class WashingLine(WashingLineBase):
    id: int


class BatchRuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    min_quantity: Optional[int] = None
    max_quantity: Optional[int] = None


class BatchRuleCreate(BatchRuleBase):
    pass


class BatchRule(BatchRuleBase):
    id: int


class WorkTeamBase(BaseModel):
    name: str
    leader: Optional[str] = None
    description: Optional[str] = None


class WorkTeamCreate(WorkTeamBase):
    pass


class WorkTeam(WorkTeamBase):
    id: int


class QcStandardBase(BaseModel):
    name: str
    description: Optional[str] = None
    cleanliness_requirement: Optional[str] = None
    damage_tolerance: Optional[str] = None


class QcStandardCreate(QcStandardBase):
    pass


class QcStandard(QcStandardBase):
    id: int


class ClothRecordCreate(BaseModel):
    customer_id: int
    category_id: int
    batch_no: str
    quantity: int
    stain_level: StainLevel
    damage_description: Optional[str] = None
    remark: Optional[str] = None


class ClothRecordUpdate(BaseModel):
    quantity: Optional[int] = None
    stain_level: Optional[StainLevel] = None
    damage_description: Optional[str] = None
    remark: Optional[str] = None


class ClothRecord(BaseModel):
    id: int
    customer_id: int
    category_id: int
    batch_no: str
    quantity: int
    stain_level: StainLevel
    status: ClothStatus
    damage_description: Optional[str] = None
    remark: Optional[str] = None
    sorter_id: Optional[int] = None
    washing_line_id: Optional[int] = None
    work_team_id: Optional[int] = None
    created_at: str
    updated_at: str
    sorted_at: Optional[str] = None
    qc_at: Optional[str] = None


class SortingRecordCreate(BaseModel):
    cloth_record_id: int
    washing_line_id: int
    work_team_id: int
    sorter_remark: Optional[str] = None


class QcRecordCreate(BaseModel):
    cloth_record_id: int
    cleanliness: CleanlinessLevel
    damage_recheck: DamageLevel
    rewash_conclusion: Optional[bool] = False
    delivery_suggestion: DeliverySuggestion
    qc_remark: Optional[str] = None


class QcRecord(BaseModel):
    id: int
    cloth_record_id: int
    inspector_id: int
    cleanliness: CleanlinessLevel
    damage_recheck: DamageLevel
    rewash_conclusion: bool
    delivery_suggestion: DeliverySuggestion
    qc_remark: Optional[str] = None
    created_at: str


class RewashRecordCreate(BaseModel):
    cloth_record_id: int
    reason: str
    rewash_count: Optional[int] = 1


class RewashRecord(BaseModel):
    id: int
    cloth_record_id: int
    reason: str
    rewash_count: int
    created_at: str


class ClothRecordFilter(BaseModel):
    customer_id: Optional[int] = None
    category_id: Optional[int] = None
    washing_line_id: Optional[int] = None
    work_team_id: Optional[int] = None
    status: Optional[ClothStatus] = None
    stain_level: Optional[StainLevel] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
