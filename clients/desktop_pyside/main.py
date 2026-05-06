import json
import os
import sys
import webbrowser
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


ROLE_TITLES = {
    "tech_expert": "технический эксперт",
    "dispatcher_specialist": "специалист-диспетчер",
    "manager": "руководитель",
    "admin": "администратор",
}

EMPTY_MONITORING = "Данные мониторинга появятся здесь."
EMPTY_EXPERT = "Здесь появятся действия технического эксперта."
EMPTY_DISPATCHER = "Здесь появятся действия диспетчера."
EMPTY_MANAGER = "Здесь появятся действия руководителя."
EMPTY_REPORTS = "Здесь появится очередь отчетов."


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

        self.setWindowTitle("Мониторинг обслуживания")
        self.resize(1640, 920)
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(
            """
            QMainWindow {
                background: #1c194f;
            }
            QWidget {
                color: #ffffff;
                font-family: "Segoe UI", "SF Pro Display", Arial;
                font-size: 14px;
            }
            QWidget#AppShell {
                background: #1c194f;
            }
            QWidget#Workspace {
                background: #1c194f;
            }
            QFrame#TopBar, QFrame#PanelCard {
                background: #080e24;
                border: 1px solid #34306f;
                border-radius: 22px;
            }
            QLabel#AppTitle {
                color: #ffffff;
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#AppSubtitle {
                color: #c9c5ff;
                font-size: 14px;
            }
            QLabel#StatusPill {
                background: #7b2550;
                border: 1px solid #8b3360;
                border-radius: 16px;
                color: #ffffff;
                padding: 8px 12px;
                font-weight: 600;
            }
            QLabel {
                color: #ffffff;
            }
            QLabel#PanelTitle {
                color: #ffffff;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#PanelHelp {
                color: #c9c5ff;
                line-height: 145%;
            }
            QLabel#FieldLabel {
                color: #dcd8ff;
                font-weight: 600;
            }
            QLineEdit, QTextEdit, QComboBox {
                background: #302d79;
                border: 1px solid #514bb1;
                border-radius: 12px;
                padding: 9px 11px;
                color: #ffffff;
                selection-background-color: #8d82ff;
                selection-color: #ffffff;
            }
            QTextEdit {
                font-family: "Segoe UI", "SF Pro Text", Arial;
                font-size: 13px;
                line-height: 145%;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                background: #373386;
                border: 1px solid #8d82ff;
            }
            QComboBox::drop-down {
                border: 0;
                width: 28px;
            }
            QPushButton {
                background: #8377ff;
                color: white;
                border: 0;
                border-radius: 13px;
                padding: 10px 15px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #948bff;
            }
            QPushButton:pressed {
                background: #6f62f0;
            }
            QPushButton#LogoutButton {
                background: #7b2550;
                color: #ffffff;
                border: 1px solid #8b3360;
            }
            QPushButton#LogoutButton:hover {
                background: #8b2d5c;
            }
            QScrollArea {
                border: 0;
                background: transparent;
            }
            QScrollArea QWidget {
                background: #1c194f;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 4px 0 4px 0;
            }
            QScrollBar::handle:vertical {
                background: #5a55aa;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            """
        )

        central = QWidget()
        central.setObjectName("AppShell")
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        self._add_shadow(top_bar, blur=26, y_offset=8, alpha=22)
        top_layout = QVBoxLayout(top_bar)
        top_layout.setContentsMargins(22, 18, 22, 18)
        top_layout.setSpacing(14)

        heading_row = QHBoxLayout()
        heading_text = QVBoxLayout()
        title = QLabel("Мониторинг обслуживания")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Рабочее место эксперта, диспетчера и руководителя")
        subtitle.setObjectName("AppSubtitle")
        heading_text.addWidget(title)
        heading_text.addWidget(subtitle)
        heading_row.addLayout(heading_text, 1)

        self.info = QLabel("Не выполнен вход")
        self.info.setObjectName("StatusPill")
        heading_row.addWidget(self.info)
        self.logout_btn = QPushButton("Выйти")
        self.logout_btn.setObjectName("LogoutButton")
        self.logout_btn.clicked.connect(self.logout)
        self.logout_btn.setVisible(False)
        heading_row.addWidget(self.logout_btn)

        auth_row = QHBoxLayout()
        auth_row.setSpacing(10)
        self.api_label = QLabel("API")
        self.api_label.setObjectName("FieldLabel")
        self.api_label.setVisible(self.debug_mode)
        self.api_base = QLineEdit("http://127.0.0.1:8000")
        self.api_base.setVisible(self.debug_mode)
        self.email = QLineEdit("temp-techexpert@example.com")
        self.email.setPlaceholderText("Электронная почта")
        self.password = QLineEdit("Expert123!")
        self.password.setPlaceholderText("Пароль")
        self.password.setEchoMode(QLineEdit.Password)
        self.login_btn = QPushButton("Войти")
        self.login_btn.clicked.connect(self.login)

        auth_row.addWidget(self.api_label)
        auth_row.addWidget(self.api_base, 2)
        auth_row.addWidget(self.email, 1)
        auth_row.addWidget(self.password, 1)
        auth_row.addWidget(self.login_btn)
        self.auth_widgets = [self.api_label, self.api_base, self.email, self.password, self.login_btn]

        top_layout.addLayout(heading_row)
        top_layout.addLayout(auth_row)

        panels = QHBoxLayout()
        panels.setSpacing(16)
        self.monitoring_panel = self._build_monitoring_panel()
        self.expert_panel = self._build_expert_panel()
        self.dispatcher_panel = self._build_dispatcher_panel()
        self.manager_panel = self._build_manager_panel()

        panels.addWidget(self.monitoring_panel, 2)
        panels.addWidget(self.expert_panel, 2)
        panels.addWidget(self.dispatcher_panel, 2)
        panels.addWidget(self.manager_panel, 3)

        panels_container = QWidget()
        panels_container.setObjectName("Workspace")
        panels_container.setLayout(panels)

        self.workspace_scroll = QScrollArea()
        self.workspace_scroll.setObjectName("Workspace")
        self.workspace_scroll.setWidgetResizable(True)
        self.workspace_scroll.setWidget(panels_container)
        self.workspace_scroll.viewport().setStyleSheet("background: #1c194f;")

        root.addWidget(top_bar)
        root.addWidget(self.workspace_scroll, 1)

        self.setCentralWidget(central)
        self._apply_role_visibility()

    def _build_panel_widget(self, title_text, help_text):
        panel = QFrame()
        panel.setObjectName("PanelCard")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._add_shadow(panel, blur=24, y_offset=10, alpha=18)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = QLabel(title_text)
        title.setObjectName("PanelTitle")
        help_label = QLabel(help_text)
        help_label.setObjectName("PanelHelp")
        help_label.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(help_label)
        return panel, layout

    def _add_shadow(self, widget, blur=24, y_offset=8, alpha=20):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(blur)
        shadow.setOffset(0, y_offset)
        shadow.setColor(QColor(5, 8, 24, alpha))
        widget.setGraphicsEffect(shadow)

    def _build_monitoring_panel(self):
        panel, layout = self._build_panel_widget(
            "Общий мониторинг",
            "Оперативная сводка по оборудованию, отказам и текущему состоянию работ.",
        )
        button_row = QHBoxLayout()
        self.load_monitoring_btn = QPushButton("Обновить")
        self.load_monitoring_btn.clicked.connect(self.load_monitoring)
        button_row.addWidget(self.load_monitoring_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        self.monitoring = QTextEdit()
        self.monitoring.setReadOnly(True)
        self.monitoring.setPlainText(EMPTY_MONITORING)
        layout.addWidget(self.monitoring)
        return panel

    def _build_expert_panel(self):
        panel, layout = self._build_panel_widget(
            "Технический эксперт",
            "Загрузка отказов, подтверждение инцидентов и оформление рекомендаций.",
        )
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setSpacing(10)
        self.expert_fault = QComboBox()
        self.expert_fault.addItem("Сначала загрузите отказы")
        self.expert_priority = QLineEdit("high")
        self.expert_text = QLineEdit("Проверить оборудование и заменить изношенный узел.")
        form.addRow("Отказ", self.expert_fault)
        form.addRow("Приоритет", self.expert_priority)
        form.addRow("Рекомендация", self.expert_text)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.load_faults_btn = QPushButton("Загрузить")
        self.load_faults_btn.clicked.connect(self.load_faults)
        self.create_recommendation_btn = QPushButton("Создать рекомендацию")
        self.create_recommendation_btn.clicked.connect(self.create_recommendation)
        self.confirm_fault_btn = QPushButton("Подтвердить")
        self.confirm_fault_btn.clicked.connect(self.confirm_fault)
        buttons.addWidget(self.load_faults_btn)
        buttons.addWidget(self.create_recommendation_btn)
        buttons.addWidget(self.confirm_fault_btn)
        layout.addLayout(buttons)

        self.expert_output = QTextEdit()
        self.expert_output.setReadOnly(True)
        self.expert_output.setPlainText(EMPTY_EXPERT)
        layout.addWidget(self.expert_output)
        return panel

    def _build_dispatcher_panel(self):
        panel, layout = self._build_panel_widget(
            "Диспетчер",
            "Работа с рекомендациями и создание планов обслуживания.",
        )
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.load_recommendations_btn = QPushButton("Загрузить рекомендации")
        self.load_recommendations_btn.clicked.connect(self.load_dispatcher_recommendations)
        self.create_plan_btn = QPushButton("Создать план")
        self.create_plan_btn.clicked.connect(self.create_plan)
        buttons.addWidget(self.load_recommendations_btn)
        buttons.addWidget(self.create_plan_btn)
        layout.addLayout(buttons)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setSpacing(10)
        self.recommendations = QComboBox()
        self.recommendations.addItem("Сначала загрузите рекомендации")
        self.plan_date = QLineEdit("2026-04-30")
        form.addRow("Рекомендация", self.recommendations)
        form.addRow("Дата плана", self.plan_date)
        layout.addLayout(form)

        self.dispatcher_output = QTextEdit()
        self.dispatcher_output.setReadOnly(True)
        self.dispatcher_output.setPlainText(EMPTY_DISPATCHER)
        layout.addWidget(self.dispatcher_output)
        return panel

    def _build_manager_panel(self):
        panel, layout = self._build_panel_widget(
            "Руководитель",
            "Дашборд, шаблоны, очередь отчетов и доступ к готовым документам.",
        )
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.load_manager_home_btn = QPushButton("Обновить обзор")
        self.load_manager_home_btn.clicked.connect(self.load_manager_home)
        self.load_templates_btn = QPushButton("Шаблоны")
        self.load_templates_btn.clicked.connect(self.load_templates)
        self.load_report_jobs_btn = QPushButton("Отчеты")
        self.load_report_jobs_btn.clicked.connect(self.load_report_jobs)
        buttons.addWidget(self.load_manager_home_btn)
        buttons.addWidget(self.load_templates_btn)
        buttons.addWidget(self.load_report_jobs_btn)
        layout.addLayout(buttons)

        template_form = QFormLayout()
        template_form.setLabelAlignment(Qt.AlignLeft)
        template_form.setFormAlignment(Qt.AlignTop)
        template_form.setSpacing(10)
        self.template_select = QComboBox()
        self.template_select.addItem("Сначала загрузите шаблоны")
        self.delay_value = QLineEdit("10")
        self.delay_unit = QComboBox()
        self.delay_unit.addItems(["секунды", "минуты", "часы"])
        template_form.addRow("Шаблон", self.template_select)
        template_form.addRow("Задержка", self.delay_value)
        template_form.addRow("Единицы", self.delay_unit)
        layout.addLayout(template_form)

        report_buttons = QHBoxLayout()
        report_buttons.setSpacing(8)
        self.queue_report_btn = QPushButton("Сформировать сейчас")
        self.queue_report_btn.clicked.connect(self.queue_report_now)
        self.queue_delayed_report_btn = QPushButton("Сформировать позже")
        self.queue_delayed_report_btn.clicked.connect(self.queue_report_delayed)
        report_buttons.addWidget(self.queue_report_btn)
        report_buttons.addWidget(self.queue_delayed_report_btn)
        layout.addLayout(report_buttons)

        report_job_form = QFormLayout()
        report_job_form.setLabelAlignment(Qt.AlignLeft)
        report_job_form.setFormAlignment(Qt.AlignTop)
        self.report_job_select = QComboBox()
        self.report_job_select.addItem("Сначала загрузите отчеты")
        self.open_report_btn = QPushButton("Открыть DOCX")
        self.open_report_btn.clicked.connect(self.open_report_document)
        report_job_row = QHBoxLayout()
        report_job_row.addWidget(self.report_job_select, 1)
        report_job_row.addWidget(self.open_report_btn)
        report_job_container = QWidget()
        report_job_container.setLayout(report_job_row)
        report_job_form.addRow("Очередь", report_job_container)
        layout.addLayout(report_job_form)

        self.manager_dashboard = QTextEdit()
        self.manager_dashboard.setReadOnly(True)
        self.manager_dashboard.setPlainText("Данные дашборда появятся здесь.")
        self.report_jobs_view = QTextEdit()
        self.report_jobs_view.setReadOnly(True)
        self.report_jobs_view.setPlainText(EMPTY_REPORTS)
        self.manager_output = QTextEdit()
        self.manager_output.setReadOnly(True)
        self.manager_output.setPlainText(EMPTY_MANAGER)
        layout.addWidget(self.manager_dashboard)
        layout.addWidget(self.report_jobs_view)
        layout.addWidget(self.manager_output)
        return panel

    def _request(self, path, body=None):
        if path != "/login" and not self.token:
            raise RuntimeError("Сначала выполните вход.")

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
            raise RuntimeError(f"Backend недоступен или вернул ошибку: {exc}") from exc

    def _set_json(self, widget, value, empty_message):
        if not value or (isinstance(value, list) and len(value) == 0):
            widget.setPlainText(empty_message)
            return
        widget.setPlainText(self._format_result(value, empty_message))

    def _format_result(self, value, empty_message):
        if not value or (isinstance(value, list) and len(value) == 0):
            return empty_message

        if isinstance(value, list):
            return self._format_section("Найденные записи", value)

        if not isinstance(value, dict):
            return str(value)

        lines = []
        command = value.get("command")
        if isinstance(command, dict):
            lines.extend(self._format_command(command))

        query = value.get("query") if isinstance(value.get("query"), dict) else value
        sections = [
            ("dashboard", "Дашборд"),
            ("faults", "Отказы"),
            ("monitoring", "Мониторинг"),
            ("recommendations", "Рекомендации"),
            ("templates", "Шаблоны отчетов"),
            ("reports", "Отчеты"),
            ("recent_reports", "Последние отчеты"),
        ]
        for key, title in sections:
            rows = query.get(key) if isinstance(query, dict) else None
            if rows:
                if lines:
                    lines.append("")
                lines.append(self._format_section(title, rows))

        if lines:
            return "\n".join(lines)
        return self._format_section("Результат", value)

    def _format_command(self, command):
        status_map = {
            "updated": "обновлено",
            "created": "создано",
            "queued": "поставлено в очередь",
            "success": "выполнено",
            "ok": "выполнено",
            "confirmed": "подтверждено",
        }
        lines = ["Операция выполнена"]
        status = command.get("status")
        if status:
            lines.append(f"Статус: {status_map.get(status, status)}")
        if command.get("fault_status"):
            lines.append(f"Состояние отказа: {status_map.get(command['fault_status'], command['fault_status'])}")
        if command.get("fault_ids"):
            lines.append(f"Отказы: {', '.join(str(item) for item in command['fault_ids'])}")
        if command.get("task_id"):
            lines.append(f"Задача: {command['task_id']}")
        if command.get("report_id"):
            lines.append(f"Отчет: {command['report_id']}")
        return lines

    def _format_section(self, title, data):
        if isinstance(data, dict) and not self._looks_like_record(data):
            lines = [title]
            for key, item in data.items():
                if isinstance(item, list):
                    lines.append(f"{self._prettify_key(key)}: {len(item)} записей")
                elif isinstance(item, dict):
                    lines.append(f"{self._prettify_key(key)}:")
                    for child_key, child_value in item.items():
                        lines.append(f"   {self._prettify_key(child_key)}: {self._display_value(child_value)}")
                else:
                    lines.append(f"{self._prettify_key(key)}: {self._display_value(item)}")
            return "\n".join(lines)

        if isinstance(data, dict):
            rows = [data]
        elif isinstance(data, list):
            rows = data
        else:
            return f"{title}\n{data}"

        if not rows:
            return f"{title}\nЗаписей нет."

        lines = [title]
        for index, item in enumerate(rows, 1):
            lines.extend(self._format_item(index, item))
        return "\n".join(lines)

    def _format_item(self, index, item):
        if not isinstance(item, dict):
            return [f"{index}. {item}"]

        title = (
            item.get("equipment_name")
            or item.get("template_name")
            or item.get("report_type")
            or item.get("component_name")
            or item.get("status")
            or f"Запись {item.get('id', index)}"
        )
        lines = [f"{index}. {title}"]

        details = [
            ("component_name", "Компонент"),
            ("description", "Описание"),
            ("severity", "Важность"),
            ("status", "Статус"),
            ("priority", "Приоритет"),
            ("recommendation_text", "Рекомендация"),
            ("planned_date", "Дата плана"),
            ("detected_at", "Обнаружено"),
            ("report_type", "Тип отчета"),
            ("template_name", "Шаблон"),
            ("job_id", "Задача"),
        ]
        for key, label in details:
            if item.get(key) and item.get(key) != title:
                lines.append(f"   {label}: {self._display_value(item[key])}")
        if item.get("has_document") is not None:
            lines.append(f"   Документ: {'готов' if item.get('has_document') else 'еще формируется'}")
        return lines

    def _looks_like_record(self, item):
        known_fields = {
            "id",
            "equipment_name",
            "component_name",
            "description",
            "severity",
            "status",
            "priority",
            "recommendation_text",
            "planned_date",
            "report_type",
            "template_name",
            "job_id",
            "has_document",
        }
        return any(key in item for key in known_fields)

    def _prettify_key(self, key):
        labels = {
            "total_faults": "Всего отказов",
            "open_faults": "Открытые отказы",
            "confirmed_faults": "Подтвержденные отказы",
            "total_tasks": "Всего задач",
            "active_tasks": "Активные задачи",
            "completed_tasks": "Завершенные задачи",
            "reports": "Отчеты",
            "faults": "Отказы",
            "recommendations": "Рекомендации",
            "templates": "Шаблоны",
            "status": "Статус",
            "count": "Количество",
        }
        return labels.get(str(key), str(key).replace("_", " ").capitalize())

    def _display_value(self, value):
        value_map = {
            "high": "высокий",
            "medium": "средний",
            "low": "низкий",
            "critical": "критический",
            "confirmed": "подтверждено",
            "open": "открыто",
            "new": "новое",
            "updated": "обновлено",
            "created": "создано",
            "queued": "в очереди",
            "pending": "ожидает",
            "completed": "завершено",
            "failed": "ошибка",
        }
        if isinstance(value, str):
            return value_map.get(value, value)
        return value

    def _show_success(self, title, message):
        QMessageBox.information(self, title, message)

    def _apply_auth_visibility(self):
        signed_in = bool(self.token)
        self.logout_btn.setVisible(signed_in)
        self.info.setText(
            f"Роль: {ROLE_TITLES.get(self.role, self.role)}"
            if signed_in
            else "Не выполнен вход"
        )
        for widget in self.auth_widgets:
            if widget in {self.api_label, self.api_base}:
                widget.setVisible((not signed_in) and self.debug_mode)
            else:
                widget.setVisible(not signed_in)
        self.workspace_scroll.setVisible(signed_in)

    def logout(self):
        self.token = ""
        self.role = ""
        self.active_task_id = ""
        self._apply_role_visibility()
        self.password.clear()
        self.email.setFocus()

    def _apply_role_visibility(self):
        self._apply_auth_visibility()
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
        self.expert_fault.addItems(labels or ["Нет доступных отказов"])

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
        self.recommendations.addItems(labels or ["Нет доступных рекомендаций"])

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
        self.template_select.addItems(labels or ["Нет активных шаблонов"])

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
        self.report_job_select.addItems(labels or ["Нет отчетов в очереди"])
        self._set_json(self.report_jobs_view, rows, EMPTY_REPORTS)

    def selected_fault_id(self):
        item = self.faults_by_label.get(self.expert_fault.currentText())
        if not item:
            raise RuntimeError("Сначала загрузите и выберите отказ.")
        return int(item["id"])

    def selected_recommendation_ids(self):
        item = self.recommendations_by_label.get(self.recommendations.currentText())
        if not item:
            raise RuntimeError("Сначала загрузите и выберите рекомендацию.")
        return [int(item["recommendation_id"])]

    def selected_template_payload(self):
        item = self.templates_by_label.get(self.template_select.currentText())
        if not item:
            raise RuntimeError("Сначала загрузите и выберите шаблон отчета.")
        return {"template_id": int(item["id"])}

    def selected_delay_seconds(self):
        try:
            value = int(self.delay_value.text())
        except ValueError as exc:
            raise RuntimeError("Задержка должна быть целым числом.") from exc
        if value <= 0:
            raise RuntimeError("Задержка должна быть больше 0.")
        multiplier = {"секунды": 1, "минуты": 60, "часы": 3600}[self.delay_unit.currentText()]
        return value * multiplier

    def selected_report_job(self):
        item = self.report_jobs_by_label.get(self.report_job_select.currentText())
        if not item:
            raise RuntimeError("Сначала загрузите очередь отчетов.")
        return item

    def login(self):
        try:
            result = self._request("/login", {"email": self.email.text(), "password": self.password.text()})
            self.token = result["access_token"]
            self.role = result["role"]
            self.info.setText(f"Роль: {ROLE_TITLES.get(self.role, self.role)}")
            self._apply_role_visibility()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка входа", str(exc))

    def load_monitoring(self):
        try:
            result = self._request("/bff/desktop/monitoring")
            self._set_json(self.monitoring, result, EMPTY_MONITORING)
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка мониторинга", str(exc))

    def load_faults(self):
        try:
            result = self._request("/expert/faults")
            self._apply_faults(result)
            self._set_json(self.expert_output, result, EMPTY_EXPERT)
        except Exception as exc:
            self.expert_output.setPlainText(f"Ошибка: {exc}")

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
                self._set_json(self.monitoring, result["query"]["monitoring"], EMPTY_MONITORING)
            self._set_json(self.expert_output, result, EMPTY_EXPERT)
            self._show_success("Готово", "Рекомендация создана")
        except Exception as exc:
            self.expert_output.setPlainText(f"Ошибка: {exc}")

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
                self._set_json(self.monitoring, result["query"]["monitoring"], EMPTY_MONITORING)
            self._set_json(self.expert_output, result, EMPTY_EXPERT)
            self._show_success("Готово", "Отказ подтвержден")
        except Exception as exc:
            self.expert_output.setPlainText(f"Ошибка: {exc}")

    def load_dispatcher_recommendations(self):
        try:
            result = self._request("/specialist/recommendations")
            self._apply_recommendations(result)
            self._set_json(self.dispatcher_output, result, EMPTY_DISPATCHER)
        except Exception as exc:
            self.dispatcher_output.setPlainText(f"Ошибка: {exc}")

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
                self._set_json(self.monitoring, result["query"]["monitoring"], EMPTY_MONITORING)
            self._set_json(self.dispatcher_output, result, EMPTY_DISPATCHER)
            self._show_success("Готово", "План обслуживания создан")
        except Exception as exc:
            self.dispatcher_output.setPlainText(f"Ошибка: {exc}")

    def load_manager_home(self):
        try:
            result = self._request("/bff/web/manager-home")
            self._set_json(self.manager_dashboard, result.get("dashboard"), "Данные дашборда появятся здесь.")
            self._apply_templates(result.get("templates", []))
            self._apply_report_jobs(result.get("recent_reports", []))
            self._set_json(self.manager_output, result, EMPTY_MANAGER)
        except Exception as exc:
            self.manager_output.setPlainText(f"Ошибка: {exc}")

    def load_templates(self):
        try:
            result = self._request("/reports/templates")
            self._apply_templates(result)
            self._set_json(self.manager_output, {"templates": result}, EMPTY_MANAGER)
        except Exception as exc:
            self.manager_output.setPlainText(f"Ошибка: {exc}")

    def load_report_jobs(self):
        try:
            result = self._request("/bff/web/reports?limit=30")
            self._apply_report_jobs(result.get("reports", []))
            self._set_json(self.manager_output, result, EMPTY_MANAGER)
        except Exception as exc:
            self.manager_output.setPlainText(f"Ошибка: {exc}")

    def _queue_report(self, delay_seconds=0):
        payload = self.selected_template_payload()
        payload["delay_seconds"] = delay_seconds
        result = self._request("/bff/web/reports/generate", payload)
        self.active_task_id = result.get("command", {}).get("task_id", "")
        query = result.get("query", {})
        if query.get("dashboard"):
            self._set_json(self.manager_dashboard, query["dashboard"], "Данные дашборда появятся здесь.")
        if query.get("templates"):
            self._apply_templates(query["templates"])
        if query.get("recent_reports"):
            self._apply_report_jobs(query["recent_reports"])
        self._set_json(self.manager_output, result, EMPTY_MANAGER)

    def queue_report_now(self):
        try:
            self._queue_report(delay_seconds=0)
            self._show_success("Готово", "Отчет отправлен на формирование")
        except Exception as exc:
            self.manager_output.setPlainText(f"Ошибка: {exc}")

    def queue_report_delayed(self):
        try:
            self._queue_report(delay_seconds=self.selected_delay_seconds())
            self._show_success("Готово", "Отчет поставлен в очередь с задержкой")
        except Exception as exc:
            self.manager_output.setPlainText(f"Ошибка: {exc}")

    def open_report_document(self):
        try:
            job = self.selected_report_job()
            if not job.get("has_document"):
                raise RuntimeError("Для выбранного отчета еще нет готового DOCX.")
            url = (
                f"{self.api_base.text().rstrip('/')}/reports/document/{job['job_id']}"
                f"?token={quote(self.token)}"
            )
            webbrowser.open(url)
        except Exception as exc:
            self.manager_output.setPlainText(f"Ошибка: {exc}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DesktopWindow()
    window.show()
    sys.exit(app.exec())
