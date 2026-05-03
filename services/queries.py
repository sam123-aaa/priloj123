from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from orm_models import EquipmentComponent, Fault, MaintenancePlan, MaintenanceRecommendation, MaintenanceTask

DEFAULT_MEASUREMENT_OPTIONS = [
    {"parameter_name": "Люфт", "unit": "мм", "min_value": None, "max_value": None},
    {"parameter_name": "Отклонение температуры", "unit": "C", "min_value": None, "max_value": None},
    {"parameter_name": "Давление", "unit": "бар", "min_value": None, "max_value": None},
    {"parameter_name": "Вибрация", "unit": "мм/с", "min_value": None, "max_value": None},
]


def _ownership_clause(user, alias="owner_id"):
    if user["role_code"] == "admin":
        return "TRUE", []
    return f"{alias} = %s", [user["user_id"]]


def get_faults_for_user(conn, user):
    clause, params = _ownership_clause(user, "f.owner_id")
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT
            f.id,
            f.component_id,
            f.owner_id,
            f.description,
            f.severity,
            f.status,
            f.detected_at,
            e.name AS equipment_name,
            ec.name AS component_name
        FROM faults f
        JOIN equipment_components ec ON ec.id = f.component_id
        JOIN equipment e ON e.id = ec.equipment_id
        WHERE {clause}
        ORDER BY f.id DESC
        """,
        params,
    )
    return cur.fetchall()


def get_tasks_for_mechanic(conn, user):
    cur = conn.cursor()
    if user["role_code"] == "admin":
        cur.execute(
            """
            SELECT
                mt.id,
                mt.plan_id,
                mt.mechanic_id,
                mt.description,
                mt.start_time,
                mt.end_time,
                mt.result,
                mt.status,
                mp.planned_date,
                e.name AS equipment_name
            FROM maintenance_tasks mt
            JOIN maintenance_plan mp ON mt.plan_id = mp.id
            JOIN equipment e ON mp.equipment_id = e.id
            ORDER BY mt.id DESC
            """
        )
    else:
        cur.execute(
            """
            SELECT
                mt.id,
                mt.plan_id,
                mt.mechanic_id,
                mt.description,
                mt.start_time,
                mt.end_time,
                mt.result,
                mt.status,
                mp.planned_date,
                e.name AS equipment_name
            FROM maintenance_tasks mt
            JOIN maintenance_plan mp ON mt.plan_id = mp.id
            JOIN equipment e ON mp.equipment_id = e.id
            WHERE (
                mt.mechanic_id = %s
                OR mt.owner_id = %s
                OR (mt.mechanic_id IS NULL AND mt.status = 'created')
            )
              AND mt.status IN ('created', 'active')
            ORDER BY mt.id DESC
            """,
            (user["user_id"], user["user_id"]),
        )
    return cur.fetchall()


def get_transactions(conn, user, limit: int, user_id=None, action=None):
    if user["role_code"] != "admin":
        raise HTTPException(status_code=403, detail="Просмотр всех транзакций доступен только администратору")

    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_id, role_code, action, endpoint, details, created_at
        FROM transactions
        WHERE (%s IS NULL OR user_id = %s)
          AND (%s IS NULL OR action = %s)
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, user_id, action, action, limit),
    )
    return cur.fetchall()


def get_report_status(conn, task_id: str, user):
    cur = conn.cursor()
    if user["role_code"] == "admin":
        cur.execute(
            """
            SELECT job_id, owner_id, report_type, status, generated_at, payload
            FROM report_read_model
            WHERE job_id = %s
            """,
            (task_id,),
        )
    else:
        cur.execute(
            """
            SELECT job_id, owner_id, report_type, status, generated_at, payload
            FROM report_read_model
            WHERE job_id = %s AND owner_id = %s
            """,
            (task_id, user["user_id"]),
        )
    return cur.fetchone()


def get_recent_report_jobs(conn, user, limit: int = 20):
    cur = conn.cursor()
    if user["role_code"] == "admin":
        cur.execute(
            """
            SELECT
                rrm.job_id,
                rrm.owner_id,
                rrm.report_type,
                rrm.status,
                bj.created_at AS queued_at,
                bj.started_at,
                bj.finished_at,
                rrm.generated_at,
                CASE WHEN rd.job_id IS NULL THEN FALSE ELSE TRUE END AS has_document,
                rrm.payload
            FROM report_read_model rrm
            LEFT JOIN background_jobs bj ON bj.id = rrm.job_id
            LEFT JOIN report_documents rd ON rd.job_id = rrm.job_id
            ORDER BY COALESCE(bj.created_at, rrm.generated_at) DESC NULLS LAST, rrm.job_id DESC
            LIMIT %s
            """,
            (limit,),
        )
    else:
        cur.execute(
            """
            SELECT
                rrm.job_id,
                rrm.owner_id,
                rrm.report_type,
                rrm.status,
                bj.created_at AS queued_at,
                bj.started_at,
                bj.finished_at,
                rrm.generated_at,
                CASE WHEN rd.job_id IS NULL THEN FALSE ELSE TRUE END AS has_document,
                rrm.payload
            FROM report_read_model rrm
            LEFT JOIN background_jobs bj ON bj.id = rrm.job_id
            LEFT JOIN report_documents rd ON rd.job_id = rrm.job_id
            WHERE rrm.owner_id = %s
            ORDER BY COALESCE(bj.created_at, rrm.generated_at) DESC NULLS LAST, rrm.job_id DESC
            LIMIT %s
            """,
            (user["user_id"], limit),
        )
    return cur.fetchall()


def get_report_document(conn, job_id: str, user):
    cur = conn.cursor()
    if user["role_code"] == "admin":
        cur.execute(
            """
            SELECT job_id, owner_id, title, file_name, content_type, html_content, file_content, created_at
            FROM report_documents
            WHERE job_id = %s
            """,
            (job_id,),
        )
    else:
        cur.execute(
            """
            SELECT job_id, owner_id, title, file_name, content_type, html_content, file_content, created_at
            FROM report_documents
            WHERE job_id = %s AND owner_id = %s
            """,
            (job_id, user["user_id"]),
        )
    return cur.fetchone()


def get_web_dashboard(conn, user):
    clause, params = _ownership_clause(user, "mp.owner_id")
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT
            mp.id AS plan_id,
            mp.planned_date,
            e.name AS equipment_name,
            COUNT(mt.id) AS tasks_total,
            COUNT(mt.id) FILTER (WHERE mt.status = 'completed') AS tasks_completed
        FROM maintenance_plan mp
        JOIN equipment e ON e.id = mp.equipment_id
        LEFT JOIN maintenance_tasks mt ON mt.plan_id = mp.id
        WHERE {clause}
        GROUP BY mp.id, mp.planned_date, e.name
        ORDER BY mp.planned_date DESC, mp.id DESC
        """,
        params,
    )
    return cur.fetchall()


