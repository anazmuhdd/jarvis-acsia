import { useState } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

function StatusBadge({ status }) {
  if (!status) return null;
  const color =
    status === "success" ? "#22c55e" : status === "loading" ? "#f59e0b" : "#ef4444";
  const label =
    status === "success" ? "✓ Success" : status === "loading" ? "⏳ Running..." : "✗ Error";
  return (
    <span className="badge" style={{ background: color + "22", color, border: `1px solid ${color}` }}>
      {label}
    </span>
  );
}

function ApiCard({ title, description, method, badge, children, onTrigger, status, result }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`card ${status === "loading" ? "card-loading" : ""}`}>
      <div className="card-header">
        <div className="card-title-row">
          <span className={`method-badge method-${method.toLowerCase()}`}>{method}</span>
          <h3 className="card-title">{title}</h3>
          {badge && <span className="chip">{badge}</span>}
        </div>
        <p className="card-desc">{description}</p>
      </div>
      <div className="card-body">
        {children}
        <button
          className={`btn ${status === "loading" ? "btn-disabled" : "btn-primary"}`}
          onClick={onTrigger}
          disabled={status === "loading"}
        >
          {status === "loading" ? "Running..." : `Trigger ${method}`}
        </button>
        <StatusBadge status={status} />
      </div>
      {result && (
        <div className="result-panel">
          <button className="toggle-btn" onClick={() => setExpanded(!expanded)}>
            {expanded ? "▲ Hide Response" : "▼ Show Response"}
          </button>
          {expanded && (
            <pre className="result-json">{typeof result === "string" ? result : JSON.stringify(result, null, 2)}</pre>
          )}
        </div>
      )}
    </div>
  );
}

function useApiCall() {
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);

  const call = async (fn) => {
    setStatus("loading");
    setResult(null);
    try {
      const res = await fn();
      setResult(res);
      setStatus("success");
    } catch (err) {
      setResult(err.message || String(err));
      setStatus("error");
    }
  };

  return { status, result, call };
}

async function apiFetch(path, { method = "GET", token, body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(async () => ({ raw: await res.text() }));
  if (!res.ok) throw new Error(data?.detail || JSON.stringify(data));
  return data;
}

export default function App() {
  const [customMessage, setCustomMessage] = useState("<h1>Hello from Jarvis Admin!</h1>");

  const ping = useApiCall();
  const messages = useApiCall();
  const chat = useApiCall();
  const sendMsg = useApiCall();
  const recap = useApiCall();

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">🤖</span>
            <div>
              <h1 className="logo-title">Jarvis Admin</h1>
              <p className="logo-sub">Teams Recap Assistant — Control Panel</p>
            </div>
          </div>
        </div>
      </header>

      <main className="main">
        <section className="section">
          <h2 className="section-title">🔧 System</h2>
          <div className="grid">
            <ApiCard
              title="Health Check"
              description="Ping the API server to verify it is running."
              method="GET"
              status={ping.status}
              result={ping.result}
              onTrigger={() => ping.call(() => apiFetch("/"))}
            />
          </div>
        </section>

        <section className="section">
          <h2 className="section-title">💬 Teams Messaging</h2>
          <div className="grid">
            <ApiCard
              title="Fetch All Messages"
              description="Retrieve all chat and Teams channel messages for the configured user."
              method="GET"
              status={messages.status}
              result={messages.result}
              onTrigger={() =>
                messages.call(() => apiFetch("/api/messages"))
              }
            />
            <ApiCard
              title="Get or Create Direct Chat"
              description="Find or create a 1-on-1 Teams chat session with the configured user."
              method="POST"
              status={chat.status}
              result={chat.result}
              onTrigger={() =>
                chat.call(() => apiFetch("/api/chat", { method: "POST" }))
              }
            />
            <ApiCard
              title="Send Test Message"
              description="Send a custom HTML-formatted message directly to the user's Teams chat."
              method="POST"
              status={sendMsg.status}
              result={sendMsg.result}
              onTrigger={() =>
                sendMsg.call(() =>
                  apiFetch("/api/send-message", {
                    method: "POST",
                    body: { message_html: customMessage },
                  })
                )
              }
            >
              <label className="label">HTML Message Content</label>
              <textarea
                className="textarea"
                value={customMessage}
                onChange={(e) => setCustomMessage(e.target.value)}
                rows={3}
              />
            </ApiCard>
          </div>
        </section>

        <section className="section">
          <h2 className="section-title">🧠 AI Recap Engine</h2>
          <div className="grid grid-full">
            <ApiCard
              title="Generate & Send Full Recap"
              description="Run the full AI recap pipeline using the NVIDIA LLM: fetch messages → generate summary & tasks → send to Teams chat → save tasks to Microsoft To Do → archive to OneNote."
              method="POST"
              badge="Full Pipeline"
              status={recap.status}
              result={recap.result}
              onTrigger={() =>
                recap.call(() =>
                  apiFetch("/api/recap/generate", { method: "POST" })
                )
              }
            />
          </div>
        </section>
      </main>

      <footer className="footer">
        <p>Jarvis Admin Panel — Teams Recap Assistant v1.0</p>
      </footer>
    </div>
  );
}
