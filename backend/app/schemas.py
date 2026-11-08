"""요청 스키마. 업무 검증 메시지는 서비스가 소유하고, 여기서는 타입·길이만 제한한다."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

S20 = Optional[str]


def Str(n: int):
    return Field(default=None, max_length=n)


class In(BaseModel):
    model_config = ConfigDict(extra="ignore")

    def given(self) -> dict:
        return self.model_dump(exclude_unset=True)


class LoginIn(In):
    emp_no: str = Field(default="", max_length=50)
    password: str = Field(default="", max_length=200)


class OtpIn(In):
    code: str = Field(default="", max_length=10)


class MemberIn(In):
    last_name: Optional[str] = Str(50)
    first_name: Optional[str] = Str(50)
    birth_date: Optional[str] = Str(20)
    email: Optional[str] = Str(100)
    phone: Optional[str] = Str(20)
    emp_no: Optional[str] = Str(50)
    password: Optional[str] = Str(200)
    password_confirm: Optional[str] = Str(200)


class UserIn(MemberIn):
    status: Optional[str] = Str(20)
    groups: Optional[list[str]] = None
    totp_enabled: Optional[bool] = None


class ApproveIn(In):
    groups: list[str] = Field(default_factory=list)


class MenuAccessIn(In):
    menu_id: str = Field(max_length=20)


class HullIn(In):
    hull_no: Optional[str] = Str(50)
    hull_nm: Optional[str] = Str(100)
    ship_type: Optional[str] = Str(20)
    hull_status: Optional[str] = Str(20)
    owner_nm: Optional[str] = Str(100)
    class_society: Optional[str] = Str(50)
    length_m: Optional[float] = None
    breadth_m: Optional[float] = None
    depth_m: Optional[float] = None
    dead_weight: Optional[float] = None
    dock_no: Optional[str] = Str(50)
    contract_dt: Optional[str] = Str(20)
    delivery_dt: Optional[str] = Str(20)
    remark: Optional[str] = Str(500)
    use_yn: Optional[bool] = None


class MilestoneItem(In):
    milestone_cd: Optional[str] = Str(20)
    plan_dt: Optional[str] = Str(20)
    actual_dt: Optional[str] = Str(20)
    remark: Optional[str] = Str(500)


class MilestonesIn(In):
    items: list[MilestoneItem] = Field(default_factory=list)


class BlockIn(In):
    block_cd: Optional[str] = Str(20)
    block_nm: Optional[str] = Str(100)
    block_type: Optional[str] = Str(20)
    parent_block_id: Optional[int] = None
    weight_ton: Optional[float] = None
    use_yn: Optional[bool] = None


class PlanIn(In):
    block_id: Optional[int] = None
    proc_cd: Optional[str] = Str(20)
    plan_start_dt: Optional[str] = Str(20)
    plan_end_dt: Optional[str] = Str(20)
    manager_emp_no: Optional[str] = Str(50)
    remark: Optional[str] = Str(1000)
    pred_plan_ids: Optional[list[int]] = None
    confirm_late_preds: bool = False


class PredsIn(In):
    pred_plan_ids: list[int] = Field(default_factory=list)
    confirm_late_preds: bool = False


class LinkDrawingIn(In):
    drawing_id: Optional[int] = None
    required: bool = True


class LinkPlanIn(In):
    plan_id: Optional[int] = None
    required: bool = True


class ProgressIn(In):
    progress_rate: Optional[float] = None
    man_hour: Optional[float] = None
    worker_cnt: Optional[int] = None
    worker_emp_no: Optional[str] = Str(50)
    remark: Optional[str] = Str(1000)


class DrawingIn(In):
    drawing_no: Optional[str] = Str(50)
    drawing_nm: Optional[str] = Str(200)
    hull_no: Optional[str] = Str(50)
    block_id: Optional[int] = None
    discipline: Optional[str] = Str(20)
    designer_emp_no: Optional[str] = Str(50)


class RevisionIn(In):
    change_desc: Optional[str] = Str(1000)


class ApprovalRequestIn(In):
    reviewer_emp_no: Optional[str] = Str(50)
    approver_emp_no: Optional[str] = Str(50)


class DecisionIn(In):
    result: Optional[str] = Str(20)
    comment: Optional[str] = Str(1000)
