from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), default="user")
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scans: Mapped[list["CTScan"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class CTScan(Base):
    __tablename__ = "ct_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_name: Mapped[str] = mapped_column(String(512))
    file_path: Mapped[str] = mapped_column(String(1024))
    upload_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    owner: Mapped[User] = relationship(back_populates="scans")
    detections: Mapped[list["DetectionResult"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    reports: Mapped[list["ClinicalReport"]] = relationship(back_populates="scan", cascade="all, delete-orphan")


class DetectionResult(Base):
    __tablename__ = "detection_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("ct_scans.id"), index=True)
    confidence_score: Mapped[float] = mapped_column(Float)
    lesion_size: Mapped[float] = mapped_column(Float, nullable=True)
    created_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    boxes_text: Mapped[str] = mapped_column(Text)

    scan: Mapped[CTScan] = relationship(back_populates="detections")


class ClinicalReport(Base):
    __tablename__ = "clinical_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("ct_scans.id"), index=True)
    report_text: Mapped[str] = mapped_column(Text)
    created_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scan: Mapped[CTScan] = relationship(back_populates="reports")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=True)
    meta_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
