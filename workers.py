import json
import logging
import time
from io import BytesIO
from datetime import datetime
from html import escape
from zipfile import ZIP_DEFLATED, ZipFile

from database import get_db
from queue_app import celery_app
from observability import record_worker_task
from services.cache import invalidate_read_cache
from task_status import set_task_status

logger = logging.getLogger("maintenance.worker")


def _ensure_report_documents_table(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS report_documents (
            job_id UUID PRIMARY KEY REFERENCES report_read_model(job_id) ON DELETE CASCADE,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            file_name TEXT NOT NULL DEFAULT 'report.docx',
            content_type TEXT NOT NULL DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            html_content TEXT NOT NULL,
            file_content BYTEA NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute("ALTER TABLE report_documents ADD COLUMN IF NOT EXISTS file_name TEXT NOT NULL DEFAULT 'report.docx'")
    cur.execute(
        """
        ALTER TABLE report_documents
        ALTER COLUMN content_type
        SET DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        """
    )
    cur.execute("ALTER TABLE report_documents ADD COLUMN IF NOT EXISTS file_content BYTEA NULL")
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_report_documents_owner_id
        ON report_documents(owner_id)
        """
    )


def _docx_paragraph(text: str):
    return f"<w:p><w:r><w:t>{escape(str(text))}</w:t></w:r></w:p>"


def _build_docx_document(job_id: str, report_type: str, user_id: int, generated_at: str):
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {_docx_paragraph(f"Отчёт {report_type}")}
    {_docx_paragraph(f"ID фоновой задачи: {job_id}")}
    {_docx_paragraph(f"Тип отчёта: {report_type}")}
    {_docx_paragraph(f"Сформировал пользователь: {user_id}")}
    {_docx_paragraph(f"Дата формирования UTC: {generated_at}")}
    {_docx_paragraph("Сводка: отчёт сформирован фоновой задачей через Celery + Redis.")}
    {_docx_paragraph("Статус: документ сохранён в read model и доступен менеджеру из web-клиента.")}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
    </w:sectPr>
  </w:body>
</w:document>"""
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as docx:
        docx.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        docx.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        docx.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _build_report_html_preview(job_id: str, report_type: str, user_id: int, generated_at: str):
    title = f"Отчёт {report_type}"
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; color: #1f2340; }}
    .header {{ border-bottom: 3px solid #7770ee; padding-bottom: 16px; margin-bottom: 24px; }}
    h1 {{ margin: 0 0 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 18px; }}
    th, td {{ border: 1px solid #d7d8ef; padding: 10px; text-align: left; }}
    th {{ background: #efefff; }}
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: #e8fff0; color: #126b35; }}
  </style>
</head>
<body>
  <section class="header">
    <h1>{escape(title)}</h1>
    <div class="badge">Сформирован</div>
  </section>
  <p><strong>ID задачи:</strong> {escape(job_id)}</p>
  <p><strong>Тип отчёта:</strong> {escape(report_type)}</p>
  <p><strong>Сформировал пользователь:</strong> {user_id}</p>
  <p><strong>Дата формирования UTC:</strong> {escape(generated_at)}</p>
  <table>
    <thead>
      <tr>
        <th>Раздел</th>
        <th>Содержание</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Сводка</td>
        <td>Отчёт {escape(report_type)} сформирован фоновой задачей через Celery + Redis.</td>
      </tr>
      <tr>
        <td>Статус</td>
        <td>Документ сохранён в read model и доступен менеджеру из web-клиента.</td>
      </tr>
    </tbody>
  </table>
</body>
</html>"""


if celery_app is not None:
    @celery_app.task(bind=True, name="workers.generate_report")
    def generate_report(self, job_id: str, report_type: str, user_id: int):
        started_at = time.perf_counter()
        set_task_status(job_id, "in_progress", {"report_type": report_type, "user_id": user_id})
        logger.info(
            "Starting report generation job_id=%s report_type=%s user_id=%s",
            job_id,
            report_type,
            user_id,
        )

        generated_at = datetime.utcnow().isoformat()
        document_html = _build_report_html_preview(job_id, report_type, user_id, generated_at)
        document_docx = _build_docx_document(job_id, report_type, user_id, generated_at)
        document_file_name = f"report-{report_type}-{job_id}.docx"
        result = {
            "report_type": report_type,
            "generated_at": generated_at,
            "generated_by": user_id,
            "summary": f"Report {report_type} generated asynchronously",
            "document_url": f"/reports/document/{job_id}",
        }

        with get_db() as conn:
            _ensure_report_documents_table(conn)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO report_read_model (job_id, owner_id, report_type, status)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (job_id) DO UPDATE
                SET owner_id = EXCLUDED.owner_id,
                    report_type = EXCLUDED.report_type,
                    status = EXCLUDED.status
                """,
                (job_id, user_id, report_type, "in_progress"),
            )
            cur.execute(
                """
                UPDATE background_jobs
                SET status = %s, started_at = COALESCE(started_at, NOW())
                WHERE id = %s
                """,
                ("in_progress", job_id),
            )
            cur.execute(
                """
                UPDATE report_read_model
                SET status = %s
                WHERE job_id = %s
                """,
                ("in_progress", job_id),
            )

        set_task_status(job_id, "completed", result)

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO report_read_model (job_id, owner_id, report_type, status, generated_at, payload)
                VALUES (%s, %s, %s, %s, NOW(), %s::jsonb)
                ON CONFLICT (job_id) DO UPDATE
                SET owner_id = EXCLUDED.owner_id,
                    report_type = EXCLUDED.report_type,
                    status = EXCLUDED.status,
                    generated_at = EXCLUDED.generated_at,
                    payload = EXCLUDED.payload
                """,
                (job_id, user_id, report_type, "completed", json.dumps(result, ensure_ascii=False)),
            )
            cur.execute(
                """
                UPDATE background_jobs
                SET status = %s, finished_at = NOW(), result = %s::jsonb
                WHERE id = %s
                """,
                ("completed", json.dumps(result, ensure_ascii=False), job_id),
            )
            cur.execute(
                """
                UPDATE report_read_model
                SET status = %s, generated_at = NOW(), payload = %s::jsonb
                WHERE job_id = %s
                """,
                ("completed", json.dumps(result, ensure_ascii=False), job_id),
            )
            cur.execute(
                """
                INSERT INTO report_documents (job_id, owner_id, title, file_name, content_type, html_content, file_content)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO UPDATE
                SET title = EXCLUDED.title,
                    file_name = EXCLUDED.file_name,
                    content_type = EXCLUDED.content_type,
                    html_content = EXCLUDED.html_content,
                    file_content = EXCLUDED.file_content,
                    created_at = NOW()
                """,
                (
                    job_id,
                    user_id,
                    f"Отчёт {report_type}",
                    document_file_name,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    document_html,
                    document_docx,
                ),
            )
            cur.execute(
                """
                UPDATE domain_events
                SET status = %s, processed_at = NOW()
                WHERE aggregate_type = 'report_job' AND aggregate_id::text = %s AND status = 'pending'
                """,
                ("processed", job_id),
            )

        logger.info("Completed report generation job_id=%s", job_id)
        invalidate_read_cache()
        record_worker_task("workers.generate_report", "completed", (time.perf_counter() - started_at) * 1000)
        return result
