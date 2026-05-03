const STORAGE_KEY = "manager_web_api_base";
const DEBUG_KEY = "manager_web_debug";

const ROLE_META = {
  guest: {
    badge: "Guest",
    shellTitle: "Operations Portal",
    shellCopy: "Use one web client for manager, tech expert, dispatcher specialist, and admin workflows.",
    heroEyebrow: "Unified Web",
    heroTitle: "Role-aware operations workspace",
    heroCopy: "The interface unlocks the same role actions that are available in the desktop client.",
  },
  manager: {
    badge: "Manager",
    shellTitle: "Manager Workspace",
    shellCopy: "Dashboard, report templates, and background report jobs are available here.",
    heroEyebrow: "Manager Web",
    heroTitle: "Plans, templates, and report queue",
    heroCopy: "The manager workflow now matches the desktop client feature set.",
  },
  tech_expert: {
    badge: "Tech Expert",
    shellTitle: "Expert Workspace",
    shellCopy: "Monitoring, fault review, confirmation, and recommendation actions are available on the web.",
    heroEyebrow: "Expert Web",
    heroTitle: "Review faults and create recommendations",
    heroCopy: "The tech expert workflow now matches the desktop client feature set.",
  },
  dispatcher_specialist: {
    badge: "Dispatcher",
    shellTitle: "Dispatcher Workspace",
    shellCopy: "Monitoring and plan creation from recommendations are available on the web.",
    heroEyebrow: "Dispatcher Web",
    heroTitle: "Turn recommendations into maintenance plans",
    heroCopy: "The dispatcher workflow now matches the desktop client feature set.",
  },
  admin: {
    badge: "Admin",
    shellTitle: "Admin Workspace",
    shellCopy: "Admin can access manager, tech expert, and dispatcher workflows in one web client.",
    heroEyebrow: "Admin Web",
    heroTitle: "Full cross-role control panel",
    heroCopy: "All role-specific workflows are available together in this web client.",
  },
};

const state = {
  token: "",
  role: "",
  templates: [],
  faults: [],
  recommendations: [],
  activeTaskId: "",
  reportPollTimer: null,
};

function apiBase() {
  return localStorage.getItem(STORAGE_KEY) || "http://127.0.0.1:8000";
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

function renderTable(targetId, rows, emptyMessage = "No data") {
  const target = document.getElementById(targetId);
  if (!target) {
    return;
  }
  if (!rows || rows.length === 0) {
    target.innerHTML = `<div class="empty-state">${emptyMessage}</div>`;
    return;
  }
  const columns = Object.keys(rows[0]);
  target.innerHTML = `
    <table>
      <thead>
        <tr>${columns.map((column) => `<th>${column}</th>`).join("")}</tr>
      </thead>
      <tbody>
        ${rows.map((row) => `<tr>${columns.map((column) => `<td>${formatCell(row[column])}</td>`).join("")}</tr>`).join("")}
      </tbody>
    </table>
  `;
}

function formatCell(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "object") {
    return `<pre>${JSON.stringify(value, null, 2)}</pre>`;
  }
  return String(value);
}

function setOptions(selectId, rows, valueKey, labelBuilder, emptyLabel) {
  const select = document.getElementById(selectId);
  if (!select) {
    return;
  }
  if (!rows || rows.length === 0) {
    select.innerHTML = `<option value="">${emptyLabel}</option>`;
    select.disabled = true;
    return;
  }
  select.disabled = false;
  select.innerHTML = rows
    .map((row) => `<option value="${row[valueKey]}">${labelBuilder(row)}</option>`)
    .join("");
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
    throw new Error("Backend is not reachable. Start FastAPI on http://127.0.0.1:8000");
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
  document.getElementById("roleBadge").textContent = meta.badge;
  document.getElementById("shellTitle").textContent = meta.shellTitle;
  document.getElementById("shellCopy").textContent = meta.shellCopy;
  document.getElementById("heroEyebrow").textContent = meta.heroEyebrow;
  document.getElementById("heroTitle").textContent = meta.heroTitle;
  document.getElementById("heroCopy").textContent = meta.heroCopy;
  document.getElementById("sessionInfo").textContent = state.token ? `Role: ${state.role}` : "Not signed in";

  document.getElementById("managerPanel").classList.toggle("hidden", !hasRole("manager"));
  document.getElementById("monitoringPanel").classList.toggle("hidden", !hasRole("tech_expert", "dispatcher_specialist"));
  document.getElementById("expertPanel").classList.toggle("hidden", !hasRole("tech_expert"));
  document.getElementById("dispatcherPanel").classList.toggle("hidden", !hasRole("dispatcher_specialist"));
}

