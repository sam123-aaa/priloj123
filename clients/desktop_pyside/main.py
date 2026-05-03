import json
import os
import sys
import webbrowser
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class DesktopWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.token = ""
        self.role = ""
        self.debug_mode = bool(int(os.getenv("CLIENT_DEBUG_UI", "0")))
        self.faults_by_label = {}
        self.recommendations_by_label = {}
        self.templates_by_label = {}
        self.report_jobs_by_label = {}
        self.active_task_id = ""

        self.setWindowTitle("Desktop Client")
        self.resize(1640, 920)
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #171433;
                color: #f4f3ff;
                font-family: Avenir Next;
                font-size: 14px;
            }
            QLabel {
                color: #f4f3ff;
            }
            QLineEdit, QTextEdit, QComboBox {
                background: #19183f;
                border: 1px solid rgba(144,145,219,0.18);
                border-radius: 12px;
                padding: 8px;
                color: #f4f3ff;
            }
            QPushButton {
                background: #8b86ff;
                color: white;
                border: 0;
                border-radius: 14px;
                padding: 10px 14px;
            }
            QPushButton:hover {
                background: #9a96ff;
            }
            """
        )

        central = QWidget()
        root = QVBoxLayout(central)

        auth_row = QHBoxLayout()
        self.api_label = QLabel("API")
        self.api_label.setVisible(self.debug_mode)
        self.api_base = QLineEdit("http://127.0.0.1:8000")
        self.api_base.setVisible(self.debug_mode)
        self.email = QLineEdit("temp-techexpert@example.com")
        self.password = QLineEdit("Expert123!")
        self.password.setEchoMode(QLineEdit.Password)
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.login)

        auth_row.addWidget(self.api_label)
        auth_row.addWidget(self.api_base, 2)
        auth_row.addWidget(self.email, 1)
        auth_row.addWidget(self.password, 1)
        auth_row.addWidget(login_btn)

        self.info = QLabel("Not signed in")
        self.info.setStyleSheet("font-size: 16px; color: #c9c6ff;")

        panels = QHBoxLayout()
        self.monitoring_panel = self._build_monitoring_panel()
        self.expert_panel = self._build_expert_panel()
        self.dispatcher_panel = self._build_dispatcher_panel()
        self.manager_panel = self._build_manager_panel()

        panels.addWidget(self.monitoring_panel, 2)
        panels.addWidget(self.expert_panel, 2)
        panels.addWidget(self.dispatcher_panel, 2)
        panels.addWidget(self.manager_panel, 3)

        root.addLayout(auth_row)
        root.addWidget(self.info)
        root.addLayout(panels)

        self.setCentralWidget(central)
        self._apply_role_visibility()

    def _build_panel_widget(self, title_text, help_text):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        title = QLabel(title_text)
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        help_label = QLabel(help_text)
        help_label.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(help_label)
        return panel, layout

    def _build_monitoring_panel(self):
        panel, layout = self._build_panel_widget(
            "Shared Monitoring",
            "Available for tech expert, dispatcher specialist, and admin.",
        )
        button_row = QHBoxLayout()
        self.load_monitoring_btn = QPushButton("Refresh monitoring")
        self.load_monitoring_btn.clicked.connect(self.load_monitoring)
        button_row.addWidget(self.load_monitoring_btn)
        layout.addLayout(button_row)
        self.monitoring = QTextEdit()
        self.monitoring.setReadOnly(True)
        self.monitoring.setPlainText("Monitoring data will appear here.")
        layout.addWidget(self.monitoring)
        return panel

    def _build_expert_panel(self):
        panel, layout = self._build_panel_widget(
            "Tech Expert",
            "Load faults, confirm them, and create recommendations.",
        )
        form = QFormLayout()
        self.expert_fault = QComboBox()
        self.expert_fault.addItem("Load faults first")
        self.expert_priority = QLineEdit("high")
        self.expert_text = QLineEdit("Inspect the equipment and replace the worn assembly.")
        form.addRow("Fault", self.expert_fault)
        form.addRow("Priority", self.expert_priority)
        form.addRow("Recommendation", self.expert_text)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.load_faults_btn = QPushButton("Load faults")
        self.load_faults_btn.clicked.connect(self.load_faults)
        self.create_recommendation_btn = QPushButton("Create recommendation")
        self.create_recommendation_btn.clicked.connect(self.create_recommendation)
        self.confirm_fault_btn = QPushButton("Confirm fault")
        self.confirm_fault_btn.clicked.connect(self.confirm_fault)
        buttons.addWidget(self.load_faults_btn)
        buttons.addWidget(self.create_recommendation_btn)
        buttons.addWidget(self.confirm_fault_btn)
        layout.addLayout(buttons)

        self.expert_output = QTextEdit()
        self.expert_output.setReadOnly(True)
        self.expert_output.setPlainText("Expert actions will appear here.")
        layout.addWidget(self.expert_output)
        return panel

    def _build_dispatcher_panel(self):
        panel, layout = self._build_panel_widget(
            "Dispatcher Specialist",
            "Load recommendations and create maintenance plans.",
        )
        buttons = QHBoxLayout()
        self.load_recommendations_btn = QPushButton("Load recommendations")
        self.load_recommendations_btn.clicked.connect(self.load_dispatcher_recommendations)
        self.create_plan_btn = QPushButton("Create plan")
        self.create_plan_btn.clicked.connect(self.create_plan)
        buttons.addWidget(self.load_recommendations_btn)
        buttons.addWidget(self.create_plan_btn)
        layout.addLayout(buttons)

        form = QFormLayout()
        self.recommendations = QComboBox()
        self.recommendations.addItem("Load recommendations first")
        self.plan_date = QLineEdit("2026-04-30")
        form.addRow("Recommendation", self.recommendations)
        form.addRow("Planned date", self.plan_date)
        layout.addLayout(form)

        self.dispatcher_output = QTextEdit()
        self.dispatcher_output.setReadOnly(True)
        self.dispatcher_output.setPlainText("Dispatcher actions will appear here.")
        layout.addWidget(self.dispatcher_output)
        return panel

    def _build_manager_panel(self):
        panel, layout = self._build_panel_widget(
            "Manager",
            "Dashboard, templates, report queue, and report document access are available on desktop too.",
        )
        buttons = QHBoxLayout()
        self.load_manager_home_btn = QPushButton("Refresh manager view")
        self.load_manager_home_btn.clicked.connect(self.load_manager_home)
        self.load_templates_btn = QPushButton("Load templates")
        self.load_templates_btn.clicked.connect(self.load_templates)
        self.load_report_jobs_btn = QPushButton("Load reports")
        self.load_report_jobs_btn.clicked.connect(self.load_report_jobs)
        buttons.addWidget(self.load_manager_home_btn)
        buttons.addWidget(self.load_templates_btn)
        buttons.addWidget(self.load_report_jobs_btn)
        layout.addLayout(buttons)

        template_form = QFormLayout()
        self.template_select = QComboBox()
        self.template_select.addItem("Load templates first")
        self.delay_value = QLineEdit("10")
        self.delay_unit = QComboBox()
        self.delay_unit.addItems(["seconds", "minutes", "hours"])
        template_form.addRow("Template", self.template_select)
        template_form.addRow("Delay value", self.delay_value)
        template_form.addRow("Delay unit", self.delay_unit)
        layout.addLayout(template_form)

        report_buttons = QHBoxLayout()
        self.queue_report_btn = QPushButton("Generate now")
        self.queue_report_btn.clicked.connect(self.queue_report_now)
        self.queue_delayed_report_btn = QPushButton("Generate with delay")
        self.queue_delayed_report_btn.clicked.connect(self.queue_report_delayed)
        report_buttons.addWidget(self.queue_report_btn)
        report_buttons.addWidget(self.queue_delayed_report_btn)
        layout.addLayout(report_buttons)

        report_job_form = QFormLayout()
        self.report_job_select = QComboBox()
        self.report_job_select.addItem("Load reports first")
        self.open_report_btn = QPushButton("Open DOCX")
        self.open_report_btn.clicked.connect(self.open_report_document)
        report_job_row = QHBoxLayout()
        report_job_row.addWidget(self.report_job_select, 1)
        report_job_row.addWidget(self.open_report_btn)
        report_job_container = QWidget()
        report_job_container.setLayout(report_job_row)
        report_job_form.addRow("Report jobs", report_job_container)
        layout.addLayout(report_job_form)

        self.manager_dashboard = QTextEdit()
        self.manager_dashboard.setReadOnly(True)
        self.manager_dashboard.setPlainText("Dashboard data will appear here.")
        self.report_jobs_view = QTextEdit()
        self.report_jobs_view.setReadOnly(True)
        self.report_jobs_view.setPlainText("Report job data will appear here.")
        self.manager_output = QTextEdit()
        self.manager_output.setReadOnly(True)
        self.manager_output.setPlainText("Manager actions will appear here.")
        layout.addWidget(self.manager_dashboard)
        layout.addWidget(self.report_jobs_view)
        layout.addWidget(self.manager_output)
        return panel

    def _request(self, path, body=None):
        if path != "/login" and not self.token:
            raise RuntimeError("Login first.")

        payload = json.dumps(body).encode() if body is not None else None
        request = Request(
            f"{self.api_base.text().rstrip('/')}{path}",
            data=payload,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.token}"} if self.token else {}),
            },
            method="POST" if body is not None else "GET",
        )

        try:
            with urlopen(request) as response:
                return json.loads(response.read().decode())
        except HTTPError as exc:
            raw_detail = exc.read().decode()
            try:
                parsed = json.loads(raw_detail)
                detail = parsed.get("detail") or parsed.get("message") or parsed
            except (json.JSONDecodeError, AttributeError):
                detail = raw_detail
            raise RuntimeError(detail or str(exc)) from exc
        except Exception as exc:
            raise RuntimeError(f"Backend is unavailable or returned an error: {exc}") from exc

    def _set_json(self, widget, value, empty_message):
        if not value or (isinstance(value, list) and len(value) == 0):
            widget.setPlainText(empty_message)
            return
        widget.setPlainText(json.dumps(value, ensure_ascii=False, indent=2))

    def _apply_role_visibility(self):
        monitoring_visible = self.role in {"tech_expert", "dispatcher_specialist", "admin"}
        expert_visible = self.role in {"tech_expert", "admin"}
        dispatcher_visible = self.role in {"dispatcher_specialist", "admin"}
        manager_visible = self.role in {"manager", "admin"}

        self.monitoring_panel.setVisible(monitoring_visible)
        self.expert_panel.setVisible(expert_visible)
        self.dispatcher_panel.setVisible(dispatcher_visible)
        self.manager_panel.setVisible(manager_visible)

    def _apply_faults(self, rows):
        self.faults_by_label = {
            (
                f"{item['id']} | {item.get('equipment_name', '')} / "
                f"{item.get('component_name', '')} | {item.get('severity', '')}"
            ): item
            for item in rows
        }
        self.expert_fault.clear()
        labels = list(self.faults_by_label.keys())
        self.expert_fault.addItems(labels or ["No available faults"])

    def _apply_recommendations(self, rows):
        self.recommendations_by_label = {
            (
                f"{item['recommendation_id']} | {item.get('equipment_name', '')} | "
                f"{item.get('priority', '')} | {item.get('recommendation_text', '')}"
            ): item
            for item in rows
        }
        self.recommendations.clear()
        labels = list(self.recommendations_by_label.keys())
        self.recommendations.addItems(labels or ["No available recommendations"])

    def _apply_templates(self, rows):
        self.templates_by_label = {
            (
                f"{item.get('template_name', item.get('report_type', 'template'))} | "
                f"{item.get('report_type', '')} | #{item['id']}"
            ): item
            for item in rows
        }
        self.template_select.clear()
        labels = list(self.templates_by_label.keys())
        self.template_select.addItems(labels or ["No active templates"])

    def _apply_report_jobs(self, rows):
        self.report_jobs_by_label = {
            (
                f"{item.get('report_type', 'report')} | {item.get('status', '')} | "
                f"{item.get('job_id', '')}"
            ): item
            for item in rows
        }
        self.report_job_select.clear()
        labels = list(self.report_jobs_by_label.keys())
        self.report_job_select.addItems(labels or ["No report jobs"])
        self._set_json(self.report_jobs_view, rows, "Report job data will appear here.")

    def selected_fault_id(self):
        item = self.faults_by_label.get(self.expert_fault.currentText())
        if not item:
            raise RuntimeError("Load and select a fault first.")
        return int(item["id"])

    def selected_recommendation_ids(self):
        item = self.recommendations_by_label.get(self.recommendations.currentText())
        if not item:
            raise RuntimeError("Load and select a recommendation first.")
        return [int(item["recommendation_id"])]

    def selected_template_payload(self):
        item = self.templates_by_label.get(self.template_select.currentText())
        if not item:
            raise RuntimeError("Load and select a report template first.")
        return {"template_id": int(item["id"])}

    def selected_delay_seconds(self):
        try:
            value = int(self.delay_value.text())
        except ValueError as exc:
            raise RuntimeError("Delay value must be an integer.") from exc
        if value <= 0:
            raise RuntimeError("Delay value must be greater than 0.")
        multiplier = {"seconds": 1, "minutes": 60, "hours": 3600}[self.delay_unit.currentText()]
        return value * multiplier

    def selected_report_job(self):
        item = self.report_jobs_by_label.get(self.report_job_select.currentText())
        if not item:
            raise RuntimeError("Load report jobs first.")
        return item

    def login(self):
        try:
            result = self._request("/login", {"email": self.email.text(), "password": self.password.text()})
            self.token = result["access_token"]
            self.role = result["role"]
            self.info.setText(f"Role: {self.role}")
            self._apply_role_visibility()
        except Exception as exc:
            QMessageBox.critical(self, "Login error", str(exc))

    def load_monitoring(self):
        try:
            result = self._request("/bff/desktop/monitoring")
            self._set_json(self.monitoring, result, "Monitoring data will appear here.")
        except Exception as exc:
            QMessageBox.critical(self, "Monitoring error", str(exc))

    def load_faults(self):
        try:
            result = self._request("/expert/faults")
            self._apply_faults(result)
            self._set_json(self.expert_output, result, "Expert actions will appear here.")
        except Exception as exc:
            self.expert_output.setPlainText(f"Error: {exc}")

    def create_recommendation(self):
        try:
            result = self._request(
                "/bff/desktop/expert/recommendations",
                {
                    "fault_id": self.selected_fault_id(),
                    "recommendation_text": self.expert_text.text(),
                    "priority": self.expert_priority.text(),
                },
            )
            if result.get("query", {}).get("faults"):
                self._apply_faults(result["query"]["faults"])
            if result.get("query", {}).get("monitoring"):
                self._set_json(self.monitoring, result["query"]["monitoring"], "Monitoring data will appear here.")
            self._set_json(self.expert_output, result, "Expert actions will appear here.")
        except Exception as exc:
            self.expert_output.setPlainText(f"Error: {exc}")

    def confirm_fault(self):
        try:
            result = self._request(
                "/bff/desktop/expert/faults/confirm",
                {
                    "fault_ids": [self.selected_fault_id()],
                    "action": "confirm",
                },
            )
            if result.get("query", {}).get("faults"):
                self._apply_faults(result["query"]["faults"])
            if result.get("query", {}).get("monitoring"):
                self._set_json(self.monitoring, result["query"]["monitoring"], "Monitoring data will appear here.")
            self._set_json(self.expert_output, result, "Expert actions will appear here.")
        except Exception as exc:
            self.expert_output.setPlainText(f"Error: {exc}")

    def load_dispatcher_recommendations(self):
        try:
            result = self._request("/specialist/recommendations")
            self._apply_recommendations(result)
            self._set_json(self.dispatcher_output, result, "Dispatcher actions will appear here.")
        except Exception as exc:
            self.dispatcher_output.setPlainText(f"Error: {exc}")

    def create_plan(self):
        try:
            result = self._request(
                "/bff/desktop/dispatcher/plans",
                {
                    "recommendation_ids": self.selected_recommendation_ids(),
                    "planned_date": self.plan_date.text(),
                },
            )
            if result.get("query", {}).get("recommendations"):
                self._apply_recommendations(result["query"]["recommendations"])
            if result.get("query", {}).get("monitoring"):
                self._set_json(self.monitoring, result["query"]["monitoring"], "Monitoring data will appear here.")
            self._set_json(self.dispatcher_output, result, "Dispatcher actions will appear here.")
        except Exception as exc:
            self.dispatcher_output.setPlainText(f"Error: {exc}")

    def load_manager_home(self):
        try:
            result = self._request("/bff/web/manager-home")
            self._set_json(self.manager_dashboard, result.get("dashboard"), "Dashboard data will appear here.")
            self._apply_templates(result.get("templates", []))
            self._apply_report_jobs(result.get("recent_reports", []))
            self._set_json(self.manager_output, result, "Manager actions will appear here.")
        except Exception as exc:
            self.manager_output.setPlainText(f"Error: {exc}")

    def load_templates(self):
        try:
            result = self._request("/reports/templates")
            self._apply_templates(result)
            self._set_json(self.manager_output, {"templates": result}, "Manager actions will appear here.")
        except Exception as exc:
            self.manager_output.setPlainText(f"Error: {exc}")

    def load_report_jobs(self):
        try:
            result = self._request("/bff/web/reports?limit=30")
            self._apply_report_jobs(result.get("reports", []))
            self._set_json(self.manager_output, result, "Manager actions will appear here.")
        except Exception as exc:
            self.manager_output.setPlainText(f"Error: {exc}")

    def _queue_report(self, delay_seconds=0):
        payload = self.selected_template_payload()
        payload["delay_seconds"] = delay_seconds
        result = self._request("/bff/web/reports/generate", payload)
        self.active_task_id = result.get("command", {}).get("task_id", "")
        query = result.get("query", {})
        if query.get("dashboard"):
            self._set_json(self.manager_dashboard, query["dashboard"], "Dashboard data will appear here.")
        if query.get("templates"):
            self._apply_templates(query["templates"])
        if query.get("recent_reports"):
            self._apply_report_jobs(query["recent_reports"])
        self._set_json(self.manager_output, result, "Manager actions will appear here.")

    def queue_report_now(self):
        try:
            self._queue_report(delay_seconds=0)
        except Exception as exc:
            self.manager_output.setPlainText(f"Error: {exc}")

    def queue_report_delayed(self):
        try:
            self._queue_report(delay_seconds=self.selected_delay_seconds())
        except Exception as exc:
            self.manager_output.setPlainText(f"Error: {exc}")

    def open_report_document(self):
        try:
            job = self.selected_report_job()
            if not job.get("has_document"):
                raise RuntimeError("Selected report does not have a generated DOCX yet.")
            url = (
                f"{self.api_base.text().rstrip('/')}/reports/document/{job['job_id']}"
                f"?token={quote(self.token)}"
            )
            webbrowser.open(url)
        except Exception as exc:
            self.manager_output.setPlainText(f"Error: {exc}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DesktopWindow()
    window.show()
    sys.exit(app.exec())
