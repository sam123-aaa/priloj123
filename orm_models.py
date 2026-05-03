from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    role_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(Text)
    endpoint: Mapped[str] = mapped_column(Text)
    details: Mapped[Dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DomainEvent(Base):
    __tablename__ = "domain_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String)
    aggregate_type: Mapped[str] = mapped_column(String)
    aggregate_id: Mapped[str] = mapped_column(String)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Fault(Base):
    __tablename__ = "faults"

    id: Mapped[int] = mapped_column(primary_key=True)
    component_id: Mapped[int] = mapped_column(ForeignKey("equipment_components.id"))
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    component: Mapped["EquipmentComponent"] = relationship(back_populates="faults", lazy="joined")
    recommendations: Mapped[List["MaintenanceRecommendation"]] = relationship(
        back_populates="fault",
        lazy="selectin",
    )


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    components: Mapped[List["EquipmentComponent"]] = relationship(back_populates="equipment", lazy="select")


class EquipmentComponent(Base):
    __tablename__ = "equipment_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"))
    name: Mapped[str] = mapped_column(String)
    equipment: Mapped["Equipment"] = relationship(back_populates="components", lazy="joined")
    faults: Mapped[List["Fault"]] = relationship(back_populates="component", lazy="select")


class MaintenanceRecommendation(Base):
    __tablename__ = "maintenance_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    fault_id: Mapped[int] = mapped_column(ForeignKey("faults.id"))
    recommendation_text: Mapped[str] = mapped_column(Text)
    priority: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fault: Mapped["Fault"] = relationship(back_populates="recommendations", lazy="joined")
    plans: Mapped[List["MaintenancePlan"]] = relationship(back_populates="recommendation", lazy="select")


class MaintenancePlan(Base):
    __tablename__ = "maintenance_plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("maintenance_recommendations.id"))
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"))
    planned_date: Mapped[date] = mapped_column(Date)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    equipment: Mapped["Equipment"] = relationship(lazy="joined")
    recommendation: Mapped["MaintenanceRecommendation"] = relationship(back_populates="plans", lazy="joined")
    tasks: Mapped[List["MaintenanceTask"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MaintenanceTask(Base):
    __tablename__ = "maintenance_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("maintenance_plan.id"))
    mechanic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    plan: Mapped["MaintenancePlan"] = relationship(back_populates="tasks", lazy="joined")
    quality_checks: Mapped[List["QualityCheck"]] = relationship(back_populates="task", lazy="selectin")


class QualityCheck(Base):
    __tablename__ = "quality_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("maintenance_tasks.id"))
    inspector_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task: Mapped["MaintenanceTask"] = relationship(back_populates="quality_checks", lazy="joined")