function resetRoleData() {
  state.templates = [];
  state.faults = [];
  state.recommendations = [];
  state.activeTaskId = "";
  stopReportPolling();

  renderTable("webDashboard", [], "No data yet");
  renderTable("reportTemplates", [], "No templates yet");
  renderTable("desktopMonitoring", [], "No monitoring data yet");
  renderJsonBox("expertResult", null, "Expert actions will appear here.");
  renderJsonBox("dispatcherResult", null, "Dispatcher actions will appear here.");
  document.getElementById("activeReportStatus").textContent = "Current report status will appear here.";
  document.getElementById("activeReportStatus").className = "live-status empty-state";
  document.getElementById("reportJobs").innerHTML = "<div class='empty-state'>No background reports yet</div>";
  setOptions("templateSelect", [], "id", () => "", "Load templates first");
  setOptions("faultSelect", [], "id", () => "", "Load faults first");
  setOptions("recommendationSelect", [], "recommendation_id", () => "", "Load recommendations first");
  setReportMessage("");
}

function selectedTemplate() {
  const value = document.getElementById("templateSelect").value;
  if (!value) {
    throw new Error("Select a report template first.");
  }
  return state.templates.find((item) => String(item.id) === String(value)) || null;
}

function selectedReportPayload() {
  const template = selectedTemplate();
  if (!template) {
    throw new Error("Select a report template first.");
  }
  return { template_id: Number(template.id) };
}

function selectedDelaySeconds() {
  const value = Number(document.getElementById("delayValue").value);
  const unit = document.getElementById("delayUnit").value;
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error("Delay must be greater than 0.");
  }
  const multiplier = unit === "hours" ? 3600 : unit === "minutes" ? 60 : 1;
  return Math.round(value * multiplier);
}

function selectedFaultId() {
  const value = Number(document.getElementById("faultSelect").value);
  if (!value) {
    throw new Error("Load and select a fault first.");
  }
  return value;
}

function selectedRecommendationId() {
  const value = Number(document.getElementById("recommendationSelect").value);
  if (!value) {
    throw new Error("Load and select a recommendation first.");
  }
  return value;
}

function statusLabel(status) {
  const labels = {
    queued: "Queued",
    in_progress: "In progress",
    completed: "Completed",
    failed: "Failed",
  };
  return labels[status] || status;
}

function renderTemplateSelect(rows) {
  state.templates = rows || [];
  setOptions(
    "templateSelect",
    state.templates,
    "id",
    (item) => item.template_name || item.name || item.report_type || `Template ${item.id}`,
    "No active templates"
  );
}

function renderFaultSelect(rows) {
  state.faults = rows || [];
  setOptions(
    "faultSelect",
    state.faults,
    "id",
    (item) => `#${item.id} | ${item.equipment_name || "-"} / ${item.component_name || "-"} | ${item.severity || "-"}`,
    "No available faults"
  );
}

function renderRecommendationSelect(rows) {
  state.recommendations = rows || [];
  setOptions(
    "recommendationSelect",
    state.recommendations,
    "recommendation_id",
    (item) => `#${item.recommendation_id} | ${item.equipment_name || "-"} | ${item.priority || "-"}`,
    "No available recommendations"
  );
}

function renderActiveReportStatus(rows) {
  const box = document.getElementById("activeReportStatus");
  if (!state.activeTaskId) {
    box.className = "live-status empty-state";
    box.textContent = "Current report status will appear here.";
    return;
  }
  const report = rows.find((item) => item.job_id === state.activeTaskId);
  if (!report) {
    box.className = "live-status status-queued";
    box.textContent = `Report ${state.activeTaskId} is queued. Waiting for status update.`;
    return;
  }
  box.className = `live-status status-${report.status}`;
  box.textContent = `Current report: ${report.report_type}. Status: ${statusLabel(report.status)}.`;
}

function renderReportJobs(rows) {
  const list = rows || [];
  renderActiveReportStatus(list);
  syncReportPolling(list);

  const target = document.getElementById("reportJobs");
  if (!target) {
    return;
  }
  if (!list.length) {
    target.innerHTML = "<div class='empty-state'>No background reports yet</div>";
    return;
  }
  target.innerHTML = list
    .map((item) => {
      const documentButton = item.has_document
        ? `<button type="button" data-open-report="${item.job_id}">Open DOCX</button>`
        : "<span class='muted'>Document will appear after completion</span>";
      return `
        <article class="report-card">
          <div>
            <div class="status-pill status-${item.status}">${statusLabel(item.status)}</div>
            <h3>${item.report_type}</h3>
            <p class="muted">Task: ${item.job_id}</p>
            <p class="muted">Queued: ${item.queued_at || "-"} | Started: ${item.started_at || "-"} | Finished: ${item.finished_at || "-"}</p>
          </div>
          <div class="report-actions">${documentButton}</div>
        </article>
      `;
    })
    .join("");
  target.querySelectorAll("[data-open-report]").forEach((button) => {
    button.addEventListener("click", () => openReportDocument(button.dataset.openReport));
  });
}

