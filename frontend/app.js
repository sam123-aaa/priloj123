const STORAGE_KEY = "maintenance_api_base";

function getApiBase() {
  return localStorage.getItem(STORAGE_KEY) || "http://127.0.0.1:8000";
}

function setApiBase(value) {
  localStorage.setItem(STORAGE_KEY, value.replace(/\/$/, ""));
}

function initApiBaseForm() {
  const input = document.getElementById("apiBase");
  const button = document.getElementById("saveApiBase");
  if (!input || !button) {
    return;
  }
  input.value = getApiBase();
  button.addEventListener("click", () => {
    setApiBase(input.value.trim());
    button.textContent = "Сохранено";
    setTimeout(() => {
      button.textContent = "Сохранить URL API";
    }, 1200);
  });
}

function createState(pageKey) {
  return {
    token: localStorage.getItem(`${pageKey}_token`) || "",
    role: localStorage.getItem(`${pageKey}_role`) || "",
    pageKey,
  };
}

function persistState(state) {
  localStorage.setItem(`${state.pageKey}_token`, state.token || "");
  localStorage.setItem(`${state.pageKey}_role`, state.role || "");
}

function logoutState(state) {
  state.token = "";
  state.role = "";
  persistState(state);
}

async function apiRequest(path, options = {}, state) {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (state?.token) {
    headers.set("Authorization", `Bearer ${state.token}`);
  }

  const response = await fetch(`${getApiBase()}${path}`, {
    ...options,
    headers,
  });

  let body = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    body = await response.json();
  } else {
    body = await response.text();
  }

  if (!response.ok) {
    const message = body?.detail || body?.message || `HTTP ${response.status}`;
    throw new Error(message);
  }

  return body;
}

function setError(message) {
  const errorBox = document.getElementById("errorBox");
  if (!errorBox) {
    return;
  }
  if (!message) {
    errorBox.textContent = "";
    errorBox.classList.add("hidden");
    return;
  }
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function renderTable(containerId, rows) {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }
  if (!rows || rows.length === 0) {
    container.innerHTML = "<div class='empty-state'>Нет данных</div>";
    return;
  }

  const columns = Object.keys(rows[0]);
  const header = columns.map((column) => `<th>${column}</th>`).join("");
  const body = rows
    .map((row) => {
      const cells = columns
        .map((column) => `<td>${formatCell(row[column])}</td>`)
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");

  container.innerHTML = `<table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`;
}

function renderTaskCards(containerId, rows) {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }
  if (!rows || rows.length === 0) {
    container.innerHTML = "<div class='empty-state'>Нет задач</div>";
    return;
  }
  container.innerHTML = rows
    .map(
      (row) => `
      <article class="task-card">
        <strong>#${row.task_id || row.id}</strong>
        <div>${row.description || "-"}</div>
        <div class="muted">status: ${row.status || "-"}</div>
        <div class="muted">planned_date: ${row.planned_date || "-"}</div>
        <div class="muted">equipment: ${row.equipment_name || "-"}</div>
      </article>
    `
    )
    .join("");
}

function setVisible(id, visible) {
  const element = document.getElementById(id);
  if (element) {
    element.classList.toggle("hidden", !visible);
  }
}

function setOptions(selectId, rows, valueKey, labelBuilder, emptyLabel) {
  const select = document.getElementById(selectId);
  if (!select) {
    return;
  }
  if (!rows || rows.length === 0) {
    select.innerHTML = `<option value="">${emptyLabel}</option>`;
    return;
  }
  select.innerHTML = rows
    .map((row) => `<option value="${row[valueKey]}">${labelBuilder(row)}</option>`)
    .join("");
}

function formatCell(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "object") {
    return `<pre>${JSON.stringify(value, null, 2)}</pre>`;
  }
  return String(value);
}

