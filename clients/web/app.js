const STORAGE_KEY = "manager_web_api_base";
const DEBUG_KEY = "manager_web_debug";
const AUTH_TOKEN_KEY = "manager_web_token";
const AUTH_ROLE_KEY = "manager_web_role";

const ROLE_META = {
  guest: {
    badge: "Гость",
    shellTitle: "Управленческая панель",
    shellCopy: "",
    heroEyebrow: "MANAGER WEB",
    heroTitle: "Анализ показателей и шаблоны отчётов",
    heroCopy: "",
  },
  manager: {
    badge: "Менеджер",
    shellTitle: "Управленческая панель",
    shellCopy: "",
    heroEyebrow: "MANAGER WEB",
    heroTitle: "Анализ показателей и шаблоны отчётов",
    heroCopy: "",
  },
  tech_expert: {
    badge: "Эксперт",
    shellTitle: "Экспертная панель",
    shellCopy: "",
    heroEyebrow: "EXPERT WEB",
    heroTitle: "Неисправности и рекомендации",
    heroCopy: "",
  },
  dispatcher_specialist: {
    badge: "Диспетчер",
    shellTitle: "Диспетчерская панель",
    shellCopy: "",
    heroEyebrow: "DISPATCHER WEB",
    heroTitle: "Планы обслуживания и мониторинг",
    heroCopy: "",
  },
  admin: {
    badge: "Админ",
    shellTitle: "Административная панель",
    shellCopy: "",
    heroEyebrow: "ADMIN WEB",
    heroTitle: "Сводный контроль по всем ролям",
    heroCopy: "",
  },
};

const state = {
  token: "",
  role: "",
  templates: [],
  faults: [],
  recommendations: [],
  reportJobs: [],
  managerQuery: {},
  activeTaskId: "",
  reportPollTimer: null,
  syncPollTimer: null,
  syncVersion: "",
  interactions: {
    dashboard: 0,
    templates: 0,
    queue: 0,
    queue_now: 0,
    queue_later: 0,
    open_docx: 0,
  },
};

function apiBase() {
  return localStorage.getItem(STORAGE_KEY) || "http://127.0.0.1:8000";
}

function persistSession() {
  if (!state.token || !state.role) {
    return;
  }
  localStorage.setItem(AUTH_TOKEN_KEY, state.token);
  localStorage.setItem(AUTH_ROLE_KEY, state.role);
}

function clearPersistedSession() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_ROLE_KEY);
}

function restorePersistedSession() {
  state.token = localStorage.getItem(AUTH_TOKEN_KEY) || "";
  state.role = localStorage.getItem(AUTH_ROLE_KEY) || "";
  return Boolean(state.token && state.role);
}

function isDebugEnabled() {
  const params = new URLSearchParams(window.location.search);
  return params.get("debug") === "1" || localStorage.getItem(DEBUG_KEY) === "1";
}

function applyDebugVisibility() {
  const panel = document.getElementById("debugPanel");
  if (panel) {
    panel.classList.toggle("hidden", !isDebugEnabled());
  }
}

function hasRole(...roles) {
  return state.role === "admin" || roles.includes(state.role);
}

function setError(message) {
  const box = document.getElementById("errorBox");
  if (!box) {
    return;
  }
  if (!message) {
    box.classList.add("hidden");
    box.textContent = "";
    return;
  }
  box.textContent = message;
  box.classList.remove("hidden");
}

function setReportMessage(message, isError = false) {
  const target = document.getElementById("reportResult");
  if (!target) {
    return;
  }
  target.textContent = message || "";
  target.classList.toggle("inline-error", Boolean(isError));
}

