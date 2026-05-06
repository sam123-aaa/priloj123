import json
from datetime import datetime
from enum import Enum
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from audit import log_transaction
from events import publish_domain_event
from orm_models import EquipmentComponent, Fault, MaintenancePlan, MaintenanceRecommendation, MaintenanceTask
from queue_app import celery_app
from rbac import require_owner_or_admin
from services.cache import invalidate_read_cache
from task_status import set_task_status


class MaintenanceTaskStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


ALLOWED_TASK_TRANSITIONS = {
    MaintenanceTaskStatus.CREATED: {MaintenanceTaskStatus.ACTIVE},
    MaintenanceTaskStatus.ACTIVE: {
        MaintenanceTaskStatus.COMPLETED,
        MaintenanceTaskStatus.CANCELLED,
    },
    MaintenanceTaskStatus.COMPLETED: set(),
    MaintenanceTaskStatus.CANCELLED: set(),
}


class EntityNotFoundError(Exception):
    pass


class InvalidStatusTransitionError(Exception):
    pass


def _require_owner_or_admin_with_audit(conn, user, owner_id, endpoint, resource_type, resource_id):
    try:
        require_owner_or_admin(user, owner_id)
    except HTTPException:
        log_transaction(
            conn,
            action="security_idor_denied",
            endpoint=endpoint,
            user_id=user.get("user_id"),
            role_code=user.get("role_code"),
            details={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "owner_id": owner_id,
            },
        )
        conn.commit()
        raise


def create_plan_with_tasks(session: Session, recommendation_ids, planned_date, user):
    plan_ids = []
    task_ids = []
    missing_recommendations = []

    with session.begin():
        recommendations = session.scalars(
            select(MaintenanceRecommendation)
            .options(
                joinedload(MaintenanceRecommendation.fault),
                selectinload(MaintenanceRecommendation.plans),
            )
            .where(MaintenanceRecommendation.id.in_(recommendation_ids))
        ).all()
        recommendations_by_id = {item.id: item for item in recommendations}

        for recommendation_id in recommendation_ids:
            recommendation = recommendations_by_id.get(recommendation_id)
            if not recommendation:
                missing_recommendations.append(recommendation_id)
                continue

            require_owner_or_admin(user, recommendation.owner_id)
            fault = recommendation.fault
            if not fault:
                missing_recommendations.append(recommendation_id)
                continue

            component = session.get(EquipmentComponent, fault.component_id)
            if not component:
                missing_recommendations.append(recommendation_id)
                continue

            plan = MaintenancePlan(
                recommendation_id=recommendation_id,
                equipment_id=component.equipment_id,
                planned_date=planned_date,
                created_by=user["user_id"],
                owner_id=user["user_id"],
                status="created",
            )
            task = MaintenanceTask(
                description=recommendation.recommendation_text,
                status=MaintenanceTaskStatus.CREATED.value,
                owner_id=user["user_id"],
            )
            plan.tasks.append(task)
            session.add(plan)
            session.flush()

            publish_domain_event(
                session,
                event_type="maintenance_plan_created",
                aggregate_type="maintenance_plan",
                aggregate_id=plan.id,
                payload={
                    "plan_id": plan.id,
                    "task_id": task.id,
                    "recommendation_id": recommendation_id,
                    "owner_id": user["user_id"],
                },
            )
            plan_ids.append(plan.id)
            task_ids.append(task.id)

        if not plan_ids:
            raise EntityNotFoundError(
                "План не создан: рекомендации не найдены, не связаны с оборудованием или недоступны"
            )

    invalidate_read_cache()
    return {
        "status": "plan created",
        "plan_ids": plan_ids,
        "task_ids": task_ids,
        "missing_recommendation_ids": missing_recommendations,
    }


def transition_task_status(session: Session, task_id, target_status, user, result=None):
    with session.begin():
        task = session.get(
            MaintenanceTask,
            task_id,
            options=(joinedload(MaintenanceTask.plan),),
        )
        if not task:
            raise EntityNotFoundError("Задача не найдена")

        current_status = MaintenanceTaskStatus(task.status)
        next_status = MaintenanceTaskStatus(target_status)
        can_claim_unassigned_task = (
            user["role_code"] == "mechanic"
            and current_status == MaintenanceTaskStatus.CREATED
            and next_status == MaintenanceTaskStatus.ACTIVE
            and task.mechanic_id is None
        )
        if not can_claim_unassigned_task:
            require_owner_or_admin(user, task.owner_id)
        if next_status not in ALLOWED_TASK_TRANSITIONS[current_status]:
            raise InvalidStatusTransitionError(
                f"Недопустимый переход: {current_status.value} -> {next_status.value}"
            )

        if next_status == MaintenanceTaskStatus.ACTIVE:
            task.mechanic_id = user["user_id"]
            task.owner_id = user["user_id"]
            task.start_time = datetime.utcnow()
            task.status = next_status.value
        elif next_status == MaintenanceTaskStatus.COMPLETED:
            if task.mechanic_id != user["user_id"]:
                raise EntityNotFoundError("Задача недоступна для этого механика")
            task.end_time = datetime.utcnow()
            task.result = result
            task.status = next_status.value
            publish_domain_event(
                session,
                event_type="maintenance_task_completed",
                aggregate_type="maintenance_task",
                aggregate_id=task.id,
                payload={
                    "task_id": task.id,
                    "plan_id": task.plan_id,
                    "owner_id": task.owner_id,
                    "result": result,
                },
            )
        else:
            if task.mechanic_id != user["user_id"]:
                raise EntityNotFoundError("Задача недоступна для этого механика")
            task.end_time = datetime.utcnow()
            task.status = next_status.value

        session.flush()
        result_payload = {
            "id": task.id,
            "plan_id": task.plan_id,
            "mechanic_id": task.mechanic_id,
            "description": task.description,
            "start_time": task.start_time,
            "end_time": task.end_time,
            "result": task.result,
            "status": task.status,
        }
        invalidate_read_cache()
        return result_payload