async function loginFromForm(form, state, onSuccess) {
  const formData = new FormData(form);
  try {
    setError("");
    const payload = {
      email: formData.get("email"),
      password: formData.get("password"),
    };
    const result = await apiRequest("/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.token = result.access_token;
    state.role = typeof result.role === "string" ? result.role : result.role?.code || "";
    persistState(state);
    onSuccess(result);
  } catch (error) {
    setError(error.message);
  }
}

function bindApiBaseInput() {
  const input = document.getElementById("apiBaseInput");
  const button = document.getElementById("saveApiBase");
  if (!input || !button) {
    return;
  }
  input.value = getApiBase();
  button.addEventListener("click", () => {
    setApiBase(input.value.trim());
    button.textContent = "Сохранено";
    setTimeout(() => {
      button.textContent = "Сохранить URL";
    }, 1200);
  });
}

function initWebClient() {
  const state = createState("web");
  const sessionInfo = document.getElementById("sessionInfo");
  const loginForm = document.getElementById("loginForm");
  const logoutButton = document.getElementById("logoutButton");
  const refreshDashboard = document.getElementById("refreshDashboard");
  const reportForm = document.getElementById("reportForm");
  const delayedReportForm = document.getElementById("delayedReportForm");
  const statusForm = document.getElementById("statusForm");
  const reportResult = document.getElementById("reportResult");
  const reportStatus = document.getElementById("reportStatus");

  bindApiBaseInput();
  sessionInfo.textContent = state.token ? `Авторизован как ${state.role}` : "Не авторизован";

  async function loadDashboard() {
    if (!state.token) {
      renderTable("webDashboard", []);
      return;
    }
    try {
      const rows = await apiRequest("/bff/web/dashboard", {}, state);
      renderTable("webDashboard", rows);
    } catch (error) {
      setError(error.message);
    }
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await loginFromForm(loginForm, state, async () => {
      sessionInfo.textContent = `Авторизован как ${state.role}`;
      await loadDashboard();
    });
  });

  logoutButton.addEventListener("click", () => {
    logoutState(state);
    sessionInfo.textContent = "Не авторизован";
    renderTable("webDashboard", []);
  });

  refreshDashboard.addEventListener("click", loadDashboard);

  reportForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const formData = new FormData(reportForm);
      const data = await apiRequest(
        "/reports/generate",
        {
          method: "POST",
          body: JSON.stringify({ report_type: formData.get("reportType") }),
        },
        state
      );
      reportResult.textContent = `Task queued: ${data.task_id}`;
    } catch (error) {
      setError(error.message);
    }
  });

  delayedReportForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const formData = new FormData(delayedReportForm);
      const data = await apiRequest(
        "/reports/generate-delayed",
        {
          method: "POST",
          body: JSON.stringify({
            report_type: formData.get("reportType"),
            delay_seconds: Number(formData.get("delaySeconds")),
          }),
        },
        state
      );
      reportResult.textContent = `Delayed task queued: ${data.task_id}`;
    } catch (error) {
      setError(error.message);
    }
  });

  statusForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const formData = new FormData(statusForm);
      const data = await apiRequest(`/reports/status/${formData.get("taskId")}`, {}, state);
      reportStatus.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
      setError(error.message);
    }
  });

  loadDashboard();
}