function renderJsonBox(targetId, value, emptyMessage) {
  const target = document.getElementById(targetId);
  if (!target) {
    return;
  }
  if (!value || (Array.isArray(value) && value.length === 0)) {
    target.textContent = emptyMessage;
    target.classList.add("empty-state");
    return;
  }
  target.textContent = JSON.stringify(value, null, 2);
  target.classList.remove("empty-state");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatCell(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "object") {
    return `<pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
  }
  return escapeHtml(value);
}

function renderTable(targetId, rows, emptyMessage = "Нет данных") {
  const target = document.getElementById(targetId);
  if (!target) {
    return;
  }
  if (!rows || rows.length === 0) {
    target.innerHTML = `<div class="empty-state">${escapeHtml(emptyMessage)}</div>`;
    return;
  }
  const columns = Object.keys(rows[0]);
  target.innerHTML = `
    <table>
      <thead>
        <tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr>
      </thead>
      <tbody>
        ${rows.map((row) => `<tr>${columns.map((column) => `<td>${formatCell(row[column])}</td>`).join("")}</tr>`).join("")}
      </tbody>
    </table>
  `;
}

function humanizeTemplateParams(payload) {
  if (!payload || typeof payload !== "object") {
    return "Без дополнительных параметров.";
  }
  const lines = [];
  if (payload.period === "day") {
    lines.push("Период: текущие сутки.");
  }
  if (payload.scope === "quality") {
    lines.push("Фокус: проверки качества и завершённые задачи.");
  }
  if (payload.scope === "faults") {
    lines.push("Фокус: открытые и обработанные неисправности.");
  }
  return lines.length ? lines.join(" ") : "Параметры задаются автоматически.";
}

function workTemplatePurpose(item) {
  const type = item.report_type || "";
  if (type === "daily-overview") {
    return "Подходит для ежедневной оперативной сводки по оборудованию, неисправностям и задачам за смену.";
  }
  if (type === "quality-summary") {
    return "Используется для контроля качества, проверки завершённых задач и оценки результатов обслуживания.";
  }
  if (type === "fault-analysis") {
    return "Нужен для анализа накопленных неисправностей, повторяющихся проблем и приоритизации работ.";
  }
  return item.description || "Рабочий шаблон отчёта для управленческой сводки.";
}

function renderTemplateCards(rows) {
  const target = document.getElementById("reportTemplates");
  if (!target) {
    return;
  }
  if (!rows || rows.length === 0) {
    target.innerHTML = "<div class='empty-state'>Нет шаблонов</div>";
    return;
  }
  target.classList.remove("empty-state");
  target.innerHTML = `
    <div class="template-list">
      ${rows
        .map(
          (item) => `
            <article class="template-card">
              <div class="template-card-head">
                <h3>${escapeHtml(item.template_name || item.name || "Шаблон отчёта")}</h3>
                <span class="template-type">${escapeHtml(item.report_type || "report")}</span>
              </div>
              <p><strong>Назначение:</strong> ${escapeHtml(workTemplatePurpose(item))}</p>
              <p><strong>Что попадёт в отчёт:</strong> ${escapeHtml(item.description || "Содержимое определяется шаблоном.")}</p>
              <p><strong>Параметры запуска:</strong> ${escapeHtml(humanizeTemplateParams(item.default_payload))}</p>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function setOptions(selectId, rows, valueKey, labelBuilder, emptyLabel) {
  const select = document.getElementById(selectId);
  if (!select) {
    return;
  }
  if (!rows || rows.length === 0) {
    select.innerHTML = `<option value="">${escapeHtml(emptyLabel)}</option>`;
    select.disabled = true;
    return;
  }
  select.disabled = false;
  select.innerHTML = rows
    .map((row) => `<option value="${escapeHtml(row[valueKey])}">${escapeHtml(labelBuilder(row))}</option>`)
    .join("");
}

function trackInteraction(actionKey, amount = 1) {
  if (!(actionKey in state.interactions)) {
    return;
  }
  state.interactions[actionKey] += amount;
  renderManagerDashboard();
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (state.token) {
    headers.set("Authorization", `Bearer ${state.token}`);
  }

  let response;
  try {
    response = await fetch(`${apiBase()}${path}`, { ...options, headers });
  } catch (_error) {
    throw new Error("Backend недоступен. Подними FastAPI на http://127.0.0.1:8000");
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail || body.message || body.error || `HTTP ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail, null, 2));
  }
  return body;
}

function currentRoleMeta() {
  return ROLE_META[state.role] || ROLE_META.guest;
}

