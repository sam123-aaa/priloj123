const METRICS = {
  gap: { label: "Люфт", parameter_name: "Люфт", unit: "мм" },
  temperature: { label: "Температура", parameter_name: "Отклонение температуры", unit: "C" },
  pressure: { label: "Давление", parameter_name: "Давление", unit: "бар" },
  vibration: { label: "Вибрация", parameter_name: "Вибрация", unit: "мм/с" },
};

const state = {
  token: localStorage.getItem("mobile_token") || "",
  role: localStorage.getItem("mobile_role") || "",
  components: [],
  mechanicTasks: [],
  qualityTasks: [],
};

const $ = (id) => document.getElementById(id);

function defaultApiBase() {
  const saved = localStorage.getItem("mobile_api_base");
  if (saved) return saved;
  if (["capacitor:", "file:", "https:"].includes(location.protocol)) return "http://10.0.2.2:8000";
  return "http://127.0.0.1:8000";
}

function setToast(message, isError = false) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.toggle("is-error", isError);
  toast.classList.remove("hidden");
  clearTimeout(setToast.timer);
  setToast.timer = setTimeout(() => toast.classList.add("hidden"), 2400);
}

function saveSession() {
  localStorage.setItem("mobile_token", state.token);
  localStorage.setItem("mobile_role", state.role);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json; charset=utf-8", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(`${$("apiBaseInput").value.replace(/\/$/, "")}${path}`, { ...options, headers });
  const text = await response.text();
  let body = text;
  try { body = text ? JSON.parse(text) : null; } catch (_) {}
  if (!response.ok) {
    const detail = body?.detail || body?.message || text || `HTTP ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

function showRolePanels() {
  $("workspace").classList.toggle("hidden", !state.token);
  $("logoutButton").classList.toggle("hidden", !state.token);
  $("sessionBadge").textContent = state.token ? `Роль: ${state.role}` : "Не авторизован";
  const role = state.role;
  const tabButtons = document.querySelectorAll(".tab");
  tabButtons.forEach((button) => {
    const tab = button.dataset.tab;
    const allowed =
      role === "admin" ||
      (tab === "measurements" && role === "metrologist") ||
      (tab === "mechanic" && role === "mechanic") ||
      (tab === "quality" && role === "quality_engineer");
    button.hidden = !allowed;
  });
  const firstAllowed = [...tabButtons].find((button) => !button.hidden);
  if (firstAllowed) activateTab(firstAllowed.dataset.tab);
}

function activateTab(tab) {
  document.querySelectorAll(".tab").forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
  document.querySelectorAll(".panel").forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === tab));
}

function option(label, value) {
  const item = document.createElement("option");
  item.value = value ?? "";
  item.textContent = label;
  return item;
}

function selectedComponent() {
  return state.components.find((item) => String(item.component_id) === $("componentSelect").value);
}

function selectedMetric() {
  const component = selectedComponent();
  const key = $("metricSelect").value;
  const base = { ...METRICS[key] };
  const options = component?.measurement_options || [];
  const match = options.find((item) => metricKey(item.parameter_name) === key);
  return { ...base, ...(match || {}) };
}

function metricKey(name = "") {
  const lower = name.toLowerCase();
  if (lower.includes("люфт") || lower.includes("gap")) return "gap";
  if (lower.includes("темпера") || lower.includes("temp")) return "temperature";
  if (lower.includes("давлен") || lower.includes("pressure")) return "pressure";
  if (lower.includes("вибрац") || lower.includes("vibration")) return "vibration";
  return "";
}

function updateMetricInfo() {
  const component = selectedComponent();
  if (!component) {
    $("metricInfo").textContent = "Компонент не выбран";
    return;
  }
  const metric = selectedMetric();
  $("metricInfo").textContent = `${component.equipment_name || ""} | ${component.component_name || ""} | ${metric.parameter_name} (${metric.unit})`;
}

async function loadComponents() {
  $("measurementResult").textContent = "Загрузка компонентов...";
  const rows = await api("/bff/mobile/components");
  state.components = Array.isArray(rows) ? rows : rows?.components || [];
  const select = $("componentSelect");
  select.replaceChildren();
  if (!state.components.length) {
    select.append(option("Нет компонентов", ""));
  } else {
    state.components.forEach((item) => select.append(option(`${item.equipment_name || "Оборудование"} | ${item.component_name}`, item.component_id)));
  }
  updateMetricInfo();
  $("measurementResult").textContent = `Компонентов загружено: ${state.components.length}`;
}

async function sendMeasurement() {
  const component = selectedComponent();
  if (!component) throw new Error("Выберите компонент");
  const metric = selectedMetric();
  const value = Number(String($("measurementValue").value).replace(",", "."));
  if (!Number.isFinite(value)) throw new Error("Введите числовое значение");
  const result = await api("/bff/mobile/metrolog/measurements", {
    method: "POST",
    body: JSON.stringify([{ component_id: Number(component.component_id), metric_name: metric.parameter_name, value, unit: metric.unit }]),
  });
  $("measurementResult").textContent = JSON.stringify(result.command || result, null, 2);
}

function renderTaskSelect(selectId, rows) {
  const select = $(selectId);
  select.replaceChildren();
  if (!rows.length) {
    select.append(option("Нет задач", ""));
    return;
  }
  rows.forEach((task) => select.append(option(`#${task.task_id} | ${task.status} | ${task.equipment_name || ""}`, task.task_id)));
}

function selectedTask(rows, selectId) {
  return rows.find((item) => String(item.task_id) === $(selectId).value);
}

function updateTaskInfo() {
  const mechanic = selectedTask(state.mechanicTasks, "mechanicTaskSelect");
  $("mechanicTaskInfo").textContent = mechanic ? `#${mechanic.task_id} | ${mechanic.status} | ${mechanic.description || ""}` : "Задача не выбрана";
  const quality = selectedTask(state.qualityTasks, "qualityTaskSelect");
  $("qualityTaskInfo").textContent = quality ? `#${quality.task_id} | ${quality.status} | ${quality.description || ""}` : "Задача не выбрана";
}

async function loadMechanicTasks() {
  $("mechanicOutput").textContent = "Загрузка задач...";
  state.mechanicTasks = await api("/bff/mobile/tasks");
  renderTaskSelect("mechanicTaskSelect", state.mechanicTasks);
  updateTaskInfo();
  $("mechanicOutput").textContent = `Задач загружено: ${state.mechanicTasks.length}`;
}

async function mechanicAction(action) {
  const task = selectedTask(state.mechanicTasks, "mechanicTaskSelect");
  if (!task) throw new Error("Выберите задачу механика");
  const body = action === "finish" ? { result: $("mechanicResult").value.trim() } : {};
  if (action === "finish" && !body.result) throw new Error("Заполните результат");
  const result = await api(`/bff/mobile/mechanic/tasks/${task.task_id}/${action}`, { method: "POST", body: JSON.stringify(body) });
  $("mechanicOutput").textContent = JSON.stringify(result.command || result, null, 2);
  await loadMechanicTasks();
}

async function loadQualityTasks() {
  $("qualityOutput").textContent = "Загрузка проверок...";
  state.qualityTasks = await api("/bff/mobile/quality/tasks");
  renderTaskSelect("qualityTaskSelect", state.qualityTasks);
  updateTaskInfo();
  $("qualityOutput").textContent = `Задач загружено: ${state.qualityTasks.length}`;
}

async function saveQuality() {
  const task = selectedTask(state.qualityTasks, "qualityTaskSelect");
  if (!task) throw new Error("Выберите задачу для проверки");
  const payload = { status: $("qualityStatus").value, notes: $("qualityNotes").value.trim() };
  if (!payload.notes) throw new Error("Заполните примечание");
  const result = await api(`/bff/mobile/quality/tasks/${task.task_id}/check`, { method: "POST", body: JSON.stringify(payload) });
  $("qualityOutput").textContent = JSON.stringify(result.command || result, null, 2);
  await loadQualityTasks();
}

function logout() {
  state.token = "";
  state.role = "";
  saveSession();
  showRolePanels();
  $("loginCard").classList.remove("hidden");
  setToast("Вы вышли из сессии");
}

async function guarded(fn) {
  try {
    await fn();
  } catch (error) {
    setToast(error.message, true);
  }
}

function bindEvents() {
  $("apiBaseInput").value = defaultApiBase();
  $("loginForm").addEventListener("submit", (event) => guarded(async () => {
    event.preventDefault();
    localStorage.setItem("mobile_api_base", $("apiBaseInput").value.replace(/\/$/, ""));
    $("loginButton").disabled = true;
    $("loginButton").textContent = "Вход...";
    try {
      const result = await api("/login", { method: "POST", body: JSON.stringify({ email: $("emailInput").value, password: $("passwordInput").value }) });
      state.token = result.access_token;
      state.role = typeof result.role === "string" ? result.role : result.role?.code || "";
      saveSession();
      $("loginCard").classList.add("hidden");
      showRolePanels();
      setToast(`Вход выполнен: ${state.role}`);
      if (state.role === "metrologist" || state.role === "admin") await loadComponents();
      if (state.role === "mechanic" || state.role === "admin") await loadMechanicTasks();
      if (state.role === "quality_engineer" || state.role === "admin") await loadQualityTasks();
    } finally {
      $("loginButton").disabled = false;
      $("loginButton").textContent = "Войти";
    }
  }));
  $("logoutButton").addEventListener("click", logout);
  document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => activateTab(button.dataset.tab)));
  $("refreshComponents").addEventListener("click", () => guarded(loadComponents));
  $("componentSelect").addEventListener("change", updateMetricInfo);
  $("metricSelect").addEventListener("change", updateMetricInfo);
  document.querySelectorAll(".stepper button").forEach((button) => button.addEventListener("click", () => {
    const current = Number(String($("measurementValue").value || "0").replace(",", ".")) || 0;
    $("measurementValue").value = Number(current + Number(button.dataset.delta)).toFixed(2).replace(/\.?0+$/, "");
  }));
  $("clearValue").addEventListener("click", () => { $("measurementValue").value = ""; });
  $("sendMeasurement").addEventListener("click", () => guarded(sendMeasurement));
  $("refreshMechanicTasks").addEventListener("click", () => guarded(loadMechanicTasks));
  $("mechanicTaskSelect").addEventListener("change", updateTaskInfo);
  document.querySelectorAll("[data-action]").forEach((button) => button.addEventListener("click", () => guarded(() => mechanicAction(button.dataset.action))));
  $("refreshQualityTasks").addEventListener("click", () => guarded(loadQualityTasks));
  $("qualityTaskSelect").addEventListener("change", updateTaskInfo);
  $("saveQuality").addEventListener("click", () => guarded(saveQuality));
}

bindEvents();
showRolePanels();
if (state.token) $("loginCard").classList.add("hidden");
