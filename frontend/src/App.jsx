import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const PRODUCTION_API_URL = `${window.location.origin}/api`;
const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_URL = isLocalHost 
  ? (import.meta.env.VITE_API_URL || "") 
  : `${window.location.origin}/api`;

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

function formatMessage(text) {
  // Split text into lines, then within each line, detect URLs and make them clickable
  return text.split("\n").map((line, i) => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const isUrl = /^https?:\/\/[^\s]+$/;
    const parts = line.split(urlRegex);
    return (
      <span key={i}>
        {i > 0 && <br />}
        {parts.map((part, j) =>
          isUrl.test(part) ? (
            <a key={j} href={part} target="_blank" rel="noopener noreferrer" className="chat-link">
              {part.includes("rzp.io") ? "💳 Click to Pay" : part}
            </a>
          ) : (
            <span key={j}>{part}</span>
          )
        )}
      </span>
    );
  });
}

function getEmojiForFood(name) {
  const n = name.toLowerCase();
  if (n.includes("pizza")) return "🍕";
  if (n.includes("coffee")) return "☕";
  if (n.includes("fries") || n.includes("french")) return "🍟";
  if (n.includes("burger")) return "🍔";
  if (n.includes("biryani") || n.includes("rice")) return "🍛";
  if (n.includes("dosa")) return "🥞";
  if (n.includes("shake") || n.includes("chocolate")) return "🥤";
  if (n.includes("wrap")) return "🌯";
  if (n.includes("pasta")) return "🍝";
  return "🍽️";
}

function MenuCard({ item, onAction }) {
  const [localQty, setLocalQty] = useState(1);

  const handleDecrement = () => {
    setLocalQty((prev) => Math.max(1, prev - 1));
  };

  const handleIncrement = () => {
    setLocalQty((prev) => prev + 1);
  };

  return (
    <div className="menu-card">
      <div className="menu-card-emoji" aria-hidden="true">
        {getEmojiForFood(item.name)}
      </div>
      <div className="menu-card-info">
        <h3>{item.name.replace(/\b\w/g, c => c.toUpperCase())}</h3>
        <span className="price">₹{item.price.toFixed(2)}</span>
      </div>
      <div className="menu-card-actions">
        <div className="local-qty-selector">
          <button 
            type="button" 
            className="qty-btn qty-minus" 
            onClick={handleDecrement}
          >
            −
          </button>
          <span className="qty-val">{localQty}</span>
          <button 
            type="button" 
            className="qty-btn qty-plus" 
            onClick={handleIncrement}
          >
            ＋
          </button>
        </div>
        <button 
          type="button" 
          className="add-to-cart-btn" 
          onClick={() => {
            onAction(`${localQty} ${item.name}`);
            setLocalQty(1);
          }}
        >
          🛒 CART
        </button>
      </div>
    </div>
  );
}

