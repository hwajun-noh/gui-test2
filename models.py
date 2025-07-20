from pydantic import BaseModel
from typing import Optional, List

class SignupData(BaseModel):
    name: str
    password: str
    role: str = "manager"  # 기본값은 'manager'
    contact: str

class LoginData(BaseModel):
    name: str
    password: str

class ReAdRowData(BaseModel):
    id: Optional[int] = None
    주소: str
    호: str
    층: str
    보증금_월세: str
    관리비_만원: str
    권리금: str
    현업종: str
    평수: str
    방화장실갯수: str
    연락처: str
    타입: str
    주차대수: str
    용도: str
    매물번호: str
    사용승인일: str
    메모: str
    담당자: str
    사진경로: str
    소유자명: str
    소유자관계: str
    광고종료일: str

class SearchFilter(BaseModel):
    dongs: List[str] = []
    rectangles: List[List[float]] = []
    deposit_min: int = 0
    deposit_max: int = 99999999
    monthly_min: int = 0
    monthly_max: int = 99999999
    pyeong_min: float = 0.0
    pyeong_max: float = 99999999.0
    floor_min: int = 1

class CopyItem(BaseModel):
    id: int
    source: str
    memo: Optional[str] = None

class CopyToMyListPayload(BaseModel):
    items: List[CopyItem]
    manager: str = "관리자"

class CompletedItem(BaseModel):
    id: int
    source: str
    status: str = "계약완료"
    memo: Optional[str] = ""

class CompletedDealsPayload(BaseModel):
    items: List[CompletedItem]
    manager: str = "관리자" 