function applyRolePresentation() {
  const meta = currentRoleMeta();
  document.body.classList.remove("role-guest", "role-manager", "role-tech_expert", "role-dispatcher_specialist", "role-admin");
  document.body.classList.add(`role-${state.role || "guest"}`);
  document.getElementById("roleBadge").textContent = meta.badge;
  document.getElementById("shellTitle").textContent = meta.shellTitle;
  document.getElementById("shellCopy").textContent = meta.shellCopy;
  document.getElementById("heroEyebrow").textContent = meta.heroEyebrow;
  document.getElementById("heroTitle").textContent = meta.heroTitle;
  document.getElementById("heroCopy").textContent = meta.heroCopy;
  document.getElementById("sessionInfo").textContent = state.token ? `Роль: ${state.role}` : "Не авторизован";

  document.getElementById("managerPanel").classList.toggle("hidden", !hasRole("manager"));
  document.getElementById("monitoringPanel").classList.toggle("hidden", !hasRole("tech_expert", "dispatcher_specialist"));
  document.getElementById("expertPanel").classList.toggle("hidden", !hasRole("tech_expert"));
  document.getElementById("dispatcherPanel").classList.toggle("hidden", !hasRole("dispatcher_specialist"));
}

function stopReportPolling() {
  if (!state.reportPollTimer) {
    return;
  }
  clearInterval(state.reportPollTimer);
  state.reportPollTimer = null;
}

function stopSyncPolling() {
  if (!state.syncPollTimer) {
    return;
  }
  clearInterval(state.syncPollTimer);
  state.syncPollTimer = null;
}

function resetRoleData() {
  state.templates = [];
  state.faults = [];
  state.recommendations = [];
  state.reportJobs = [];
  state.managerQuery = {};
  state.activeTaskId = "";
  state.syncVersion = "";
  stopReportPolling();
  stopSyncPolling();

  renderManagerDashboard();
  renderTemplateCards([]);
  renderTable("desktopMonitoring", [], "Нет данных мониторинга");
  renderJsonBox("expertResult", null, "Действия эксперта появятся здесь.");
  renderJsonBox("dispatcherResult", null, "Действия диспетчера появятся здесь.");
  document.getElementById("activeReportStatus").textContent = "Текущий статус задачи появится здесь";
  document.getElementById("activeReportStatus").className = "live-status empty-state";
  document.getElementById("reportJobs").innerHTML = "<div class='empty-state'>Фоновых отчётов пока нет</div>";
  setOptions("templateSelect", [], "id", () => "", "Сначала загрузите шаблоны");
  setOptions("faultSelect", [], "id", () => "", "Сначала загрузите неисправности");
  setOptions("recommendationSelect", [], "recommendation_id", () => "", "Сначала загрузите рекомендации");
  setReportMessage("");
}

function selectedTemplate() {
  const value = document.getElementById("templateSelect").value;
  if (!value) {
    throw new Error("Сначала выберите шаблон отчёта.");
  }
  return state.templates.find((item) => String(item.id) === String(value)) || null;
}

function selectedReportPayload() {
  const template = selectedTemplate();
  return { template_id: Number(template.id) };
}

function selectedDelaySeconds() {
  const value = Number(document.getElementById("delayValue").value);
  const unit = document.getElementById("delayUnit").value;
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error("Задержка должна быть больше 0.");
  }
  const multiplier = unit === "hours" ? 3600 : unit === "minutes" ? 60 : 1;
  return Math.round(value * multiplier);
}

function selectedFaultId() {
  const value = Number(document.getElementById("faultSelect").value);
  if (!value) {
    throw new Error("Сначала загрузите и выберите неисправность.");
  }
  return value;
}

function selectedRecommendationId() {
  const value = Number(document.getElementById("recommendationSelect").value);
  if (!value) {
    throw new Error("Сначала загрузите и выберите рекомендацию.");
  }
  return value;
}

function statusLabel(status) {
  const labels = {
    queued: "В очереди",
    in_progress: "Выполняется",
    completed: "Завершён",
    failed: "Ошибка",
  };
  return labels[status] || status;
}

