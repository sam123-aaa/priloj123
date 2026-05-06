import json
import os

from kivy.app import App
from kivy.lang import Builder
from kivy.network.urlrequest import UrlRequest
from kivy.properties import BooleanProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.core.window import Window
from kivy.utils import platform

METRIC_PRESETS = {
    "gap": {"parameter_name": "Люфт", "unit": "мм", "min_value": None, "max_value": None},
    "temperature": {
        "parameter_name": "Отклонение температуры",
        "unit": "C",
        "min_value": None,
        "max_value": None,
    },
    "pressure": {"parameter_name": "Давление", "unit": "бар", "min_value": None, "max_value": None},
    "vibration": {"parameter_name": "Вибрация", "unit": "мм/с", "min_value": None, "max_value": None},
}

DEFAULT_MEASUREMENT_OPTIONS = list(METRIC_PRESETS.values())


def default_api_base():
    if os.getenv("API_BASE_URL"):
        return os.getenv("API_BASE_URL")
    if platform == "android":
        return "http://10.0.2.2:8000"
    return "http://127.0.0.1:8000"


class FullTouchButton(Button):
    def collide_point(self, x, y):
        return self.x <= x <= self.right and self.y <= y <= self.top

    def on_touch_down(self, touch):
        if self.disabled or not self.collide_point(*touch.pos):
            return False
        touch.grab(self)
        self.state = "down"
        self.dispatch("on_press")
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
        touch.ungrab(self)
        self.state = "normal"
        if self.collide_point(*touch.pos) or self.always_release:
            self.dispatch("on_release")
        return True


class FullTouchSpinner(Spinner):
    def collide_point(self, x, y):
        return self.x <= x <= self.right and self.y <= y <= self.top


class FullTouchTextInput(TextInput):
    def collide_point(self, x, y):
        return self.x <= x <= self.right and self.y <= y <= self.top

    def on_touch_down(self, touch):
        if self.disabled or not self.collide_point(*touch.pos):
            return False
        self.focus = True
        return super().on_touch_down(touch) or True


class TouchSafeScrollView(ScrollView):
    def on_touch_down(self, touch):
        if self.disabled or not self.collide_point(*touch.pos):
            return False
        for child in reversed(self.children):
            if child.dispatch("on_touch_down", touch):
                return True
        return super().on_touch_down(touch)

