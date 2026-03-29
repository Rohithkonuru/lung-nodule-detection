from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class ScanOut(BaseModel):
    id: int
    file_name: str
    upload_date: datetime | None = None
    status: str = "uploaded"
    nodule_count: int = 0
    has_report: bool = False


class AnalyzeResponse(BaseModel):
    id: int
    scan_id: int
    num_detections: int
    confidence_score: float
    avg_size_mm: float
    detections: list[dict]
    runtime: float


class ReportResponse(BaseModel):
    id: int
    scan_id: int
    report_text: str
    created_date: datetime | None = None