def enqueue_report(conn, report_type: str, user: dict, delay_seconds: int = 0):
    job_id = str(uuid4())
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO background_jobs (id, job_type, status, owner_id, payload)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        """,
        (
            job_id,
            "report_generation",
            "queued",
            user["user_id"],
            json.dumps({"report_type": report_type}, ensure_ascii=False),
        ),
    )
    cur.execute(
        """
        INSERT INTO reports (report_type, created_by, owner_id, data)
        VALUES (%s, %s, %s, %s::jsonb)
        """,
        (
            report_type,
            user["user_id"],
            user["user_id"],
            json.dumps({"job_id": job_id, "status": "queued"}, ensure_ascii=False),
        ),
    )
    cur.execute(
        """
        INSERT INTO report_read_model (job_id, owner_id, report_type, status)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (job_id) DO UPDATE
        SET status = EXCLUDED.status, report_type = EXCLUDED.report_type, owner_id = EXCLUDED.owner_id
        """,
        (job_id, user["user_id"], report_type, "queued"),
    )
    cur.execute(
        """
        INSERT INTO domain_events (event_type, aggregate_type, aggregate_id, payload, status)
        VALUES (%s, %s, %s, %s::jsonb, %s)
        """,
        (
            "report_requested",
            "report_job",
            job_id,
            json.dumps(
                {
                    "job_id": job_id,
                    "report_type": report_type,
                    "owner_id": user["user_id"],
                    "delay_seconds": delay_seconds,
                },
                ensure_ascii=False,
            ),
            "pending",
        ),
    )

    set_task_status(job_id, "queued", {"report_type": report_type})
    log_transaction(
        conn,
        action="report_enqueued",
        endpoint="/reports/generate",
        user_id=user["user_id"],
        role_code=user["role_code"],
        details={"task_id": job_id, "report_type": report_type, "delay_seconds": delay_seconds},
    )
    conn.commit()
    invalidate_read_cache()

    if celery_app is None:
        raise RuntimeError("Celery is not installed")

    celery_app.send_task(
        "workers.generate_report",
        kwargs={"job_id": job_id, "report_type": report_type, "user_id": user["user_id"]},
        countdown=delay_seconds,
    )
    return {"task_id": job_id, "status": "queued"}


def resolve_report_type(conn, report_type: str = None, template_id: int = None):
    if report_type:
        return report_type
    if template_id is None:
        raise HTTPException(status_code=422, detail="Нужно передать report_type или template_id")

    cur = conn.cursor()
    cur.execute(
        """
        SELECT report_type
        FROM report_templates
        WHERE id = %s AND is_active = TRUE
        """,
        (template_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Шаблон отчёта не найден")
    return row["report_type"]


def confirm_faults(conn, fault_ids, action: str, user: dict):
    cur = conn.cursor()
    status = "confirmed" if action == "confirm" else "rejected"

    for fault_id in fault_ids:
        cur.execute("SELECT owner_id FROM faults WHERE id = %s", (fault_id,))
        fault = cur.fetchone()
        if not fault:
            raise HTTPException(status_code=404, detail=f"Неисправность {fault_id} не найдена")
        _require_owner_or_admin_with_audit(conn, user, fault["owner_id"], "/faults/confirm", "fault", fault_id)
        cur.execute(
            """
            UPDATE faults
            SET status = %s, confirmed_by = %s, confirmed_at = NOW()
            WHERE id = %s
            """,
            (status, user["user_id"], fault_id),
        )

    invalidate_read_cache()
    return {"status": "updated", "fault_status": status, "fault_ids": fault_ids}


def create_recommendation(conn, fault_id: int, recommendation_text: str, priority: str, user: dict):
    cur = conn.cursor()
    cur.execute("SELECT id, owner_id FROM faults WHERE id = %s", (fault_id,))
    fault = cur.fetchone()
    if not fault:
        raise HTTPException(status_code=404, detail="Неисправность не найдена")

    _require_owner_or_admin_with_audit(conn, user, fault["owner_id"], "/recommendations", "fault", fault_id)
    cur.execute(
        """
        INSERT INTO maintenance_recommendations (fault_id, recommendation_text, created_by, owner_id, priority)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (fault_id, recommendation_text, user["user_id"], user["user_id"], priority),
    )
    recommendation_id = cur.fetchone()["id"]
    invalidate_read_cache()
    return {"status": "created", "recommendation_id": recommendation_id}


def create_quality_check(conn, task_id: int, status: str, notes: str, user: dict):
    cur = conn.cursor()
    cur.execute("SELECT owner_id FROM maintenance_tasks WHERE id = %s", (task_id,))
    task = cur.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    _require_owner_or_admin_with_audit(conn, user, task["owner_id"], "/quality-checks", "task", task_id)
    cur.execute(
        """
        INSERT INTO quality_checks (task_id, inspector_id, check_date, status, notes, owner_id)
        VALUES (%s, %s, NOW(), %s, %s, %s)
        RETURNING id
        """,
        (task_id, user["user_id"], status, notes, user["user_id"]),
    )
    check_id = cur.fetchone()["id"]
    invalidate_read_cache()
    return {"status": "checked", "check_id": check_id, "task_id": task_id}
