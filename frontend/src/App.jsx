import { useState, useRef, useEffect } from "react";
import "./App.css";

const BOT_NAME = "FoodieBot";
const API_URL = "";  // empty = use Vite proxy to localhost:8000

const QUICK_REPLIES = [
  "Show menu 🍽️",
  "I want to order",
  "Track my order",
  "Cancel order",
];

function TypingIndicator() {
  return (
    <div className="message bot">
      <div className="avatar">🤖</div>
      <div className="bubble typing">
        <span /><span /><span />
      </div>
    </div>
  );
}

function Message({ msg }) {
  const isBot = msg.role === "bot";
  return (
    <div className={`message ${isBot ? "bot" : "user"}`}>
      {isBot && <div className="avatar">🤖</div>}
      <div className={`bubble ${isBot ? "bot-bubble" : "user-bubble"}`}>
        <p>{msg.text}</p>
        <span className="time">{msg.time}</span>
      </div>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: "bot",
      text: "Hey there! 👋 Welcome to FoodieBot. I can show you our menu, take your order, or track an existing one. What would you like?",
      time: now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function now() {
    return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  async function sendMessage(text) {
    if (!text.trim()) return;

    const userMsg = { id: Date.now(), role: "user", text, time: now() };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });
      const data = await res.json();
      const botMsg = {
        id: Date.now() + 1,
        role: "bot",
        text: data.response || "Sorry, something went wrong.",
        time: now(),
      };
      setMessages((m) => [...m, botMsg]);
    } catch {
      setMessages((m) => [
        ...m,
        { id: Date.now() + 1, role: "bot", text: "⚠️ Couldn't reach the server. Try again.", time: now() },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-icon">🍔</span>
          <div>
            <h1>FoodieBot</h1>
            <p>AI Food Ordering</p>
          </div>
        </div>

        <nav className="nav">
          <div className="nav-section">Quick Actions</div>
          {QUICK_REPLIES.map((q) => (
            <button key={q} className="nav-item" onClick={() => sendMessage(q)}>
              {q}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="status-dot" />
          <span>Bot Online</span>
        </div>
      </aside>

      {/* Chat */}
      <main className="chat">
        <header className="chat-header">
          <div className="header-info">
            <div className="avatar-lg">🤖</div>
            <div>
              <h2>{BOT_NAME}</h2>
              <p className="online">● Online</p>
            </div>
          </div>
          <div className="header-badge">Powered by Dialogflow + FastAPI</div>
        </header>

        <div className="messages">
          {messages.map((msg) => (
            <Message key={msg.id} msg={msg} />
          ))}
          {loading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>

        <div className="quick-replies">
          {QUICK_REPLIES.map((q) => (
            <button key={q} className="chip" onClick={() => sendMessage(q)}>
              {q}
            </button>
          ))}
        </div>

        <div className="input-bar">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Type your order..."
            disabled={loading}
          />
          <button
            className="send-btn"
            onClick={() => sendMessage(input)}
            disabled={loading || !input.trim()}
          >
            ➤
          </button>
        </div>
      </main>
    </div>
  );
}
