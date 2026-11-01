(() => {
  "use strict";

  const form = document.getElementById("query-form");
  const query = document.getElementById("query");
  const mode = document.getElementById("mode");
  const topK = document.getElementById("top-k");
  const token = document.getElementById("token");
  const loadTokenButton = document.getElementById("load-token");
  const runButton = document.getElementById("run");
  const formError = document.getElementById("form-error");
  const status = document.getElementById("response-status");
  const emptyState = document.getElementById("empty-state");
  const loading = document.getElementById("loading");
  const result = document.getElementById("result");
  const errorState = document.getElementById("error-state");
  const errorMessage = document.getElementById("error-message");
  const output = document.getElementById("output");
  const raw = document.getElementById("raw");

  const metric = (id) => document.getElementById(id);
  const show = (element, visible) => { element.hidden = !visible; };

  function setStatus(text, kind = "") {
    status.textContent = text;
    status.className = `pill ${kind}`.trim();
  }

  function showError(message) {
    show(emptyState, false);
    show(loading, false);
    show(result, false);
    show(errorState, true);
    errorMessage.textContent = message;
    setStatus("Error", "bad");
  }

  function renderResult(payload) {
    show(emptyState, false);
    show(loading, false);
    show(errorState, false);
    show(result, true);
    output.textContent = payload.output || "(no output)";
    metric("metric-model").textContent = payload.model_id || "—";
    metric("metric-input").textContent = payload.usage?.input_tokens ?? "—";
    metric("metric-output").textContent = payload.usage?.output_tokens ?? "—";
    metric("metric-chunks").textContent = payload.retrieval?.chunks_used ?? "—";
    const cost = payload.usage?.estimated_cost_usd;
    metric("metric-cost").textContent = typeof cost === "number" ? `$${cost.toFixed(6)}` : "—";
    const total = payload.latency_ms?.total;
    metric("metric-latency").textContent = typeof total === "number" ? `${Math.round(total)} ms` : "—";
    raw.textContent = JSON.stringify(payload, null, 2);
    setStatus("OK", "ok");
  }

  loadTokenButton.addEventListener("click", async () => {
    loadTokenButton.disabled = true;
    try {
      const response = await fetch("/local-token", { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Token endpoint returned HTTP ${response.status}`);
      const payload = await response.json();
      if (!payload.access_token) throw new Error("Token endpoint returned no access_token");
      token.value = payload.access_token;
      formError.hidden = true;
      setStatus("Token loaded", "ok");
    } catch (error) {
      formError.textContent = `Could not load local token: ${error.message}`;
      formError.hidden = false;
    } finally {
      loadTokenButton.disabled = false;
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    formError.hidden = true;
    const question = query.value.trim();
    if (!question) {
      formError.textContent = "Enter a question or prompt.";
      formError.hidden = false;
      query.focus();
      return;
    }
    if (!token.value.trim()) {
      formError.textContent = "Load a local token or paste a bearer token.";
      formError.hidden = false;
      token.focus();
      return;
    }

    runButton.disabled = true;
    show(emptyState, false);
    show(result, false);
    show(errorState, false);
    show(loading, true);
    setStatus("Running", "busy");

    const endpoint = mode.value;
    const body = endpoint === "/query"
      ? { query: question, top_k: Math.max(1, Math.min(10, Number(topK.value) || 3)) }
      : { prompt: question };

    try {
      const response = await fetch(`/api${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token.value.trim()}`,
        },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || `Request failed with HTTP ${response.status}`);
      }
      renderResult(payload);
    } catch (error) {
      showError(error.message || "Network error");
    } finally {
      runButton.disabled = false;
      show(loading, false);
    }
  });
})();