def get_mobile_tasks(conn, user):
    cur = conn.cursor()
    if user["role_code"] == "admin":
        cur.execute(
            """
            SELECT
                mt.id AS task_id,
                mt.description,
                mt.status,
                mp.planned_date,
                e.name AS equipment_name
            FROM maintenance_tasks mt
            JOIN maintenance_plan mp ON mp.id = mt.plan_id
            JOIN equipment e ON e.id = mp.equipment_id
            ORDER BY mp.planned_date, mt.id
            """
        )
    else:
        cur.execute(
            """
            SELECT
                mt.id AS task_id,
                mt.description,
                mt.status,
                mp.planned_date,
                e.name AS equipment_name
            FROM maintenance_tasks mt
            JOIN maintenance_plan mp ON mp.id = mt.plan_id
            JOIN equipment e ON e.id = mp.equipment_id
            WHERE (
                mt.owner_id = %s
                OR mt.mechanic_id = %s
                OR (mt.mechanic_id IS NULL AND mt.status = 'created')
            )
              AND mt.status IN ('created', 'active')
            ORDER BY mp.planned_date, mt.id
            """,
            (user["user_id"], user["user_id"]),
        )
    return cur.fetchall()


def get_measurement_components(conn, user):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            ec.id AS component_id,
            ec.name AS component_name,
            e.id AS equipment_id,
            e.name AS equipment_name
        FROM equipment_components ec
        JOIN equipment e ON e.id = ec.equipment_id
        ORDER BY e.name, ec.name, ec.id
        """
    )
    rows = cur.fetchall()
    if not rows:
        return rows

    component_ids = [row["component_id"] for row in rows]
    cur.execute(
        """
        SELECT component_id, parameter_name, min_value, max_value
        FROM operation_norms
        WHERE component_id = ANY(%s)
        ORDER BY component_id, parameter_name
        """,
        (component_ids,),
    )
    norm_rows = cur.fetchall()
    options_by_component = {component_id: [dict(item) for item in DEFAULT_MEASUREMENT_OPTIONS] for component_id in component_ids}
    for norm in norm_rows:
        option = {
            "parameter_name": norm["parameter_name"],
            "unit": _default_measurement_unit(norm["parameter_name"]),
            "min_value": norm["min_value"],
            "max_value": norm["max_value"],
        }
        options = options_by_component.setdefault(norm["component_id"], [])
        existing_index = next(
            (
                index
                for index, item in enumerate(options)
                if item["parameter_name"].lower() == option["parameter_name"].lower()
            ),
            None,
        )
        if existing_index is None:
            options.append(option)
        else:
            options[existing_index] = option

    for row in rows:
        row["measurement_options"] = options_by_component.get(row["component_id"], DEFAULT_MEASUREMENT_OPTIONS)
    return rows


def _default_measurement_unit(parameter_name):
    value = (parameter_name or "").lower()
    if "темпера" in value or "temperature" in value:
        return "C"
    if "давлен" in value or "pressure" in value:
        return "бар"
    if "люфт" in value or "gap" in value or "зазор" in value:
        return "мм"
    if "вибрац" in value or "vibration" in value:
        return "мм/с"
    return "ед."


def get_quality_tasks(session: Session, user):
    stmt = (
        select(MaintenanceTask)
        .options(
            joinedload(MaintenanceTask.plan).joinedload(MaintenancePlan.equipment),
            selectinload(MaintenanceTask.quality_checks),
        )
        .where(
            MaintenanceTask.end_time.is_not(None),
            ~MaintenanceTask.quality_checks.any(),
        )
        .order_by(MaintenanceTask.end_time.desc(), MaintenanceTask.id.desc())
    )
    if user["role_code"] != "admin":
        stmt = stmt.where(MaintenanceTask.owner_id == user["user_id"])

    rows = session.scalars(stmt).all()
    return [
        {
            "task_id": task.id,
            "description": task.description,
            "status": task.status,
            "result": task.result,
            "end_time": task.end_time,
            "equipment_name": task.plan.equipment.name if task.plan and task.plan.equipment else None,
        }
        for task in rows
    ]


def get_desktop_monitoring(conn, user):
    clause, params = _ownership_clause(user, "f.owner_id")
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT
            f.id AS fault_id,
            e.name AS equipment_name,
            f.severity,
            f.status,
            f.detected_at
        FROM faults f
        JOIN equipment_components ec ON ec.id = f.component_id
        JOIN equipment e ON e.id = ec.equipment_id
        WHERE {clause}
        ORDER BY f.detected_at DESC, f.id DESC
        """,
        params,
    )
    return cur.fetchall()


