import React, { useState, useRef, useEffect } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8080";

interface Message {
  role: "user" | "assistant";
  text: string;
}

interface ChatResponse {
  session_id: string;
  message: string;
  booking_completed: boolean;
  appointment_id?: number;
}

export default function ChatWidget() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      text: `Hello! Welcome to the clinic. I'm your AI receptionist. How can I help you today?\n\nI can help you:\n• Book an appointment\n• Answer questions about our services\n• Provide clinic information`,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [bookingDone, setBookingDone] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input on mount and after each response
  useEffect(() => {
    if (!loading && !bookingDone) {
      inputRef.current?.focus();
    }
  }, [loading, bookingDone]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });

      const data: ChatResponse = await res.json();
      setSessionId(data.session_id);

      let replyText = data.message;
      if (data.booking_completed && data.appointment_id) {
        setBookingDone(true);
      }

      setMessages((prev) => [...prev, { role: "assistant", text: replyText }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Sorry, I'm having trouble connecting. Please try again or call us directly." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ background: "#2563eb", color: "#fff", padding: "14px 16px", fontWeight: 600, fontSize: 15, display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 20 }}>🏥</span>
        <div>
          <div>AI Receptionist</div>
          <div style={{ fontSize: 11, fontWeight: 400, opacity: 0.85 }}>
            {loading ? "Typing…" : "Online — replies instantly"}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10, background: "#f8fafc" }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "82%",
              padding: "10px 13px",
              borderRadius: msg.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
              background: msg.role === "user" ? "#2563eb" : "#fff",
              color: msg.role === "user" ? "#fff" : "#1e293b",
              fontSize: 13.5,
              lineHeight: 1.5,
              boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
              whiteSpace: "pre-wrap",
            }}>
              {msg.text}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: "flex", justifyContent: "flex-start" }}>
            <div style={{ background: "#fff", borderRadius: "16px 16px 16px 4px", padding: "10px 14px", fontSize: 13, color: "#64748b", boxShadow: "0 1px 3px rgba(0,0,0,0.08)" }}>
              ●●●
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ padding: "10px 12px", borderTop: "1px solid #e2e8f0", display: "flex", gap: 8, background: "#fff" }}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading || bookingDone}
          placeholder={bookingDone ? "Booking complete!" : "Type a message…"}
          rows={1}
          style={{ flex: 1, resize: "none", border: "1px solid #e2e8f0", borderRadius: 10, padding: "9px 12px", fontSize: 13.5, outline: "none", fontFamily: "inherit", lineHeight: 1.4 }}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim() || bookingDone}
          style={{ background: "#2563eb", color: "#fff", border: "none", borderRadius: 10, padding: "0 16px", cursor: "pointer", fontSize: 18, opacity: loading || !input.trim() ? 0.5 : 1 }}
        >
          ➤
        </button>
      </div>
    </div>
  );
}
