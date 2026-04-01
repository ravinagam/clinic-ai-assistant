import React, { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8080";

interface Appointment {
  id: number;
  scheduled_at: string;
  status: string;
  reason: string;
  doctor_name: string;
  patient_name: string;
  patient_phone: string;
}

function addDays(d: Date, n: number) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function toYMD(d: Date) {
  return d.toISOString().split("T")[0];
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, padding: "20px 24px", borderLeft: `4px solid ${color}`, boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}>
      <div style={{ fontSize: 28, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>{label}</div>
    </div>
  );
}

export default function Dashboard() {
  const [byDay, setByDay] = useState<Record<string, Appointment[]>>({});
  const [loading, setLoading] = useState(true);

  const today = new Date();
  const dates = [today, addDays(today, 1), addDays(today, 2)];

  useEffect(() => {
    const fetchAll = async () => {
      const results: Record<string, Appointment[]> = {};
      await Promise.all(
        dates.map(async (d) => {
          const key = toYMD(d);
          try {
            const res = await fetch(`${API}/staff/appointments?target_date=${key}`);
            const data = await res.json();
            results[key] = Array.isArray(data) ? data : [];
          } catch {
            results[key] = [];
          }
        })
      );
      setByDay(results);
      setLoading(false);
    };
    fetchAll();
  }, []);

  const allApts = Object.values(byDay).flat();
  const todayApts = byDay[toYMD(today)] || [];
  const scheduled = allApts.filter((a) => a.status === "scheduled" || a.status === "confirmed").length;
  const cancelled = allApts.filter((a) => a.status === "cancelled").length;

  const dayLabel = (d: Date) =>
    d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Overview</h1>
      <p style={{ color: "#64748b", marginBottom: 24 }}>
        {today.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 32 }}>
        <StatCard label="Next 3 Days" value={allApts.length} color="#2563eb" />
        <StatCard label="Scheduled / Confirmed" value={scheduled} color="#16a34a" />
        <StatCard label="Cancelled" value={cancelled} color="#dc2626" />
      </div>

      {loading ? (
        <div style={{ padding: 20, color: "#64748b" }}>Loading…</div>
      ) : (
        dates.map((d) => {
          const key = toYMD(d);
          const apts = byDay[key] || [];
          const isToday = key === toYMD(today);
          return (
            <div key={key} style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px rgba(0,0,0,0.07)", overflow: "hidden", marginBottom: 20 }}>
              <div style={{ padding: "14px 20px", borderBottom: "1px solid #f1f5f9", fontWeight: 600, display: "flex", alignItems: "center", gap: 10 }}>
                {dayLabel(d)}
                {isToday && <span style={{ background: "#dbeafe", color: "#2563eb", fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 20 }}>TODAY</span>}
                <span style={{ marginLeft: "auto", fontSize: 13, color: "#64748b", fontWeight: 400 }}>{apts.length} appointment{apts.length !== 1 ? "s" : ""}</span>
              </div>
              {apts.length === 0 ? (
                <div style={{ padding: "14px 20px", color: "#94a3b8", fontSize: 13 }}>No appointments</div>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", fontSize: 12, color: "#64748b" }}>
                      {["#", "Time", "Patient", "Doctor", "Reason", "Status"].map((h) => (
                        <th key={h} style={{ padding: "8px 16px", textAlign: "left", fontWeight: 600 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {apts.map((a) => (
                      <tr key={a.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "11px 16px", fontSize: 13, color: "#94a3b8" }}>#{a.id}</td>
                        <td style={{ padding: "11px 16px", fontSize: 13, fontWeight: 500 }}>
                          {new Date(a.scheduled_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                        </td>
                        <td style={{ padding: "11px 16px", fontSize: 13 }}>
                          <div>{a.patient_name}</div>
                          <div style={{ fontSize: 11, color: "#94a3b8" }}>{a.patient_phone}</div>
                        </td>
                        <td style={{ padding: "11px 16px", fontSize: 13 }}>Dr. {a.doctor_name}</td>
                        <td style={{ padding: "11px 16px", fontSize: 13 }}>{a.reason || "—"}</td>
                        <td style={{ padding: "11px 16px" }}>
                          <span style={{
                            padding: "3px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600,
                            background: a.status === "cancelled" ? "#fee2e2" : a.status === "confirmed" ? "#dcfce7" : "#dbeafe",
                            color: a.status === "cancelled" ? "#dc2626" : a.status === "confirmed" ? "#16a34a" : "#2563eb",
                          }}>
                            {a.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