function formatDate(value) {
  if (!value) {
    return "Нет запусков";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function renderManagerDashboard(query = state.managerQuery) {
  const target = document.getElementById("webDashboard");
  if (!target) {
    return;
  }

  const templates = query.templates || state.templates || [];
  const jobs = query.recent_reports || state.reportJobs || [];
  const dashboardRows = query.dashboard || [];
  const completedCount = jobs.filter((item) => item.status === "completed").length;
  const queuedCount = jobs.filter((item) => item.status === "queued").length;
  const inProgressCount = jobs.filter((item) => item.status === "in_progress").length;
  const failedCount = jobs.filter((item) => item.status === "failed").length;
  const lastJob = jobs[0] || dashboardRows[0] || null;
  const topLoad = Math.max(jobs.length, templates.length, 1);

  const stats = [
    { title: "Шаблоны", value: templates.length, note: "Активные шаблоны формирования отчётов" },
    { title: "В очереди", value: queuedCount, note: "Задачи ожидают выполнения" },
    { title: "Завершено", value: completedCount, note: "Готовые фоновые отчёты" },
    {
      title: "Последний запуск",
      value: jobs.length ? "Да" : "Нет",
      note: lastJob ? formatDate(lastJob.queued_at || lastJob.finished_at || lastJob.started_at) : "Отчёты ещё не запускались",
    },
  ];

  const queueOverview = [
    { label: "Очередь", value: queuedCount, width: Math.max(12, Math.round((queuedCount / topLoad) * 100)) },
    { label: "В работе", value: inProgressCount, width: Math.max(12, Math.round((inProgressCount / topLoad) * 100)) },
    { label: "Готово", value: completedCount, width: Math.max(12, Math.round((completedCount / topLoad) * 100)) },
    { label: "Ошибки", value: failedCount, width: Math.max(12, Math.round((failedCount / topLoad) * 100)) },
  ];

  target.innerHTML = `
    <section class="stat-grid">
      ${stats
        .map(
          (item) => `
            <article class="stat-card">
              <strong>${escapeHtml(item.title)}</strong>
              <div class="stat-value">${escapeHtml(item.value)}</div>
              <div class="stat-note">${escapeHtml(item.note)}</div>
            </article>
          `
        )
        .join("")}
    </section>
    <section class="dashboard-main">
      <article class="queue-card queue-card-full">
        <h3>Состояние очереди</h3>
        <p class="card-copy">Сводка по последним задачам формирования отчётов.</p>
        <div class="queue-list">
          ${queueOverview
            .map(
              (item) => `
                <div class="queue-row">
                  <div class="queue-meta">
                    <span>${escapeHtml(item.label)}</span>
                    <strong>${escapeHtml(item.value)}</strong>
                  </div>
                  <div class="queue-bar"><div class="queue-bar-fill" style="width:${item.width}%"></div></div>
                </div>
              `
            )
            .join("")}
        </div>
        <div class="queue-footnote">${escapeHtml(
          jobs.length ? `Последняя задача: ${formatDate(lastJob?.queued_at || lastJob?.finished_at || lastJob?.started_at)}` : "После запуска отчётов здесь появится живая сводка."
        )}</div>
      </article>
    </section>
  `;
}

function renderTemplateSelect(rows) {
  state.templates = rows || [];
  setOptions(
    "templateSelect",
    state.templates,
    "id",
    (item) => item.template_name || item.name || item.report_type || `Шаблон ${item.id}`,
    "Нет активных шаблонов"
  );
}

function renderFaultSelect(rows) {
  state.faults = rows || [];
  setOptions(
    "faultSelect",
    state.faults,
    "id",
    (item) => `#${item.id} | ${item.equipment_name || "-"} / ${item.component_name || "-"} | ${item.severity || "-"}`,
    "Нет доступных неисправностей"
  );
}

function renderRecommendationSelect(rows) {
  state.recommendations = rows || [];
  setOptions(
    "recommendationSelect",
    state.recommendations,
    "recommendation_id",
    (item) => `#${item.recommendation_id} | ${item.equipment_name || "-"} | ${item.priority || "-"}`,
    "Нет доступных рекомендаций"
  );
}

function renderActiveReportStatus(rows) {
  const box = document.getElementById("activeReportStatus");
  if (!state.activeTaskId) {
    box.className = "live-status empty-state";
    box.textContent = "Текущий статус задачи появится здесь";
    return;
  }
  const report = rows.find((item) => item.job_id === state.activeTaskId);
  if (!report) {
    box.className = "live-status status-queued";
    box.textContent = `Задача ${state.activeTaskId} поставлена в очередь. Ожидается обновление статуса.`;
    return;
  }
  box.className = `live-status status-${report.status}`;
  box.textContent = `Текущий отчёт: ${report.report_type}. Статус: ${statusLabel(report.status)}.`;
}

function openReportDocument(taskId) {
  if (!taskId) {
    setError("Сначала выберите готовый отчёт.");
    return;
  }
  window.open(`${apiBase()}/reports/document/${taskId}?token=${encodeURIComponent(state.token)}`, "_blank");
}

function renderReportJobs(rows) {
  const list = rows || [];
  state.reportJobs = list;
  renderActiveReportStatus(list);
  syncReportPolling(list);
  renderManagerDashboard();

  const target = document.getElementById("reportJobs");
  if (!target) {
    return;
  }
  if (!list.length) {
    target.innerHTML = "<div class='empty-state'>Фоновых отчётов пока нет</div>";
    return;
  }
  target.innerHTML = list
    .map((item) => {
      const documentButton = item.has_document
        ? `<button type="button" data-open-report="${escapeHtml(item.job_id)}">Открыть DOCX</button>`
        : "<span class='muted'>Документ появится после завершения</span>";
      return `
        <article class="report-card">
          <div>
            <div class="status-pill status-${escapeHtml(item.status)}">${escapeHtml(statusLabel(item.status))}</div>
            <h3>${escapeHtml(item.report_type)}</h3>
            <p class="muted">Задача: ${escapeHtml(item.job_id)}</p>
            <p class="muted">Поставлен: ${escapeHtml(item.queued_at || "-")} | Старт: ${escapeHtml(item.started_at || "-")} | Готов: ${escapeHtml(item.finished_at || "-")}</p>
          </div>
          <div class="report-actions">${documentButton}</div>
        </article>
      `;
    })
    .join("");
  target.querySelectorAll("[data-open-report]").forEach((button) => {
    button.addEventListener("click", () => {
      trackInteraction("open_docx");
      openReportDocument(button.dataset.openReport);
    });
  });
}

function syncReportPolling(rows) {
  if (!state.activeTaskId) {
    stopReportPolling();
    return;
  }
  const report = rows.find((item) => item.job_id === state.activeTaskId);
  if (!report || report.status === "queued" || report.status === "in_progress") {
    startReportPolling();
    return;
  }
  stopReportPolling();
}

function applyManagerQuery(query) {
  if (!query) {
    return;
  }
  state.managerQuery = query;
  if (query.templates) {
    renderTemplateSelect(query.templates);
    renderTemplateCards(query.templates);
  }
  if (query.recent_reports) {
    renderReportJobs(query.recent_reports);
  }
  renderManagerDashboard(query);
}

function applyMonitoringRows(rows) {
  renderTable("desktopMonitoring", rows || [], "Нет данных мониторинга");
}

async function loadManagerHome() {
  trackInteraction("dashboard");
  const result = await request("/bff/web/manager-home");
  applyManagerQuery(result);
}

async function loadTemplates() {
  trackInteraction("templates");
  setReportMessage("Загрузка шаблонов...");
  try {
    const rows = await request("/reports/templates");
    renderTemplateSelect(rows);
    renderTemplateCards(rows);
    renderManagerDashboard();
    setReportMessage(rows.length ? "Шаблоны загружены." : "API не вернул активные шаблоны.");
  } catch (error) {
    renderTemplateSelect([]);
    renderTemplateCards([]);
    renderManagerDashboard();
    setReportMessage(`Не удалось загрузить шаблоны: ${error.message}`, true);
    throw error;
  }
}

async function loadReportJobs() {
  trackInteraction("queue");
  const result = await request("/bff/web/reports?limit=30");
  renderReportJobs(result.reports || []);
}

async function queueReport(delaySeconds = 0) {
  const payload = selectedReportPayload();
  const result = await request("/bff/web/reports/generate", {
    method: "POST",
    body: JSON.stringify({ ...payload, delay_seconds: delaySeconds }),
  });
  state.activeTaskId = result.command.task_id;
  applyManagerQuery(result.query);
  await loadReportJobs();
  return result;
}

async function loadMonitoring() {
  const rows = await request("/bff/desktop/monitoring");
  applyMonitoringRows(rows);
}

async function loadFaults() {
  const rows = await request("/expert/faults");
  renderFaultSelect(rows);
  renderJsonBox("expertResult", rows, "Нет доступных неисправностей.");
}

async function createRecommendation() {
  const result = await request("/bff/desktop/expert/recommendations", {
    method: "POST",
    body: JSON.stringify({
      fault_id: selectedFaultId(),
      recommendation_text: document.getElementById("recommendationText").value,
      priority: document.getElementById("expertPriority").value,
    }),
  });
  if (result.query?.faults) {
    renderFaultSelect(result.query.faults);
  }
  if (result.query?.monitoring) {
    applyMonitoringRows(result.query.monitoring);
  }
  renderJsonBox("expertResult", result, "Действия эксперта появятся здесь.");
}

async function confirmFault() {
  const result = await request("/bff/desktop/expert/faults/confirm", {
    method: "POST",
    body: JSON.stringify({
      fault_ids: [selectedFaultId()],
      action: "confirm",
    }),
  });
  if (result.query?.faults) {
    renderFaultSelect(result.query.faults);
  }
  if (result.query?.monitoring) {
    applyMonitoringRows(result.query.monitoring);
  }
  renderJsonBox("expertResult", result, "Действия эксперта появятся здесь.");
}

async function loadDispatcherRecommendations() {
  const rows = await request("/specialist/recommendations");
  renderRecommendationSelect(rows);
  renderJsonBox("dispatcherResult", rows, "Нет доступных рекомендаций.");
}

async function createPlan() {
  const result = await request("/bff/desktop/dispatcher/plans", {
    method: "POST",
    body: JSON.stringify({
      recommendation_ids: [selectedRecommendationId()],
      planned_date: document.getElementById("planDate").value,
    }),
  });
  if (result.query?.recommendations) {
    renderRecommendationSelect(result.query.recommendations);
  }
  if (result.query?.monitoring) {
    applyMonitoringRows(result.query.monitoring);
  }
  renderJsonBox("dispatcherResult", result, "Действия диспетчера появятся здесь.");
}

function startReportPolling() {
  if (state.reportPollTimer) {
    return;
  }
  state.reportPollTimer = setInterval(() => {
    if (state.token && hasRole("manager")) {
      loadReportJobs().catch((error) => setError(error.message));
    }
  }, 5000);
}

async function fetchSyncState() {
  return request("/bff/sync?scope=web");
}

function startSyncPolling() {
  if (state.syncPollTimer || !state.token) {
    return;
  }
  state.syncPollTimer = setInterval(async () => {
    try {
      const snapshot = await fetchSyncState();
      if (!snapshot.version) {
        return;
      }
      if (!state.syncVersion) {
        state.syncVersion = snapshot.version;
        return;
      }
      if (state.syncVersion !== snapshot.version) {
        state.syncVersion = snapshot.version;
        await refreshRoleData();
      }
    } catch (error) {
      setError(error.message);
    }
  }, 4000);
}

async function refreshRoleData() {
  const jobs = [];
  if (hasRole("manager")) {
    jobs.push(loadManagerHome());
    jobs.push(loadReportJobs());
  }
  if (hasRole("tech_expert", "dispatcher_specialist")) {
    jobs.push(loadMonitoring());
  }
  if (hasRole("tech_expert")) {
    jobs.push(loadFaults());
  }
  if (hasRole("dispatcher_specialist")) {
    jobs.push(loadDispatcherRecommendations());
  }
  const results = await Promise.allSettled(jobs);
  const failure = results.find((item) => item.status === "rejected");
  if (failure) {
    throw failure.reason;
  }
}

function bindDebugPanel() {
  const apiBaseInput = document.getElementById("apiBaseInput");
  const saveApiBase = document.getElementById("saveApiBase");
  if (!apiBaseInput || !saveApiBase) {
    return;
  }
  apiBaseInput.value = apiBase();
  saveApiBase.addEventListener("click", () => {
    localStorage.setItem(STORAGE_KEY, apiBaseInput.value.trim().replace(/\/$/, ""));
  });
}

function bindDebugShortcut() {
  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "d") {
      const next = isDebugEnabled() ? "0" : "1";
      localStorage.setItem(DEBUG_KEY, next);
      applyDebugVisibility();
    }
  });
}