def get_report_templates(conn, user):
    if user["role_code"] not in {"manager", "admin"}:
        raise HTTPException(status_code=403, detail="Шаблоны отчётов доступны только менеджеру")

    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, template_name, report_type, description, default_payload
        FROM report_templates
        WHERE is_active = TRUE
        ORDER BY id
        """
    )
    return cur.fetchall()


def get_dispatcher_recommendations(session: Session, user):
    stmt = (
        select(MaintenanceRecommendation)
        .options(
            joinedload(MaintenanceRecommendation.fault)
            .joinedload(Fault.component)
            .joinedload(EquipmentComponent.equipment)
        )
        .order_by(MaintenanceRecommendation.id.desc())
    )
    if user["role_code"] != "admin":
        stmt = stmt.where(MaintenanceRecommendation.owner_id == user["user_id"])

    rows = session.scalars(stmt).all()
    return [
        {
            "recommendation_id": recommendation.id,
            "recommendation_text": recommendation.recommendation_text,
            "priority": recommendation.priority,
            "owner_id": recommendation.owner_id,
            "fault_id": recommendation.fault.id if recommendation.fault else None,
            "fault_status": recommendation.fault.status if recommendation.fault else None,
            "equipment_name": (
                recommendation.fault.component.equipment.name
                if recommendation.fault and recommendation.fault.component and recommendation.fault.component.equipment
                else None
            ),
        }
        for recommendation in rows
    ]
