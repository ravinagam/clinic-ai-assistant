import React, { useState } from "react";
import Dashboard from "./pages/Dashboard";
import Appointments from "./pages/Appointments";
import Doctors from "./pages/Doctors";

const CLINIC_NAME = import.meta.env.VITE_CLINIC_NAME || "City Health Clinic";
const API = import.meta.env.VITE_API_URL || "http://localhost:8080";

type Page = "dashboard" | "appointments" | "doctors";

const NAV: { id: Page; label: string; icon: string }[] = [
  { id: "dashboard", label: "Dashboard", icon: "📊" },
  { id: "appointments", label: "Appointments", icon: "📅" },
  { id: "doctors", label: "Doctors", icon: "👨‍⚕️" },
];

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>

      {/* Top Header */}
      <header style={{
        background: "#2563eb",
        color: "#fff",
        padding: "0 28px",
        height: 56,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
        boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
        zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 22 }}>🏥</span>
          <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: 0.2 }}>{CLINIC_NAME}</span>
          <span style={{
            marginLeft: 12,
            background: "rgba(255,255,255,0.18)",
            fontSize: 11,
            fontWeight: 600,
            padding: "2px 10px",
            borderRadius: 20,
            letterSpacing: 0.5,
          }}>STAFF PORTAL</span>
        </div>
        <div style={{ fontSize: 12, opacity: 0.8 }}>
          {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        </div>
      </header>

      <div style={{ display: "flex", flex: 1 }}>
        {/* Sidebar */}
        <aside style={{
          width: 210,
          background: "#1e293b",
          color: "#fff",
          display: "flex",
          flexDirection: "column",
          padding: "20px 0",
          flexShrink: 0,
        }}>
          <nav>
            {NAV.map((item) => (
              <button
                key={item.id}
                onClick={() => setPage(item.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  width: "100%",
                  padding: "12px 20px",
                  background: page === item.id ? "#2563eb" : "transparent",
                  border: "none",
                  color: "#fff",
                  cursor: "pointer",
                  fontSize: 14,
                  textAlign: "left",
                  borderRadius: page === item.id ? "0 8px 8px 0" : 0,
                  marginRight: page === item.id ? 8 : 0,
                }}
              >
                <span>{item.icon}</span>
                {item.label}
              </button>
            ))}
          </nav>
        </aside>

        {/* Main content */}
        <main style={{ flex: 1, padding: 32, overflowY: "auto", background: "#f1f5f9" }}>
          {page === "dashboard" && <Dashboard />}
          {page === "appointments" && <Appointments />}
          {page === "doctors" && <Doctors />}
        </main>
      </div>
    </div>
  );
}