KV = """
<RoleSection@BoxLayout>:
    orientation: "vertical"
    size_hint_y: None
    height: self.minimum_height
    spacing: "10dp"
    padding: "14dp", "12dp", "14dp", "14dp"
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [18, 18, 18, 18]

<SectionTitle@Label>:
    size_hint_y: None
    height: "30dp"
    color: 0.05, 0.07, 0.12, 1
    bold: True
    font_size: "18sp"
    halign: "left"
    valign: "middle"
    text_size: self.size

<FieldLabel@Label>:
    size_hint_y: None
    height: "20dp"
    color: 0.36, 0.39, 0.46, 1
    font_size: "13sp"
    halign: "left"
    valign: "middle"
    text_size: self.size

<InfoLabel@Label>:
    size_hint_y: None
    height: max(self.texture_size[1] + dp(8), dp(28))
    color: 0.36, 0.39, 0.46, 1
    font_size: "13sp"
    halign: "left"
    valign: "top"
    text_size: self.width, None

<StatusLabel@Label>:
    size_hint_y: None
    height: max(self.texture_size[1] + dp(8), dp(34))
    color: 0.16, 0.18, 0.24, 1
    font_size: "14sp"
    halign: "left"
    valign: "middle"
    text_size: self.width, None

<EditInput@FullTouchTextInput>:
    multiline: False
    write_tab: False
    foreground_color: 0.05, 0.07, 0.12, 1
    background_normal: ""
    background_active: ""
    background_color: 0.94, 0.95, 0.97, 1
    cursor_color: 0.0, 0.48, 1, 1
    selection_color: 0.0, 0.48, 1, 0.25
    size_hint_y: None
    height: "48dp"
    padding: "12dp", "13dp"

<RoundedSpinner@FullTouchSpinner>:
    size_hint_y: None
    height: "50dp"
    font_size: "14sp"
    color: 0.05, 0.07, 0.12, 1
    background_normal: ""
    background_down: ""
    background_color: 0.94, 0.95, 0.97, 1
    option_cls: "SpinnerOption"

<PrimaryButton@Button>:
    size_hint_y: None
    height: "50dp"
    font_size: "15sp"
    bold: True
    color: 1, 1, 1, 1
    background_normal: ""
    background_down: ""
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: (0.0, 0.48, 1, 1) if not self.disabled else (0.70, 0.75, 0.82, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14, 14, 14, 14]

<SecondaryButton@Button>:
    size_hint_y: None
    height: "48dp"
    font_size: "14sp"
    color: (0.0, 0.36, 0.80, 1) if not self.disabled else (0.55, 0.58, 0.64, 1)
    background_normal: ""
    background_down: ""
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: (0.90, 0.95, 1, 1) if not self.disabled else (0.93, 0.94, 0.96, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14, 14, 14, 14]

<StepperButton@Button>:
    size_hint_y: None
    height: "48dp"
    font_size: "14sp"
    bold: True
    color: 0.0, 0.36, 0.80, 1
    background_normal: ""
    background_down: ""
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: 0.90, 0.95, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [12, 12, 12, 12]

<MobileRoot>:
    orientation: "vertical"
    padding: "12dp", "10dp", "12dp", "10dp"
    spacing: "10dp"
    canvas.before:
        Color:
            rgba: 0.95, 0.96, 0.98, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: "vertical"
        size_hint_y: None
        height: "82dp"
        padding: "4dp", "4dp", "4dp", 0
        spacing: "2dp"
        Label:
            text: "Maintenance"
            size_hint_y: None
            height: "36dp"
            color: 0.05, 0.07, 0.12, 1
            bold: True
            font_size: "28sp"
            halign: "left"
            valign: "middle"
            text_size: self.size
        Label:
            text: root.role_hint
            size_hint_y: None
            height: "38dp"
            color: 0.36, 0.39, 0.46, 1
            font_size: "13sp"
            halign: "left"
            valign: "top"
            text_size: self.width, None

    TouchSafeScrollView:
        do_scroll_x: False
        bar_width: "3dp"
        scroll_timeout: 180
        scroll_distance: "24dp"
        BoxLayout:
            orientation: "vertical"
            spacing: "10dp"
            padding: 0, 0, 0, "10dp"
            size_hint_y: None
            height: self.minimum_height

            RoleSection:
                SectionTitle:
                    text: "Вход"
                EditInput:
                    id: api_base
                    text: root.api_base
                    opacity: 1 if root.debug_mode else 0
                    disabled: not root.debug_mode
                    hint_text: "API base URL"
                    height: "48dp" if root.debug_mode else 0
                EditInput:
                    id: email
                    text: "temp-metrologist@example.com"
                    hint_text: "Email"
                EditInput:
                    id: password
                    password: True
                    text: "Metrologist123!"
                    hint_text: "Пароль"
                PrimaryButton:
                    text: "Войти" if not root.is_busy else "Загрузка..."
                    disabled: root.is_busy
                    on_press: root.login(email.text, password.text)
                StatusLabel:
                    text: root.session_info

            RoleSection:
                opacity: 1 if root.show_metrologist else 0
                disabled: not root.show_metrologist
                height: self.minimum_height if root.show_metrologist else 0
                SectionTitle:
                    text: "Измерение"
                SecondaryButton:
                    text: "Обновить оборудование"
                    disabled: root.is_busy
                    on_press: root.load_components()
                RoundedSpinner:
                    id: component_spinner
                    text: "Компоненты загружаются автоматически"
                    values: []
                    on_text: root.select_component(self.text)
                InfoLabel:
                    text: root.selected_component_info
                FieldLabel:
                    text: "Показатель"
                RoundedSpinner:
                    id: metric_spinner
                    text: root.selected_metric_label
                    values: ["Люфт", "Температура", "Давление", "Вибрация"]
                    on_text: root.select_metric_label(self.text)
                InfoLabel:
                    text: root.selected_metric_info
                FieldLabel:
                    text: "Значение"
                BoxLayout:
                    size_hint_y: None
                    height: "48dp"
                    spacing: "6dp"
                    StepperButton:
                        text: "-1"
                        size_hint_x: 0.16
                        on_press: root.adjust_measurement_value(-1)
                    StepperButton:
                        text: "-0.1"
                        size_hint_x: 0.20
                        on_press: root.adjust_measurement_value(-0.1)
                    EditInput:
                        id: value_input
                        text: "0.15"
                        input_filter: root.numeric_input_filter
                        hint_text: "0"
                        font_size: "19sp"
                        halign: "center"
                        on_text: root.on_measurement_value_change(self.text)
                    StepperButton:
                        text: "+0.1"
                        size_hint_x: 0.20
                        on_press: root.adjust_measurement_value(0.1)
                    StepperButton:
                        text: "+1"
                        size_hint_x: 0.16
                        on_press: root.adjust_measurement_value(1)
                InfoLabel:
                    text: root.measurement_value_info
                BoxLayout:
                    size_hint_y: None
                    height: "50dp"
                    spacing: "8dp"
                    SecondaryButton:
                        text: "Очистить"
                        disabled: root.is_busy
                        on_press: root.clear_measurement_value()
                    PrimaryButton:
                        text: "Отправить"
                        disabled: root.is_busy
                        on_press: root.send_measurement()

            RoleSection:
                opacity: 1 if root.show_mechanic else 0
                disabled: not root.show_mechanic
                height: self.minimum_height if root.show_mechanic else 0
                SectionTitle:
                    text: "Задачи механика"
                SecondaryButton:
                    text: "Обновить задачи"
                    disabled: root.is_busy
                    on_press: root.load_mechanic_tasks()
                RoundedSpinner:
                    id: mechanic_task_spinner
                    text: "Сначала загрузите задачи"
                    values: []
                    on_text: root.select_mechanic_task(self.text)
                InfoLabel:
                    text: root.selected_mechanic_task_info
                StatusLabel:
                    text: root.mechanic_action_hint
                FieldLabel:
                    text: "Результат выполнения"
                EditInput:
                    id: mechanic_result
                    text: "Выполнено в мобильном клиенте"
                    hint_text: "Результат для завершения"
                    disabled: root.is_busy
                BoxLayout:
                    size_hint_y: None
                    height: "50dp"
                    spacing: "8dp"
                    SecondaryButton:
                        text: "Старт"
                        disabled: root.is_busy
                        on_press: root.mechanic_action("start")
                    PrimaryButton:
                        text: "Готово"
                        disabled: root.is_busy
                        on_press: root.mechanic_action("finish")
                    SecondaryButton:
                        text: "Отмена"
                        disabled: root.is_busy
                        on_press: root.mechanic_action("cancel")

            RoleSection:
                opacity: 1 if root.show_quality else 0
                disabled: not root.show_quality
                height: self.minimum_height if root.show_quality else 0
                SectionTitle:
                    text: "Контроль качества"
                SecondaryButton:
                    text: "Обновить проверки"
                    disabled: root.is_busy
                    on_press: root.load_quality_tasks()
                RoundedSpinner:
                    id: quality_task_spinner
                    text: "Сначала загрузите задачи"
                    values: []
                    on_text: root.select_quality_task(self.text)
                InfoLabel:
                    text: root.selected_quality_task_info
                StatusLabel:
                    text: root.quality_action_hint
                FieldLabel:
                    text: "Статус проверки"
                RoundedSpinner:
                    id: quality_status
                    text: "passed"
                    values: ["passed", "failed", "needs_rework"]
                FieldLabel:
                    text: "Примечание"
                EditInput:
                    id: quality_notes
                    text: "Проверка завершена успешно"
                    hint_text: "Примечание"
                    disabled: root.is_busy
                PrimaryButton:
                    text: "Сохранить проверку"
                    disabled: root.is_busy
                    on_press: root.submit_quality_check()

            RoleSection:
                SectionTitle:
                    text: "Ответ API"
                InfoLabel:
                    text: root.output_text
"""


