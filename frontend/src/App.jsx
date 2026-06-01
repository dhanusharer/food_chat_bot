import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const PRODUCTION_API_URL = "https://foodchatbot-production.up.railway.app";
const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_URL = import.meta.env.VITE_API_URL || (isLocalHost ? "" : PRODUCTION_API_URL);

const QUICK_ACTIONS = [
  { label: "Show Menu", prompt: "Show menu", icon: "🍽️", hint: "Browse food and prices" },
  { label: "New Order", prompt: "I want to order", icon: "🛒", hint: "Start adding items" },
  { label: "Track Order", prompt: "Track my order", icon: "📦", hint: "Check order status" },
  { label: "Cancel Order", prompt: "Cancel order", icon: "✕", hint: "Cancel by order ID" },
];

const EXAMPLES = ["1 pizza", "2 naan and 1 pasta", "Track order 9"];

function now() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function Message({ msg }) {
  const isBot = msg.role === "bot";

  return (
    <article className={`message ${isBot ? "bot" : "user"}`}>
      {isBot && <div className="message-avatar" aria-hidden="true">🤖</div>}
      <div className="message-body">
        <p>{msg.text}</p>
        <time>{msg.time}</time>
      </div>
    </article>
  );
}

function TypingIndicator() {
  return (
    <article className="message bot">
      <div className="message-avatar" aria-hidden="true">🤖</div>
      <div className="typing-pill" aria-label="FoodieBot is typing">
        <span />
        <span />
        <span />
      </div>
    </article>
  );
}

export default function App() {
  const [messages, setMessages] = useState([
    {
      id: crypto.randomUUID(),
      role: "bot",
      text: "Welcome to FoodieBot. Tell me what you want to eat, ask for the menu, or track an existing order.",
      time: now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const shortSession = useMemo(() => sessionId.slice(0, 8), [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage(text) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text: trimmed, time: now() },
    ]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, session_id: sessionId }),
      });

      if (!response.ok) {
        throw new Error("Request failed");
      }

      const data = await response.json();
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "bot",
          text: data.response || "I could not find a reply for that.",
          time: now(),
        },
      ]);
    } catch {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "bot",
          text: "I could not reach the server. Check the backend URL and try again.",
          time: now(),
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function submitMessage(event) {
    event.preventDefault();
    sendMessage(input);
  }

  return (
    <main className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">🍔</span>
          <div>
            <h1>FoodieBot</h1>
            <p>Fast food ordering assistant</p>
          </div>
        </div>
        <div className="connection">
          <span aria-hidden="true" />
          Online
        </div>
      </header>

      <section className="workspace">
        <aside className="action-panel" aria-label="Quick actions">
          <div className="panel-heading">
            <span>Actions</span>
            <strong>Start Here</strong>
          </div>

          {QUICK_ACTIONS.map((action) => (
            <button
              key={action.label}
              className="action-card"
              type="button"
              onClick={() => sendMessage(action.prompt)}
              disabled={loading}
            >
              <span className="action-icon" aria-hidden="true">{action.icon}</span>
              <span>
                <strong>{action.label}</strong>
                <small>{action.hint}</small>
              </span>
            </button>
          ))}
        </aside>

        <section className="chat-panel" aria-label="Chat with FoodieBot">
          <div className="chat-panel-header">
            <div>
              <span className="eyebrow">Live Chat</span>
              <h2>What are we ordering?</h2>
            </div>
            <span className="session-chip">#{shortSession}</span>
          </div>

          <div className="suggestion-row" aria-label="Example messages">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => sendMessage(example)}
                disabled={loading}
              >
                {example}
              </button>
            ))}
          </div>

          <div className="conversation">
            {messages.map((message) => (
              <Message key={message.id} msg={message} />
            ))}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>

          <form className="composer" onSubmit={submitMessage}>
            <input
              ref={inputRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Try: 1 pizza, show menu, track order 9..."
              disabled={loading}
              aria-label="Type a message"
            />
            <button type="submit" disabled={loading || !input.trim()} aria-label="Send message">
              Send
            </button>
          </form>
        </section>

        <aside className="guide-panel" aria-label="Ordering guide">
          <div className="food-visual" aria-hidden="true">
            <span>🍕</span>
            <span>🥤</span>
            <span>🥘</span>
          </div>

          <div className="guide-section">
            <span className="eyebrow">Ordering Flow</span>
            <ol>
              <li>Open the menu</li>
              <li>Add items with quantity</li>
              <li>Check your cart</li>
              <li>Confirm the order</li>
            </ol>
          </div>

          <div className="guide-section compact">
            <span className="eyebrow">Good Inputs</span>
            <p>“2 naan and 1 paneer butter masala”</p>
            <p>“Track order 9”</p>
          </div>
        </aside>
      </section>
    </main>
  );
}