function initMobileClient() {
  const state = createState("mobile");
  const loginForm = document.getElementById("loginForm");
  const sessionInfo = document.getElementById("sessionInfo");
  const refreshTasks = document.getElementById("refreshTasks");
  const refreshComponents = document.getElementById("refreshComponents");
  const refreshQualityTasks = document.getElementById("refreshQualityTasks");
  const measurementForm = document.getElementById("measurementForm");
  const measurementResult = document.getElementById("measurementResult");
  const taskActionForm = document.getElementById("taskActionForm");
  const taskActionResult = document.getElementById("taskActionResult");
  const qualityForm = document.getElementById("qualityForm");
  const qualityResult = document.getElementById("qualityResult");

  sessionInfo.textContent = state.token ? `Авторизован как ${state.role}` : "Не авторизован";

  function applyMobileRoleVisibility() {
    const isAdmin = state.role === "admin";
    setVisible("metrologistSection", isAdmin || state.role === "metrologist");
    setVisible("mechanicSection", isAdmin || state.role === "mechanic");
    setVisible("qualitySection", isAdmin || state.role === "quality_engineer");
  }

  async function loadTasks() {
    if (!state.token) {
      renderTaskCards("mobileTasks", []);
      return;
    }
    try {
      const rows = await apiRequest("/bff/mobile/tasks", {}, state);
      renderTaskCards("mobileTasks", rows);
      setOptions(
        "mechanicTaskSelect",
        rows,
        "task_id",
        (row) => `#${row.task_id} | ${row.equipment_name || "-"} | ${row.status}`,
        "Нет задач механика"
      );
    } catch (error) {
      setError(error.message);
    }
  }

  async function loadComponents() {
    if (!state.token) {
      setOptions("componentSelect", [], "component_id", () => "", "Нет компонентов");
      return;
    }
    try {
      const rows = await apiRequest("/bff/mobile/components", {}, state);
      setOptions(
        "componentSelect",
        rows,
        "component_id",
        (row) => `${row.equipment_name} / ${row.component_name}`,
        "Нет компонентов"
      );
    } catch (error) {
      setError(error.message);
    }
  }

  async function loadQualityTasks() {
    if (!state.token) {
      renderTaskCards("qualityTasks", []);
      return;
    }
    try {
      const rows = await apiRequest("/bff/mobile/quality/tasks", {}, state);
      renderTaskCards("qualityTasks", rows);
      setOptions(
        "qualityTaskSelect",
        rows,
        "task_id",
        (row) => `#${row.task_id} | ${row.equipment_name || "-"} | ${row.status}`,
        "Нет задач на проверку"
      );
    } catch (error) {
      setError(error.message);
    }
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await loginFromForm(loginForm, state, async () => {
      sessionInfo.textContent = `Авторизован как ${state.role}`;
      applyMobileRoleVisibility();
      if (state.role === "mechanic" || state.role === "admin") {
        await loadTasks();
      }
      if (state.role === "metrologist" || state.role === "admin") {
        await loadComponents();
      }
      if (state.role === "quality_engineer" || state.role === "admin") {
        await loadQualityTasks();
      }
    });
  });

  refreshTasks.addEventListener("click", loadTasks);
  refreshComponents.addEventListener("click", loadComponents);
  refreshQualityTasks.addEventListener("click", loadQualityTasks);

  measurementForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const formData = new FormData(measurementForm);
      const payload = [
        {
          component_id: Number(formData.get("componentId")),
          parameter_name: formData.get("parameterName"),
          value: Number(formData.get("value")),
          unit: formData.get("unit"),
        },
      ];
      const result = await apiRequest(
        "/bff/mobile/metrolog/measurements",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
        state
      );
      measurementResult.textContent = JSON.stringify(result, null, 2);
      const components = result.query?.components || [];
      if (components.length) {
        setOptions(
          "componentSelect",
          components,
          "component_id",
          (row) => `${row.equipment_name} / ${row.component_name}`,
          "Нет компонентов"
        );
      }
    } catch (error) {
      setError(error.message);
    }
  });

  taskActionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const formData = new FormData(taskActionForm);
      const taskId = Number(formData.get("taskId"));
      const action = formData.get("action");
      if (!taskId) {
        throw new Error("Сначала выберите задачу");
      }
      let path = `/bff/mobile/mechanic/tasks/${taskId}/${action}`;
      let options = { method: "POST", body: JSON.stringify({}) };
      if (action === "finish") {
        options = {
          method: "POST",
          body: JSON.stringify({ result: formData.get("result") }),
        };
      }
      const result = await apiRequest(path, options, state);
      taskActionResult.textContent = JSON.stringify(result, null, 2);
      const tasks = result.query?.tasks || [];
      renderTaskCards("mobileTasks", tasks);
      setOptions(
        "mechanicTaskSelect",
        tasks,
        "task_id",
        (row) => `#${row.task_id} | ${row.equipment_name || "-"} | ${row.status}`,
        "Нет задач механика"
      );
    } catch (error) {
      setError(error.message);
    }
  });

  qualityForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const formData = new FormData(qualityForm);
      const taskId = Number(formData.get("taskId"));
      if (!taskId) {
        throw new Error("Сначала выберите задачу для проверки");
      }
      const result = await apiRequest(
        `/bff/mobile/quality/tasks/${taskId}/check`,
        {
          method: "POST",
          body: JSON.stringify({
            status: formData.get("status"),
            notes: formData.get("notes"),
          }),
        },
        state
      );
      qualityResult.textContent = JSON.stringify(result, null, 2);
      const tasks = result.query?.quality_tasks || [];
      renderTaskCards("qualityTasks", tasks);
      setOptions(
        "qualityTaskSelect",
        tasks,
        "task_id",
        (row) => `#${row.task_id} | ${row.equipment_name || "-"} | ${row.status}`,
        "Нет задач на проверку"
      );
    } catch (error) {
      setError(error.message);
    }
  });

  applyMobileRoleVisibility();
  if (state.role === "mechanic" || state.role === "admin") {
    loadTasks();
  }
  if (state.role === "metrologist" || state.role === "admin") {
    loadComponents();
  }
  if (state.role === "quality_engineer" || state.role === "admin") {
    loadQualityTasks();
  }
}