function openReportDocument(taskId) {
  if (!taskId) {
    setError("Select a completed report first.");
    return;
  }
  window.open(`${apiBase()}/reports/document/${taskId}?token=${encodeURIComponent(state.token)}`, "_blank");
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

function stopReportPolling() {
  if (!state.reportPollTimer) {
    return;
  }
  clearInterval(state.reportPollTimer);
  state.reportPollTimer = null;
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
  if (query.dashboard) {
    renderTable("webDashboard", query.dashboard, "No data yet");
  }
  if (query.templates) {
    renderTemplateSelect(query.templates);
    renderTable("reportTemplates", query.templates, "No templates yet");
  }
  if (query.recent_reports) {
    renderReportJobs(query.recent_reports);
  }
}

function applyMonitoringRows(rows) {
  renderTable("desktopMonitoring", rows || [], "No monitoring data yet");
}

async function loadManagerHome() {
  const result = await request("/bff/web/manager-home");
  applyManagerQuery(result);
}

async function loadTemplates() {
  setReportMessage("Loading report templates...");
  try {
    const rows = await request("/reports/templates");
    renderTemplateSelect(rows);
    renderTable("reportTemplates", rows, "No templates yet");
    setReportMessage(rows.length ? "Templates loaded." : "No active templates returned by API.");
  } catch (error) {
    renderTemplateSelect([]);
    renderTable("reportTemplates", [], "No templates yet");
    setReportMessage(`Unable to load templates: ${error.message}`, true);
    throw error;
  }
}

async function loadReportJobs() {
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
  renderJsonBox("expertResult", rows, "No faults available.");
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
  if (result.query && result.query.faults) {
    renderFaultSelect(result.query.faults);
  }
  if (result.query && result.query.monitoring) {
    applyMonitoringRows(result.query.monitoring);
  }
  renderJsonBox("expertResult", result, "Expert actions will appear here.");
}

async function confirmFault() {
  const result = await request("/bff/desktop/expert/faults/confirm", {
    method: "POST",
    body: JSON.stringify({
      fault_ids: [selectedFaultId()],
      action: "confirm",
    }),
  });
  if (result.query && result.query.faults) {
    renderFaultSelect(result.query.faults);
  }
  if (result.query && result.query.monitoring) {
    applyMonitoringRows(result.query.monitoring);
  }
  renderJsonBox("expertResult", result, "Expert actions will appear here.");
}

async function loadDispatcherRecommendations() {
  const rows = await request("/specialist/recommendations");
  renderRecommendationSelect(rows);
  renderJsonBox("dispatcherResult", rows, "No recommendations available.");
}

async function createPlan() {
  const result = await request("/bff/desktop/dispatcher/plans", {
    method: "POST",
    body: JSON.stringify({
      recommendation_ids: [selectedRecommendationId()],
      planned_date: document.getElementById("planDate").value,
    }),
  });
  if (result.query && result.query.recommendations) {
    renderRecommendationSelect(result.query.recommendations);
  }
  if (result.query && result.query.monitoring) {
    applyMonitoringRows(result.query.monitoring);
  }
  renderJsonBox("dispatcherResult", result, "Dispatcher actions will appear here.");
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
    applyRolePresentation();
    await refreshRoleData();
  } catch (error) {
    state.token = "";
    state.role = "";
    applyRolePresentation();
    resetRoleData();
    setError(error.message);
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
      setReportMessage("Sending report generation command...");
      const template = selectedTemplate();
      await queueReport(0);
      setReportMessage(`Report "${template ? template.template_name : "selected template"}" is queued.`);
    } catch (error) {
      setError(error.message);
      setReportMessage(error.message, true);
    }
  });

  document.getElementById("queueDelayedReport").addEventListener("click", async () => {
    try {
      setError("");
      setReportMessage("Sending delayed report generation command...");
      const template = selectedTemplate();
      const delaySeconds = selectedDelaySeconds();
      await queueReport(delaySeconds);
      setReportMessage(`Report "${template ? template.template_name : "selected template"}" is delayed by ${delaySeconds} seconds.`);
    } catch (error) {
      setError(error.message);
      setReportMessage(error.message, true);
    }
  });

  document.getElementById("createRecommendation").addEventListener("click", () => {
    createRecommendation().catch((error) => {
      setError(error.message);
      renderJsonBox("expertResult", { error: error.message }, "Expert actions will appear here.");
    });
  });

  document.getElementById("confirmFault").addEventListener("click", () => {
    confirmFault().catch((error) => {
      setError(error.message);
      renderJsonBox("expertResult", { error: error.message }, "Expert actions will appear here.");
    });
  });

  document.getElementById("createPlan").addEventListener("click", () => {
    createPlan().catch((error) => {
      setError(error.message);
      renderJsonBox("dispatcherResult", { error: error.message }, "Dispatcher actions will appear here.");
    });
  });
}

bindDebugPanel();
bindDebugShortcut();
applyDebugVisibility();
applyRolePresentation();
resetRoleData();
bindActions();