async function handleLogin(event) {
  event.preventDefault();
  try {
    setError("");
    resetRoleData();
    const form = new FormData(event.currentTarget);
    const result = await request("/login", {
      method: "POST",
      body: JSON.stringify({
        email: form.get("email"),
        password: form.get("password"),
      }),
    });
    state.token = result.access_token;
    state.role = result.role;
    persistSession();
    applyRolePresentation();
    const syncSnapshot = await fetchSyncState();
    state.syncVersion = syncSnapshot.version || "";
    await refreshRoleData();
    startSyncPolling();
  } catch (error) {
    state.token = "";
    state.role = "";
    clearPersistedSession();
    applyRolePresentation();
    resetRoleData();
    setError(error.message);
  }
}

async function bootstrapSession() {
  applyRolePresentation();
  resetRoleData();
  if (!restorePersistedSession()) {
    applyRolePresentation();
    return;
  }
  applyRolePresentation();
  try {
    const syncSnapshot = await fetchSyncState();
    state.syncVersion = syncSnapshot.version || "";
    await refreshRoleData();
    startSyncPolling();
  } catch (_error) {
    state.token = "";
    state.role = "";
    clearPersistedSession();
    applyRolePresentation();
    resetRoleData();
  }
}

function bindActions() {
  document.getElementById("loginForm").addEventListener("submit", handleLogin);
  document.getElementById("refreshDashboard").addEventListener("click", () => loadManagerHome().catch((error) => setError(error.message)));
  document.getElementById("refreshTemplates").addEventListener("click", () => loadTemplates().catch((error) => setError(error.message)));
  document.getElementById("refreshReports").addEventListener("click", () => loadReportJobs().catch((error) => setError(error.message)));
  document.getElementById("refreshMonitoring").addEventListener("click", () => loadMonitoring().catch((error) => setError(error.message)));
  document.getElementById("refreshFaults").addEventListener("click", () => loadFaults().catch((error) => setError(error.message)));
  document.getElementById("refreshRecommendations").addEventListener("click", () => loadDispatcherRecommendations().catch((error) => setError(error.message)));

  document.getElementById("queueReport").addEventListener("click", async () => {
    try {
      setError("");
      trackInteraction("queue_now");
      setReportMessage("Команда на формирование отчёта отправляется...");
      const template = selectedTemplate();
      await queueReport(0);
      setReportMessage(`Отчёт "${template ? template.template_name : "выбранный шаблон"}" поставлен в очередь.`);
    } catch (error) {
      setError(error.message);
      setReportMessage(error.message, true);
    }
  });

  document.getElementById("queueDelayedReport").addEventListener("click", async () => {
    try {
      setError("");
      trackInteraction("queue_later");
      setReportMessage("Команда на отложенное формирование отчёта отправляется...");
      const template = selectedTemplate();
      const delaySeconds = selectedDelaySeconds();
      await queueReport(delaySeconds);
      setReportMessage(`Отчёт "${template ? template.template_name : "выбранный шаблон"}" отложен на ${delaySeconds} сек.`);
    } catch (error) {
      setError(error.message);
      setReportMessage(error.message, true);
    }
  });

  document.getElementById("createRecommendation").addEventListener("click", () => {
    createRecommendation().catch((error) => {
      setError(error.message);
      renderJsonBox("expertResult", { error: error.message }, "Действия эксперта появятся здесь.");
    });
  });

  document.getElementById("confirmFault").addEventListener("click", () => {
    confirmFault().catch((error) => {
      setError(error.message);
      renderJsonBox("expertResult", { error: error.message }, "Действия эксперта появятся здесь.");
    });
  });

  document.getElementById("createPlan").addEventListener("click", () => {
    createPlan().catch((error) => {
      setError(error.message);
      renderJsonBox("dispatcherResult", { error: error.message }, "Действия диспетчера появятся здесь.");
    });
  });
}

bindDebugPanel();
bindDebugShortcut();
applyDebugVisibility();
bindActions();
bootstrapSession();
