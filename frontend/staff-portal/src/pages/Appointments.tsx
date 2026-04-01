import React, { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8080";

interface Appointment {
  id: number;
  scheduled_at: string;
  status: string;
  reason: string;
  channel: string;
  doctor_name: string;
  patient_name: string;
  patient_phone: string;
  notes: string | null;
}

const STATUS_OPTIONS = ["scheduled", "confirmed", "cancelled", "completed", "no_show"];

export default function Appointments() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);
  const [loading, setLoading] = useState(false);
  const [updating, setUpdating] = useState<number | null>(null);

  const fetchAppointments = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/staff/appointments?target_date=${date}`);
      const data = await res.json();
      setAppointments(Array.isArray(data) ? data : []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAppointments(); }, [date]);

  const updateStatus = async (id: number, status: string) => {
    setUpdating(id);
    try {
      await fetch(`${API}/staff/appointments/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      await fetchAppointments();
    } finally {
      setUpdating(null);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700 }}>Appointments</h1>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 14 }}
        />
      </div>

      <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px rgba(0,0,0,0.07)", overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 20, color: "#64748b" }}>Loading…</div>
        ) : appointments.length === 0 ? (
          <div style={{ padding: 20, color: "#64748b" }}>No appointments for this date.</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "#f8fafc", fontSize: 12, color: "#64748b" }}>
                {["#", "Time", "Patient", "Doctor", "Reason", "Channel", "Status", "Action"].map((h) => (
                  <th key={h} style={{ padding: "10px 14px", textAlign: "left", fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {appointments.map((a) => (
                <tr key={a.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                  <td style={{ padding: "11px 14px", fontSize: 13, color: "#94a3b8" }}>#{a.id}</td>
                  <td style={{ padding: "11px 14px", fontSize: 13, fontWeight: 500 }}>
                    {new Date(a.scheduled_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                  </td>
                  <td style={{ padding: "11px 14px", fontSize: 13 }}>
                    <div style={{ fontWeight: 500 }}>{a.patient_name}</div>
                    <div style={{ fontSize: 11, color: "#94a3b8" }}>{a.patient_phone}</div>
                  </td>
                  <td style={{ padding: "11px 14px", fontSize: 13 }}>Dr. {a.doctor_name}</td>
                  <td style={{ padding: "11px 14px", fontSize: 13 }}>{a.reason || "—"}</td>
                  <td style={{ padding: "11px 14px", fontSize: 12 }}>
                    <span style={{ background: "#f1f5f9", padding: "2px 8px", borderRadius: 10 }}>{a.channel}</span>
                  </td>
                  <td style={{ padding: "11px 14px" }}>
                    <span style={{
                      padding: "3px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600,
                      background: a.status === "cancelled" ? "#fee2e2" : a.status === "confirmed" || a.status === "completed" ? "#dcfce7" : "#dbeafe",
                      color: a.status === "cancelled" ? "#dc2626" : a.status === "confirmed" || a.status === "completed" ? "#16a34a" : "#2563eb",
                    }}>
                      {a.status}
                    </span>
                  </td>
                  <td style={{ padding: "11px 14px" }}>
                    <select
                      value={a.status}
                      disabled={updating === a.id}
                      onChange={(e) => updateStatus(a.id, e.target.value)}
                      style={{ padding: "5px 8px", borderRadius: 6, border: "1px solid #e2e8f0", fontSize: 12, cursor: "pointer" }}
                    >
                      {STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