function initDesktopClient() {
  const state = createState("desktop");
  const loginForm = document.getElementById("loginForm");
  const sessionInfo = document.getElementById("sessionInfo");
  const refreshButton = document.getElementById("refreshMonitoring");
  const refreshFaults = document.getElementById("refreshFaults");
  const refreshRecommendations = document.getElementById("refreshRecommendations");
  const expertForm = document.getElementById("expertForm");
  const dispatcherForm = document.getElementById("dispatcherForm");
  const confirmFault = document.getElementById("confirmFault");
  const expertResult = document.getElementById("expertResult");
  const dispatcherResult = document.getElementById("dispatcherResult");

  bindApiBaseInput();
  sessionInfo.textContent = state.token ? `Авторизован как ${state.role}` : "Не авторизован";

  function applyDesktopRoleVisibility() {
    const isAdmin = state.role === "admin";
    setVisible("expertPanel", isAdmin || state.role === "tech_expert");
    setVisible("dispatcherPanel", isAdmin || state.role === "dispatcher_specialist");
  }

  async function refreshAll() {
    if (!state.token) {
      renderTable("desktopMonitoring", []);
      renderTable("desktopTransactions", []);
      return;
    }
    try {
      const monitoring = await apiRequest("/bff/desktop/monitoring", {}, state);
      renderTable("desktopMonitoring", monitoring);
      if (state.role === "admin") {
        const transactions = await apiRequest("/transactions", {}, state);
        renderTable("desktopTransactions", transactions);
      } else {
        renderTable("desktopTransactions", []);
      }
    } catch (error) {
      setError(error.message);
    }
  }

  async function loadFaults() {
    try {
      const rows = await apiRequest("/expert/faults", {}, state);
      setOptions(
        "faultSelect",
        rows,
        "id",
        (row) => `#${row.id} | ${row.equipment_name || "-"} / ${row.component_name || "-"} | ${row.status || "-"}`,
        "Нет доступных неисправностей"
      );
      expertResult.textContent = JSON.stringify(rows, null, 2);
    } catch (error) {
      setError(error.message);
      expertResult.textContent = error.message;
    }
  }

  async function loadRecommendations() {
    try {
      const rows = await apiRequest("/specialist/recommendations", {}, state);
      setOptions(
        "recommendationSelect",
        rows,
        "recommendation_id",
        (row) => `#${row.recommendation_id} | ${row.equipment_name || "-"} | ${row.priority || "-"}`,
        "Нет доступных рекомендаций"
      );
      dispatcherResult.textContent = JSON.stringify(rows, null, 2);
    } catch (error) {
      setError(error.message);
      dispatcherResult.textContent = error.message;
    }
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await loginFromForm(loginForm, state, async () => {
      sessionInfo.textContent = `Авторизован как ${state.role}`;
      applyDesktopRoleVisibility();
      await refreshAll();
    });
  });

  refreshButton.addEventListener("click", refreshAll);
  refreshFaults.addEventListener("click", loadFaults);
  refreshRecommendations.addEventListener("click", loadRecommendations);

  expertForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const formData = new FormData(expertForm);
      const faultId = Number(formData.get("faultId"));
      if (!faultId) {
        throw new Error("Сначала выберите неисправность");
      }
      const result = await apiRequest(
        "/bff/desktop/expert/recommendations",
        {
          method: "POST",
          body: JSON.stringify({
            fault_id: faultId,
            recommendation_text: formData.get("recommendationText"),
            priority: formData.get("priority"),
          }),
        },
        state
      );
      expertResult.textContent = JSON.stringify(result, null, 2);
      renderTable("desktopMonitoring", result.query?.monitoring || []);
      if (result.query?.faults) {
        setOptions(
          "faultSelect",
          result.query.faults,
          "id",
          (row) => `#${row.id} | ${row.equipment_name || "-"} / ${row.component_name || "-"} | ${row.status || "-"}`,
          "Нет доступных неисправностей"
        );
      }
    } catch (error) {
      setError(error.message);
      expertResult.textContent = error.message;
    }
  });

  confirmFault.addEventListener("click", async () => {
    try {
      const faultId = Number(document.getElementById("faultSelect").value);
      if (!faultId) {
        throw new Error("Сначала выберите неисправность");
      }
      const result = await apiRequest(
        "/bff/desktop/expert/faults/confirm",
        {
          method: "POST",
          body: JSON.stringify({ fault_ids: [faultId], action: "confirm" }),
        },
        state
      );
      expertResult.textContent = JSON.stringify(result, null, 2);
      renderTable("desktopMonitoring", result.query?.monitoring || []);
    } catch (error) {
      setError(error.message);
      expertResult.textContent = error.message;
    }
  });

  dispatcherForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const formData = new FormData(dispatcherForm);
      const recommendationId = Number(formData.get("recommendationId"));
      if (!recommendationId) {
        throw new Error("Сначала выберите рекомендацию");
      }
      const result = await apiRequest(
        "/bff/desktop/dispatcher/plans",
        {
          method: "POST",
          body: JSON.stringify({
            recommendation_ids: [recommendationId],
            planned_date: formData.get("plannedDate"),
          }),
        },
        state
      );
      dispatcherResult.textContent = JSON.stringify(result, null, 2);
      renderTable("desktopMonitoring", result.query?.monitoring || []);
      if (result.query?.recommendations) {
        setOptions(
          "recommendationSelect",
          result.query.recommendations,
          "recommendation_id",
          (row) => `#${row.recommendation_id} | ${row.equipment_name || "-"} | ${row.priority || "-"}`,
          "Нет доступных рекомендаций"
        );
      }
    } catch (error) {
      setError(error.message);
      dispatcherResult.textContent = error.message;
    }
  });

  applyDesktopRoleVisibility();
  refreshAll();
}