KV = """
<RoleSection@BoxLayout>:
    orientation: "vertical"
    spacing: "8dp"
    padding: "14dp", "10dp", "14dp", "12dp"
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [18, 18, 18, 18]

<SectionTitle@Label>:
    size_hint_y: None
    height: "28dp"
    color: 0.05, 0.07, 0.12, 1
    bold: True
    font_size: "17sp"
    halign: "left"
    valign: "middle"
    text_size: self.size

<FieldLabel@Label>:
    size_hint_y: None
    height: "18dp"
    color: 0.36, 0.39, 0.46, 1
    font_size: "12sp"
    halign: "left"
    valign: "middle"
    text_size: self.size

<InfoLabel@Label>:
    size_hint_y: None
    height: max(self.texture_size[1] + dp(4), dp(22))
    color: 0.36, 0.39, 0.46, 1
    font_size: "12sp"
    halign: "left"
    valign: "top"
    text_size: self.width, None

<StatusLabel@Label>:
    size_hint_y: None
    height: "28dp"
    color: 0.16, 0.18, 0.24, 1
    font_size: "13sp"
    halign: "left"
    valign: "middle"
    text_size: self.width, None

<EditInput@FullTouchTextInput>:
    multiline: False
    write_tab: False
    foreground_color: 0.05, 0.07, 0.12, 1
    background_normal: ""
    background_active: ""
    background_color: 0.94, 0.95, 0.97, 1
    cursor_color: 0.0, 0.48, 1, 1
    selection_color: 0.0, 0.48, 1, 0.25
    size_hint_y: None
    height: "44dp"
    padding: "12dp", "11dp"

<RoundedSpinner@FullTouchSpinner>:
    size_hint_y: None
    height: "44dp"
    font_size: "13sp"
    color: 0.05, 0.07, 0.12, 1
    background_normal: ""
    background_down: ""
    background_color: 0.94, 0.95, 0.97, 1
    option_cls: "SpinnerOption"

<PrimaryButton@Button>:
    size_hint_y: None
    height: "46dp"
    font_size: "14sp"
    bold: True
    color: 1, 1, 1, 1
    background_normal: ""
    background_down: ""
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: (0.0, 0.48, 1, 1) if not self.disabled else (0.70, 0.75, 0.82, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14, 14, 14, 14]

<SecondaryButton@Button>:
    size_hint_y: None
    height: "46dp"
    font_size: "13sp"
    color: (0.0, 0.36, 0.80, 1) if not self.disabled else (0.55, 0.58, 0.64, 1)
    background_normal: ""
    background_down: ""
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: (0.90, 0.95, 1, 1) if not self.disabled else (0.93, 0.94, 0.96, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14, 14, 14, 14]

<StepperButton@Button>:
    size_hint_y: None
    height: "44dp"
    font_size: "13sp"
    bold: True
    color: 0.0, 0.36, 0.80, 1
    background_normal: ""
    background_down: ""
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: 0.90, 0.95, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [12, 12, 12, 12]

<MobileRoot>:
    orientation: "vertical"
    padding: "10dp"
    spacing: "8dp"
    canvas.before:
        Color:
            rgba: 0.95, 0.96, 0.98, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: "vertical"
        size_hint_y: None
        height: "62dp" if root.is_logged_in else "74dp"
        padding: "4dp", "2dp", "4dp", 0
        spacing: 0
        Label:
            text: "Maintenance"
            size_hint_y: None
            height: "34dp"
            color: 0.05, 0.07, 0.12, 1
            bold: True
            font_size: "26sp"
            halign: "left"
            valign: "middle"
            text_size: self.size
        Label:
            text: root.role_hint
            size_hint_y: None
            height: "26dp" if root.is_logged_in else "38dp"
            color: 0.36, 0.39, 0.46, 1
            font_size: "12sp"
            halign: "left"
            valign: "top"
            text_size: self.width, None

    RoleSection:
        size_hint_y: None
        height: "260dp" if not root.is_logged_in else "92dp"
        spacing: "8dp" if not root.is_logged_in else "2dp"
        SectionTitle:
            text: "Вход" if not root.is_logged_in else "Сессия"
        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: self.minimum_height if not root.is_logged_in else 0
            opacity: 1 if not root.is_logged_in else 0
            disabled: root.is_logged_in
            spacing: "8dp"
            EditInput:
                id: api_base
                text: root.api_base
                opacity: 1 if root.debug_mode else 0
                disabled: not root.debug_mode
                hint_text: "API base URL"
                height: "44dp" if root.debug_mode else 0
            EditInput:
                id: email
                text: "temp-metrologist@example.com"
                hint_text: "Email"
            EditInput:
                id: password
                password: True
                text: "Metrologist123!"
                hint_text: "Пароль"
            PrimaryButton:
                text: "Войти" if not root.is_busy else "Загрузка..."
                disabled: root.is_busy
                on_release: root.login(email.text, password.text)
        BoxLayout:
            size_hint_y: None
            height: "28dp" if not root.is_logged_in else "46dp"
            spacing: "8dp"
            StatusLabel:
                text: root.session_info
            SecondaryButton:
                text: "Выйти"
                opacity: 1 if root.is_logged_in else 0
                disabled: not root.is_logged_in
                height: "44dp"
                size_hint_x: 0.34
                on_release: root.logout()

    BoxLayout:
        orientation: "vertical"
        size_hint_y: 1
        spacing: "8dp"

        RoleSection:
            opacity: 1 if root.show_metrologist else 0
            disabled: not root.show_metrologist
            size_hint_y: 1 if root.show_metrologist else None
            height: 0 if not root.show_metrologist else self.height
            SectionTitle:
                text: "Измерение"
            BoxLayout:
                size_hint_y: None
                height: "44dp"
                spacing: "8dp"
                SecondaryButton:
                    text: "Обновить"
                    disabled: root.is_busy
                    on_release: root.load_components()
                RoundedSpinner:
                    id: component_spinner
                    text: "Выберите компонент"
                    values: []
                    on_text: root.select_component(self.text)
            InfoLabel:
                text: root.selected_component_info
            FieldLabel:
                text: "Показатель"
            RoundedSpinner:
                id: metric_spinner
                text: root.selected_metric_label
                values: ["Люфт", "Температура", "Давление", "Вибрация"]
                on_text: root.select_metric_label(self.text)
            InfoLabel:
                text: root.selected_metric_info
            FieldLabel:
                text: "Значение"
            BoxLayout:
                size_hint_y: None
                height: "44dp"
                spacing: "6dp"
                StepperButton:
                    text: "-1"
                    size_hint_x: 0.16
                    on_release: root.adjust_measurement_value(-1)
                StepperButton:
                    text: "-0.1"
                    size_hint_x: 0.20
                    on_release: root.adjust_measurement_value(-0.1)
                EditInput:
                    id: value_input
                    text: "0.15"
                    input_filter: root.numeric_input_filter
                    hint_text: "0"
                    font_size: "18sp"
                    halign: "center"
                    on_text: root.on_measurement_value_change(self.text)
                StepperButton:
                    text: "+0.1"
                    size_hint_x: 0.20
                    on_release: root.adjust_measurement_value(0.1)
                StepperButton:
                    text: "+1"
                    size_hint_x: 0.16
                    on_release: root.adjust_measurement_value(1)
            InfoLabel:
                text: root.measurement_value_info
            BoxLayout:
                size_hint_y: None
                height: "46dp"
                spacing: "8dp"
                SecondaryButton:
                    text: "Очистить"
                    disabled: root.is_busy
                    on_release: root.clear_measurement_value()
                PrimaryButton:
                    text: "Отправить"
                    disabled: root.is_busy
                    on_release: root.send_measurement()
            InfoLabel:
                text: root.output_text
                size_hint_y: 1

        RoleSection:
            opacity: 1 if root.show_mechanic else 0
            disabled: not root.show_mechanic
            size_hint_y: 1 if root.show_mechanic else None
            height: 0 if not root.show_mechanic else self.height
            SectionTitle:
                text: "Задачи механика"
            SecondaryButton:
                text: "Обновить задачи"
                disabled: root.is_busy
                on_release: root.load_mechanic_tasks()
            RoundedSpinner:
                id: mechanic_task_spinner
                text: "Сначала загрузите задачи"
                values: []
                on_text: root.select_mechanic_task(self.text)
            InfoLabel:
                text: root.selected_mechanic_task_info
            StatusLabel:
                text: root.mechanic_action_hint
            FieldLabel:
                text: "Результат выполнения"
            EditInput:
                id: mechanic_result
                text: "Выполнено в мобильном клиенте"
                hint_text: "Результат для завершения"
                disabled: root.is_busy
            BoxLayout:
                size_hint_y: None
                height: "46dp"
                spacing: "8dp"
                SecondaryButton:
                    text: "Старт"
                    disabled: root.is_busy
                    on_release: root.mechanic_action("start")
                PrimaryButton:
                    text: "Готово"
                    disabled: root.is_busy
                    on_release: root.mechanic_action("finish")
                SecondaryButton:
                    text: "Отмена"
                    disabled: root.is_busy
                    on_release: root.mechanic_action("cancel")
            InfoLabel:
                text: root.output_text
                size_hint_y: 1

        RoleSection:
            opacity: 1 if root.show_quality else 0
            disabled: not root.show_quality
            size_hint_y: 1 if root.show_quality else None
            height: 0 if not root.show_quality else self.height
            SectionTitle:
                text: "Контроль качества"
            SecondaryButton:
                text: "Обновить проверки"
                disabled: root.is_busy
                on_release: root.load_quality_tasks()
            RoundedSpinner:
                id: quality_task_spinner
                text: "Сначала загрузите задачи"
                values: []
                on_text: root.select_quality_task(self.text)
            InfoLabel:
                text: root.selected_quality_task_info
            StatusLabel:
                text: root.quality_action_hint
            FieldLabel:
                text: "Статус проверки"
            RoundedSpinner:
                id: quality_status
                text: "passed"
                values: ["passed", "failed", "needs_rework"]
            FieldLabel:
                text: "Примечание"
            EditInput:
                id: quality_notes
                text: "Проверка завершена успешно"
                hint_text: "Примечание"
                disabled: root.is_busy
            PrimaryButton:
                text: "Сохранить проверку"
                disabled: root.is_busy
                on_release: root.submit_quality_check()
            InfoLabel:
                text: root.output_text
                size_hint_y: 1
"""