function RichPayload({ payload, cart = {}, onAction }) {
  if (!payload || !payload.type) return null;

  switch (payload.type) {
    case "menu":
      return (
        <div className="menu-grid">
          {payload.items && payload.items.map((item, idx) => (
            <MenuCard key={idx} item={item} onAction={onAction} />
          ))}
        </div>
      );

    case "cart":
    case "cart_update": {
      const cartObj = payload.type === "cart_update" ? payload.cart : payload;
      if (!cartObj || !cartObj.items || cartObj.items.length === 0) {
        return <div className="cart-card">Your cart is empty.</div>;
      }
      return (
        <div className="cart-card">
          {cartObj.items.map((item, idx) => (
            <div key={idx} className="cart-item-row">
              <div className="cart-item-info">
                <strong>{item.name.replace(/\b\w/g, c => c.toUpperCase())}</strong>
                <span className="cart-item-qty-detail">Qty: {item.quantity} × ₹{item.price.toFixed(2)}</span>
                <span className="cart-item-total">Total: ₹{(item.quantity * item.price).toFixed(2)}</span>
              </div>
              <div className="cart-qty-control">
                <div className="cart-qty-selector">
                  <button 
                    type="button" 
                    className="cart-qty-btn cart-qty-minus" 
                    onClick={() => {
                      if (item.quantity > 1) {
                        onAction(`remove 1 ${item.name}`);
                      } else {
                        onAction(`remove ${item.name}`);
                      }
                    }}
                  >
                    −
                  </button>
                  <span className="cart-qty-val">{item.quantity}</span>
                  <button 
                    type="button" 
                    className="cart-qty-btn cart-qty-plus" 
                    onClick={() => onAction(`1 ${item.name}`)}
                  >
                    ＋
                  </button>
                </div>
                <button 
                  type="button" 
                  className="cart-remove-icon-btn" 
                  onClick={() => onAction(`remove ${item.name}`)}
                  title="Remove item"
                >
                  🗑️
                </button>
              </div>
            </div>
          ))}
          <div className="cart-total-row">
            <span>Total:</span>
            <strong>₹{cartObj.total.toFixed(2)}</strong>
          </div>
          <div className="cart-actions">
            <button 
              type="button" 
              className="checkout-btn" 
              onClick={() => onAction("confirm order")}
            >
              🚀 Confirm Order
            </button>
          </div>
        </div>
      );
    }

    case "receipt":
      return (
        <div className="receipt-card">
          <div className="receipt-header">
            <h4>INVOICE: Order #{payload.order_id}</h4>
            <div className="receipt-status pending">PENDING PAYMENT</div>
          </div>
          <div className="receipt-row">
            <span>Total Amount:</span>
            <strong>₹{payload.total.toFixed(2)}</strong>
          </div>
          <a 
            href={payload.payment_url} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="pay-now-btn"
          >
            💳 Pay ₹{payload.total.toFixed(2)}
          </a>
        </div>
      );

    case "track": {
      const steps = [
        { label: "Placed", key: "pending" },
        { label: "Paid", key: "paid" },
        { label: "Preparing", key: "preparing" },
        { label: "Delivered", key: "delivered" }
      ];
      const currentStatus = payload.status ? payload.status.toLowerCase() : "pending";
      
      // Determine active index
      let activeIndex = 0;
      if (currentStatus === "paid") activeIndex = 1;
      else if (currentStatus === "preparing") activeIndex = 2;
      else if (currentStatus === "delivered" || currentStatus === "completed") activeIndex = 3;

      return (
        <div className="track-card">
          <div className="receipt-header">
            <h4>TRACKING: Order #{payload.order_id}</h4>
            <div className={`receipt-status ${currentStatus}`}>{currentStatus.toUpperCase()}</div>
          </div>
          <div className="stepper">
            {steps.map((step, idx) => (
              <div key={idx} className={`step ${idx <= activeIndex ? "active" : ""}`}>
                <div className="step-dot" />
                <span className="step-label">{step.label}</span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    default:
      return null;
  }
}

function Message({ msg, cart, onAction }) {
  const isBot = msg.role === "bot";

  return (
    <article className={`message ${isBot ? "bot" : "user"}`}>
      {isBot && <div className="message-avatar" aria-hidden="true">🤖</div>}
      <div className="message-body">
        <p>{formatMessage(msg.text)}</p>
        {isBot && msg.payload && (
          <RichPayload payload={msg.payload} cart={cart} onAction={onAction} />
        )}
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
  const [cart, setCart] = useState({});
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const shortSession = useMemo(() => sessionId.slice(0, 8), [sessionId]);

  function updateCartState(payload) {
    if (!payload || !payload.type) return;
    if (payload.type === "cart") {
      const newCart = {};
      (payload.items || []).forEach((item) => {
        newCart[item.name.toLowerCase()] = item.quantity;
      });
      setCart(newCart);
    } else if (payload.type === "cart_update") {
      const newCart = {};
      const cartData = payload.cart;
      if (cartData && cartData.items) {
        cartData.items.forEach((item) => {
          newCart[item.name.toLowerCase()] = item.quantity;
        });
      }
      setCart(newCart);
    } else if (payload.type === "receipt") {
      setCart({});
    }
  }

  useEffect(() => {
    const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = isLocalHost
      ? `${wsProto}//127.0.0.1:8000/ws/${sessionId}`
      : `wss://foodchatbot-production.up.railway.app/ws/${sessionId}`;

    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("WebSocket connection established for session:", sessionId);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "order_status") {
          setMessages((current) => [
            ...current,
            {
              id: crypto.randomUUID(),
              role: "bot",
              text: `🎉 Payment confirmed for Order #${data.order_id}! We have started preparing your meal.`,
              payload: {
                type: "track",
                order_id: data.order_id,
                status: "paid"
              },
              time: now(),
            },
          ]);
        }
      } catch (err) {
        console.error("Error parsing WebSocket message:", err);
      }
    };

    return () => {
      socket.close();
    };
  }, [sessionId]);

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

    // Detect HTTPS Mixed Content block issue
    const isHttps = window.location.protocol === "https:";
    const isApiHttp = API_URL && API_URL.startsWith("http://");
    if (isHttps && isApiHttp) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "bot",
          text: `⚠️ Connection Blocked (Mixed Content):\nThe frontend is hosted on secure HTTPS (${window.location.hostname}), but the configured backend URL is insecure HTTP (${API_URL}).\n\nBrowsers block secure pages from making HTTP requests to prevent security risks. Please use a secure HTTPS backend URL, or run the frontend locally over HTTP.`,
          time: now(),
        },
      ]);
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, session_id: sessionId }),
      });

      if (!response.ok) {
        let errorDetails = `HTTP ${response.status} ${response.statusText}`;
        try {
          const errData = await response.json();
          if (errData && errData.detail) {
            errorDetails = errData.detail;
          }
        } catch {}
        throw new Error(errorDetails);
      }

      const data = await response.json();
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "bot",
          text: data.response || "I could not find a reply for that.",
          payload: data.payload,
          time: now(),
        },
      ]);
      updateCartState(data.payload);
    } catch (err) {
      console.error("Chat communication error:", err);
      
      const isTypeError = err instanceof TypeError;
      const errorText = isTypeError
        ? `🔌 Connection Error:\nCould not connect to the backend server at "${API_URL || window.location.origin}".\n\nPlease verify that the backend server is running and accessible, and that CORS is enabled.`
        : `⚠️ Server Error:\n${err.message || "An unexpected error occurred."}`;

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "bot",
          text: errorText,
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
        <div className="brand-container">
          <button 
            type="button" 
            className="menu-toggle-btn" 
            onClick={() => setIsDrawerOpen(true)}
            aria-label="Open navigation menu"
          >
            <span className="hamburger-line" />
            <span className="hamburger-line" />
            <span className="hamburger-line" />
          </button>
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">🍔</span>
            <div>
              <h1>FoodieBot</h1>
              <p>Fast food ordering assistant</p>
            </div>
          </div>
        </div>
        <div className="connection">
          <span aria-hidden="true" />
          Online
        </div>
      </header>

      {/* Mobile Drawer Overlay */}
      {isDrawerOpen && (
        <div 
          className="drawer-overlay" 
          onClick={() => setIsDrawerOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile Drawer Sidebar */}
      <div className={`drawer-sidebar ${isDrawerOpen ? "open" : ""}`}>
        <div className="drawer-header">
          <h2>Menu & Actions</h2>
          <button 
            type="button" 
            className="drawer-close-btn" 
            onClick={() => setIsDrawerOpen(false)}
            aria-label="Close navigation menu"
          >
            ✕
          </button>
        </div>
        <div className="drawer-body">
          <div className="drawer-section">
            <span className="eyebrow">Quick Actions</span>
            <div className="drawer-quick-actions">
              {QUICK_ACTIONS.map((action) => (
                <button
                  key={action.label}
                  className="action-card"
                  type="button"
                  onClick={() => {
                    sendMessage(action.prompt);
                    setIsDrawerOpen(false);
                  }}
                  disabled={loading}
                >
                  <span className="action-icon" aria-hidden="true">{action.icon}</span>
                  <span>
                    <strong>{action.label}</strong>
                    <small>{action.hint}</small>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="drawer-section">
            <span className="eyebrow">Ordering Flow</span>
            <ol className="drawer-flow-list">
              <li>Open the menu</li>
              <li>Add items with quantity</li>
              <li>Check your cart</li>
              <li>Confirm the order</li>
            </ol>
          </div>
        </div>
      </div>

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
            <div className="chat-panel-header-top">
              <div>
                <span className="eyebrow">Live Chat</span>
                <h2>What are we ordering?</h2>
              </div>
              <span className="session-chip">#{shortSession}</span>
            </div>

            <div className="mobile-actions-row" aria-label="Quick Actions">
              {QUICK_ACTIONS.map((action) => (
                <button
                  key={action.label}
                  type="button"
                  onClick={() => sendMessage(action.prompt)}
                  disabled={loading}
                >
                  <span className="mobile-action-icon">{action.icon}</span>
                  {action.label}
                </button>
              ))}
            </div>
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
              <Message key={message.id} msg={message} cart={cart} onAction={sendMessage} />
            ))}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>

          <form className="composer" onSubmit={submitMessage}>
            <input
              ref={inputRef}
              id="composer-input"
              name="message"
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
