import React, { useState } from "react";
import ChatWidget from "./ChatWidget";

const CLINIC_NAME = import.meta.env.VITE_CLINIC_NAME || "City Health Clinic";

export default function App() {
  const [open, setOpen] = useState(true);

  return (
    <>
      {/* Page header */}
      <header style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        height: 52,
        background: "#2563eb",
        color: "#fff",
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        gap: 10,
        boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
        zIndex: 9997,
      }}>
        <span style={{ fontSize: 20 }}>🏥</span>
        <span style={{ fontSize: 16, fontWeight: 700 }}>{CLINIC_NAME}</span>
        <span style={{
          marginLeft: 8,
          background: "rgba(255,255,255,0.18)",
          fontSize: 11,
          fontWeight: 600,
          padding: "2px 10px",
          borderRadius: 20,
        }}>AI Reception</span>
      </header>

      {/* Floating toggle button */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          position: "fixed",
          bottom: 24,
          right: 24,
          width: 56,
          height: 56,
          borderRadius: "50%",
          background: "#2563eb",
          border: "none",
          cursor: "pointer",
          boxShadow: "0 4px 14px rgba(0,0,0,0.25)",
          fontSize: 24,
          color: "#fff",
          zIndex: 9999,
        }}
        aria-label="Toggle chat"
      >
        {open ? "✕" : "💬"}
      </button>

      {/* Chat panel */}
      {open && (
        <div style={{
          position: "fixed",
          bottom: 92,
          right: 24,
          width: 360,
          height: 520,
          borderRadius: 16,
          boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
          background: "#fff",
          zIndex: 9998,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}>
          <ChatWidget />
        </div>
      )}
    </>
  );
}
