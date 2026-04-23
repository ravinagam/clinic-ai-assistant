import React from "react";
import DoctorPortal from "./pages/DoctorPortal";

const CLINIC_NAME = import.meta.env.VITE_CLINIC_NAME || "City Health Clinic";

export default function App() {
  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <header style={{
        background: "#0f766e",
        color: "#fff",
        padding: "0 28px",
        height: 56,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
        boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 22 }}>🏥</span>
          <span style={{ fontSize: 17, fontWeight: 700 }}>{CLINIC_NAME}</span>
          <span style={{
            marginLeft: 12,
            background: "rgba(255,255,255,0.18)",
            fontSize: 11,
            fontWeight: 600,
            padding: "2px 10px",
            borderRadius: 20,
            letterSpacing: 0.5,
          }}>DOCTOR PORTAL</span>
        </div>
        <div style={{ fontSize: 12, opacity: 0.8 }}>
          {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        </div>
      </header>

      <main style={{ flex: 1, padding: 32, overflowY: "auto" }}>
        <DoctorPortal />
      </main>
    </div>
  );
}