class MobileRoot(BoxLayout):
    api_base = StringProperty(default_api_base())
    session_info = StringProperty("Не авторизован")
    output_text = StringProperty("Здесь будут ответы API")
    show_metrologist = BooleanProperty(False)
    show_mechanic = BooleanProperty(False)
    show_quality = BooleanProperty(False)
    is_busy = BooleanProperty(False)
    is_logged_in = BooleanProperty(False)
    debug_mode = BooleanProperty(bool(int(os.getenv("CLIENT_DEBUG_UI", "0"))))
    role_hint = StringProperty("Входите под metrologist, mechanic или quality_engineer")
    touch_info = StringProperty("touch: ждёт нажатия")
    selected_component_info = StringProperty("Компонент не выбран")
    selected_metric_key = StringProperty("gap")
    selected_metric_label = StringProperty("Люфт")
    selected_metric_info = StringProperty("Показатель не выбран")
    selected_unit_info = StringProperty("Единица измерения не выбрана")
    measurement_value_info = StringProperty("Введите значение измерения")
    selected_mechanic_task_info = StringProperty("Задача не выбрана")
    mechanic_action_hint = StringProperty("Выберите задачу, чтобы увидеть доступные действия")
    selected_quality_task_info = StringProperty("Задача не выбрана")
    quality_action_hint = StringProperty("Выберите завершённую задачу для проверки")
    selected_component_id = ObjectProperty(None, allownone=True)
    selected_metric_name = StringProperty("")
    selected_metric_unit = StringProperty("")
    selected_mechanic_task_id = ObjectProperty(None, allownone=True)
    selected_mechanic_task_status = StringProperty("")
    selected_quality_task_id = ObjectProperty(None, allownone=True)
    selected_quality_task_status = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.token = ""
        self.role = ""
        self.components_by_label = {}
        self.metric_options_by_key = {key: dict(value) for key, value in METRIC_PRESETS.items()}
        self.mechanic_tasks_by_label = {}
        self.quality_tasks_by_label = {}

    def request(self, path, method="GET", payload=None, on_success=None):
        if self.is_busy:
            return
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.output_text = f"{method} {path}..."
        self.is_busy = True

        def handle_success(req, result):
            self.is_busy = False
            (on_success or self._on_success)(req, result)

        def handle_error(req, error):
            self.is_busy = False
            self._on_error(req, error)

        req_body = None
        if payload is not None:
            req_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        try:
            UrlRequest(
                f"{self.ids.api_base.text.rstrip('/')}{path}",
                req_body=req_body,
                req_headers=headers,
                method=method,
                on_success=handle_success,
                on_failure=handle_error,
                on_error=handle_error,
                timeout=12,
            )
        except Exception as exc:
            self.is_busy = False
            self.output_text = f"Ошибка запроса: {exc}"

    def login(self, email, password):
        if not email.strip() or not password:
            self.output_text = "Заполните email и пароль"
            return
        self.session_info = "Выполняется вход..."
        self.request(
            "/login",
            method="POST",
            payload={"email": email, "password": password},
            on_success=self._on_login_success,
        )

    def _on_login_success(self, _req, result):
        self.token = result["access_token"]
        self.role = result["role"]
        self.is_logged_in = True
        self.session_info = f"Роль: {self.role}"
        self.show_metrologist = self.role in {"metrologist", "admin"}
        self.show_mechanic = self.role in {"mechanic", "admin"}
        self.show_quality = self.role in {"quality_engineer", "admin"}
        hints = {
            "metrologist": "Доступен сбор измерений с оборудования",
            "mechanic": "Доступны задачи механика и изменение их статуса",
            "quality_engineer": "Доступны задачи на проверку качества",
            "admin": "Видны все мобильные сценарии",
        }
        self.role_hint = hints.get(self.role, "Эта роль не поддерживается в mobile client")
        self.output_text = json.dumps({"login": "ok", "role": self.role}, ensure_ascii=False, indent=2)
        if self.show_metrologist:
            self.load_components()
        if self.show_mechanic:
            self.load_mechanic_tasks()
        if self.show_quality:
            self.load_quality_tasks()

    def logout(self):
        self.token = ""
        self.role = ""
        self.is_logged_in = False
        self.show_metrologist = False
        self.show_mechanic = False
        self.show_quality = False
        self.session_info = "Не авторизован"
        self.role_hint = "Входите под metrologist, mechanic или quality_engineer"
        self.output_text = "Сессия завершена"
        self.selected_component_id = None
        self.selected_component_info = "Компонент не выбран"
        self.selected_metric_name = ""
        self.selected_metric_unit = ""
        self.selected_mechanic_task_id = None
        self.selected_mechanic_task_status = ""
        self.selected_mechanic_task_info = "Задача не выбрана"
        self.selected_quality_task_id = None
        self.selected_quality_task_status = ""
        self.selected_quality_task_info = "Задача не выбрана"
        self.mechanic_action_hint = "Выберите задачу, чтобы увидеть доступные действия"
        self.quality_action_hint = "Выберите завершённую задачу для проверки"

    def load_components(self):
        self.request("/bff/mobile/components", on_success=self._on_components_loaded)

    def _on_components_loaded(self, _req, result):
        if isinstance(result, dict):
            result = result.get("components") or result.get("query", {}).get("components", [])
        result = [self._component_with_defaults(item) for item in (result or [])]
        self.components_by_label = {
            f"{item['equipment_name']} / {item['component_name']}": item
            for item in result
        }
        labels = list(self.components_by_label.keys())
        self.ids.component_spinner.values = labels
        if labels:
            self.ids.component_spinner.text = labels[0]
            self.select_component(labels[0])
        else:
            self.ids.component_spinner.text = "Нет компонентов"
            self.selected_component_id = None
            self.selected_metric_name = ""
            self.selected_metric_unit = ""
            self.selected_metric_key = "gap"
            self.selected_metric_label = "Люфт"
            self.selected_component_info = "Компоненты не найдены"
            self.selected_metric_info = "Показатель не выбран"
            self.selected_unit_info = "Единица измерения не выбрана"
        self.output_text = f"Загружено компонентов: {len(result)}"

    def _component_with_defaults(self, component):
        item = dict(component)
        item["measurement_options"] = item.get("measurement_options") or DEFAULT_MEASUREMENT_OPTIONS
        return item

    def select_component(self, label):
        component = self.components_by_label.get(label)
        if not component:
            self.selected_component_id = None
            self.selected_component_info = "Компонент не выбран"
            self.metric_options_by_key = {key: dict(value) for key, value in METRIC_PRESETS.items()}
            self.selected_metric_name = ""
            self.selected_metric_unit = ""
            self.selected_metric_key = "gap"
            self.selected_metric_label = "Люфт"
            self.selected_metric_info = "Сначала выберите компонент"
            self.selected_unit_info = "Единица измерения не выбрана"
            return
        self.selected_component_id = component["component_id"]
        self.selected_component_info = (
            f"{component['equipment_name']} | {component['component_name']}"
        )
        options = component.get("measurement_options") or DEFAULT_MEASUREMENT_OPTIONS
        self.metric_options_by_key = self._merge_measurement_options(options)
        self.select_metric(self.selected_metric_key or "gap")

    def _merge_measurement_options(self, options):
        by_key = {key: dict(value) for key, value in METRIC_PRESETS.items()}
        for option in options or []:
            key = self._metric_key_for_name(option.get("parameter_name", ""))
            if key:
                merged = dict(by_key[key])
                merged.update({name: value for name, value in option.items() if value is not None})
                by_key[key] = merged
        return by_key

    def _metric_key_for_name(self, metric_name):
        name = (metric_name or "").strip().lower()
        if any(token in name for token in ("люфт", "зазор", "gap")):
            return "gap"
        if any(token in name for token in ("темпера", "temperature", "temp")):
            return "temperature"
        if any(token in name for token in ("давлен", "pressure")):
            return "pressure"
        if any(token in name for token in ("вибрац", "vibration")):
            return "vibration"
        return ""

    def _apply_metric_option(self, metric_key, option):
        if not option:
            self.selected_metric_name = ""
            self.selected_metric_unit = ""
            self.selected_metric_key = ""
            self.selected_metric_label = "Показатель не выбран"
            self.selected_metric_info = "Показатель не выбран"
            self.selected_unit_info = "Единица измерения не выбрана"
            self.on_measurement_value_change(self.ids.value_input.text if "value_input" in self.ids else "")
            return
        self.selected_metric_key = metric_key
        self.selected_metric_label = self._metric_label_for_key(metric_key)
        self.selected_metric_name = option.get("parameter_name") or ""
        self.selected_metric_unit = option.get("unit") or "ед."
        min_value = option.get("min_value")
        max_value = option.get("max_value")
        self.selected_metric_info = f"Выбрано: {self.selected_metric_name}"
        if min_value is not None and max_value is not None:
            self.selected_metric_info += f" | норма {min_value} - {max_value} {self.selected_metric_unit}"
        else:
            self.selected_metric_info += " | норма не задана"
        self.selected_unit_info = f"Единица измерения: {self.selected_metric_unit}"
        if "value_input" in self.ids:
            self.on_measurement_value_change(self.ids.value_input.text)

    def select_metric(self, metric_key):
        if metric_key not in METRIC_PRESETS:
            self.output_text = f"Показатель недоступен: {metric_key}"
            return
        option = self.metric_options_by_key.get(metric_key) or METRIC_PRESETS[metric_key]
        self._apply_metric_option(metric_key, option)
        self.output_text = f"Выбран показатель: {self.selected_metric_name}"

    def select_metric_label(self, label):
        labels = {
            "Люфт": "gap",
            "Температура": "temperature",
            "Давление": "pressure",
            "Вибрация": "vibration",
        }
        metric_key = labels.get(label)
        if metric_key:
            self.select_metric(metric_key)

    def _metric_label_for_key(self, metric_key):
        labels = {
            "gap": "Люфт",
            "temperature": "Температура",
            "pressure": "Давление",
            "vibration": "Вибрация",
        }
        return labels.get(metric_key, "Показатель не выбран")

    def numeric_input_filter(self, substring, from_undo):
        allowed = "0123456789-.,"
        return "".join(char for char in substring if char in allowed)

    def on_measurement_value_change(self, raw_text):
        raw_value = (raw_text or "").strip()
        if not raw_value:
            self.measurement_value_info = f"Введите значение, единица: {self.selected_metric_unit or '-'}"
            return
        try:
            value = float(raw_value.replace(",", "."))
        except ValueError:
            self.measurement_value_info = "Значение должно быть числом"
            return
        unit = self.selected_metric_unit or "-"
        metric = self.selected_metric_name or "показатель"
        self.measurement_value_info = f"Будет отправлено: {metric} = {value:g} {unit}"

    def clear_measurement_value(self):
        self.ids.value_input.text = ""
        self.on_measurement_value_change("")
        self.output_text = "Значение очищено"

    def _measurement_value(self):
        raw_value = self.ids.value_input.text.strip().replace(",", ".")
        if not raw_value:
            raise ValueError("Заполните значение измерения")
        return float(raw_value)

    def adjust_measurement_value(self, delta):
        try:
            value = self._measurement_value()
        except ValueError:
            value = 0.0
        value += float(delta)
        self.ids.value_input.text = f"{value:.2f}".rstrip("0").rstrip(".")
        self.output_text = f"Значение изменено: {self.ids.value_input.text}"

    def send_measurement(self):
        if not self.selected_component_id:
            self.output_text = "Сначала выберите оборудование и компонент"
            return
        if not self.selected_metric_name:
            self.output_text = "Сначала выберите показатель измерения"
            return
        if not self.selected_metric_unit:
            self.output_text = "Для выбранного показателя не задана единица измерения"
            return
        try:
            value = self._measurement_value()
        except ValueError:
            self.output_text = "Значение должно быть числом. Можно использовать точку или запятую."
            return
        payload = [
            {
                "component_id": int(self.selected_component_id),
                "metric_name": self.selected_metric_name,
                "value": value,
                "unit": self.selected_metric_unit,
            }
        ]
        self.request(
            "/bff/mobile/metrolog/measurements",
            method="POST",
            payload=payload,
            on_success=self._on_measurement_saved,
        )

    def _on_measurement_saved(self, _req, result):
        components = result.get("query", {}).get("components", [])
        if components:
            self._on_components_loaded(_req, components)
        command = result.get("command", result)
        self.output_text = json.dumps(command, ensure_ascii=False, indent=2)

    def load_mechanic_tasks(self):
        self.request("/bff/mobile/tasks", on_success=self._on_mechanic_tasks_loaded)

    def _on_mechanic_tasks_loaded(self, _req, result):
        result = result or []
        self.mechanic_tasks_by_label = {
            (
                f"#{item['task_id']} | {self._status_label(item.get('status'))} | "
                f"{item.get('equipment_name', '')}"
            ): item
            for item in result
        }
        labels = list(self.mechanic_tasks_by_label.keys())
        self.ids.mechanic_task_spinner.values = labels
        if labels:
            self.ids.mechanic_task_spinner.text = labels[0]
            self.select_mechanic_task(labels[0])
        else:
            self.ids.mechanic_task_spinner.text = "Нет задач"
            self.selected_mechanic_task_id = None
            self.selected_mechanic_task_status = ""
            self.selected_mechanic_task_info = "Для механика нет доступных задач"
            self.mechanic_action_hint = "Когда появится задача, она будет доступна здесь"
        self.output_text = f"Задачи механика загружены: {len(result)}"

    def select_mechanic_task(self, label):
        task = self.mechanic_tasks_by_label.get(label)
        if not task:
            self.selected_mechanic_task_id = None
            self.selected_mechanic_task_status = ""
            self.selected_mechanic_task_info = "Задача не выбрана"
            self.mechanic_action_hint = "Выберите задачу, чтобы увидеть доступные действия"
            return
        self.selected_mechanic_task_id = task["task_id"]
        self.selected_mechanic_task_status = task.get("status") or ""
        self.selected_mechanic_task_info = (
            f"#{task.get('task_id')} | {task.get('equipment_name', '')} | "
            f"{self._status_label(task.get('status'))}\n{task.get('description', '')}"
        )
        self.mechanic_action_hint = self._mechanic_action_hint(task.get("status"))

    def mechanic_action(self, action):
        if not self.selected_mechanic_task_id:
            self.output_text = "Сначала загрузите и выберите задачу механика"
            return
        if not self._is_mechanic_action_allowed(action, self.selected_mechanic_task_status):
            self.output_text = self._mechanic_action_hint(self.selected_mechanic_task_status)
            return
        payload = {"result": self.ids.mechanic_result.text.strip()} if action == "finish" else {}
        if action == "finish" and not payload["result"]:
            self.output_text = "Для завершения задачи заполните результат"
            return
        task_id = int(self.selected_mechanic_task_id)
        self.request(
            f"/bff/mobile/mechanic/tasks/{task_id}/{action}",
            method="POST",
            payload=payload,
            on_success=self._on_mechanic_action_done,
        )

    def _on_mechanic_action_done(self, _req, result):
        tasks = result.get("query", {}).get("tasks", [])
        self._on_mechanic_tasks_loaded(_req, tasks)
        command = result.get("command", {})
        self.output_text = (
            f"Задача #{command.get('id', self.selected_mechanic_task_id)}: "
            f"{self._status_label(command.get('status'))}"
        )

    def load_quality_tasks(self):
        self.request("/bff/mobile/quality/tasks", on_success=self._on_quality_tasks_loaded)

    def _on_quality_tasks_loaded(self, _req, result):
        result = result or []
        self.quality_tasks_by_label = {
            (
                f"#{item['task_id']} | {self._status_label(item.get('status'))} | "
                f"{item.get('equipment_name', '')}"
            ): item
            for item in result
        }
        labels = list(self.quality_tasks_by_label.keys())
        self.ids.quality_task_spinner.values = labels
        if labels:
            self.ids.quality_task_spinner.text = labels[0]
            self.select_quality_task(labels[0])
        else:
            self.ids.quality_task_spinner.text = "Нет задач"
            self.selected_quality_task_id = None
            self.selected_quality_task_status = ""
            self.selected_quality_task_info = "Нет завершённых задач для проверки"
            self.quality_action_hint = "После завершения задач механиком они появятся здесь"
        self.output_text = f"Задачи на проверку загружены: {len(result)}"

    def select_quality_task(self, label):
        task = self.quality_tasks_by_label.get(label)
        if not task:
            self.selected_quality_task_id = None
            self.selected_quality_task_status = ""
            self.selected_quality_task_info = "Задача не выбрана"
            self.quality_action_hint = "Выберите завершённую задачу для проверки"
            return
        self.selected_quality_task_id = task["task_id"]
        self.selected_quality_task_status = task.get("status") or ""
        self.selected_quality_task_info = (
            f"#{task.get('task_id')} | {task.get('equipment_name', '')} | "
            f"{self._status_label(task.get('status'))}\n{task.get('description', '')}"
        )
        self.quality_action_hint = "Выберите результат проверки и сохраните"

    def submit_quality_check(self):
        if not self.selected_quality_task_id:
            self.output_text = "Сначала загрузите и выберите задачу для проверки"
            return
        notes = self.ids.quality_notes.text.strip()
        if not notes:
            self.output_text = "Заполните примечание проверки"
            return
        task_id = int(self.selected_quality_task_id)
        payload = {
            "status": self.ids.quality_status.text,
            "notes": notes,
        }
        self.request(
            f"/bff/mobile/quality/tasks/{task_id}/check",
            method="POST",
            payload=payload,
            on_success=self._on_quality_check_done,
        )

    def _on_quality_check_done(self, _req, result):
        tasks = result.get("query", {}).get("quality_tasks", [])
        self._on_quality_tasks_loaded(_req, tasks)
        command = result.get("command", {})
        self.output_text = f"Проверка сохранена для задачи #{command.get('task_id', self.selected_quality_task_id)}"

    def _status_label(self, status):
        labels = {
            "created": "Создана",
            "active": "В работе",
            "completed": "Завершена",
            "cancelled": "Отменена",
            "queued": "В очереди",
            "in_progress": "Выполняется",
            "passed": "Пройдена",
            "failed": "Ошибка",
            "needs_rework": "Нужна доработка",
        }
        return labels.get(status, status or "-")

    def _mechanic_action_hint(self, status):
        if status == "created":
            return "Доступно: Start"
        if status == "active":
            return "Доступно: Finish или Cancel"
        if status == "completed":
            return "Задача уже завершена"
        if status == "cancelled":
            return "Задача отменена"
        return "Для задачи нет доступных действий"

    def _is_mechanic_action_allowed(self, action, status):
        if action == "start":
            return status == "created"
        if action in {"finish", "cancel"}:
            return status == "active"
        return False

    def _on_success(self, _req, result):
        self.output_text = json.dumps(result, ensure_ascii=False, indent=2)

    def _on_error(self, req, error):
        body = getattr(req, "result", None)
        if isinstance(body, dict):
            detail = body.get("detail") or body.get("message") or body
            self.output_text = json.dumps({"error": detail}, ensure_ascii=False, indent=2)
        else:
            self.output_text = f"Ошибка: {error}"


class MobileClientApp(App):
    def build(self):
        preview_size = os.getenv("MOBILE_PREVIEW_SIZE")
        if preview_size and platform not in {"android", "ios"}:
            width, height = preview_size.lower().split("x", 1)
            Window.size = (int(width), int(height))
        Window.softinput_mode = "below_target"
        Builder.load_string(KV)
        return MobileRoot()


if __name__ == "__main__":
    MobileClientApp().run()
