import React, { useEffect, useState, useRef } from "react";
import { useSpeechToText } from "../hooks/useSpeechToText";

const API = import.meta.env.VITE_API_URL || "http://localhost:8080";

interface Doctor { id: number; name: string; specialty: string | null; }

interface Appointment {
  id: number;
  scheduled_at: string;
  status: string;
  reason: string;
  notes: string | null;
  channel: string;
  patient_name: string;
  patient_phone: string;
  patient_email: string | null;
}

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  scheduled:  { bg: "#dbeafe", color: "#2563eb" },
  confirmed:  { bg: "#dcfce7", color: "#16a34a" },
  completed:  { bg: "#f0fdf4", color: "#15803d" },
  no_show:    { bg: "#fef9c3", color: "#a16207" },
  cancelled:  { bg: "#fee2e2", color: "#dc2626" },
};

function groupByDay(apts: Appointment[]): Record<string, Appointment[]> {
  return apts.reduce((acc, a) => {
    const day = new Date(a.scheduled_at).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });
    acc[day] = acc[day] || [];
    acc[day].push(a);
    return acc;
  }, {} as Record<string, Appointment[]>);
}

function LoginScreen({ onLogin }: { onLogin: (token: string, name: string, specialty: string) => void }) {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [doctorId, setDoctorId] = useState<number | "">("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API}/staff/doctors`).then(r => r.json()).then(d => setDoctors(Array.isArray(d) ? d : []));
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!doctorId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/doctor/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doctor_id: doctorId, pin }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Login failed.");
      onLogin(data.token, data.doctor_name, data.specialty || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "70vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "#fff", borderRadius: 16, padding: 40, boxShadow: "0 4px 24px rgba(0,0,0,0.10)", width: 380 }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 44, marginBottom: 10 }}>👨‍⚕️</div>
          <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Doctor Login</h2>
          <p style={{ fontSize: 13, color: "#64748b", marginTop: 6 }}>Select your name and enter your PIN</p>
        </div>

        {error && (
          <div style={{ background: "#fee2e2", color: "#dc2626", padding: "10px 14px", borderRadius: 8, fontSize: 13, marginBottom: 16 }}>
            {error}
          </div>
        )}

        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: "#64748b", display: "block", marginBottom: 6 }}>Your Name</label>
            <select
              value={doctorId}
              onChange={e => setDoctorId(Number(e.target.value))}
              required
              style={{ width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 14 }}
            >
              <option value="">Select doctor…</option>
              {doctors.map(d => <option key={d.id} value={d.id}>Dr. {d.name}{d.specialty ? ` — ${d.specialty}` : ""}</option>)}
            </select>
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: "#64748b", display: "block", marginBottom: 6 }}>PIN</label>
            <input
              type="password"
              inputMode="numeric"
              maxLength={6}
              placeholder="••••"
              value={pin}
              onChange={e => setPin(e.target.value.replace(/\D/g, ""))}
              required
              style={{ width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 24, letterSpacing: 12, textAlign: "center", boxSizing: "border-box" }}
            />
          </div>

          <button
            type="submit"
            disabled={loading || !doctorId || pin.length < 4}
            style={{ background: "#0f766e", color: "#fff", border: "none", borderRadius: 8, padding: "13px", fontWeight: 700, fontSize: 15, cursor: "pointer", opacity: loading ? 0.7 : 1, marginTop: 4 }}
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}

function AppointmentCard({ apt, token, onUpdate }: {
  apt: Appointment;
  token: string;
  onUpdate: () => void;
}) {
  const [status, setStatus] = useState(apt.status);
  const [notes, setNotes] = useState(apt.notes || "");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { isRecording, supported, startRecording, stopRecording } = useSpeechToText();

  const sc = STATUS_COLORS[status] || STATUS_COLORS.scheduled;
  const time = new Date(apt.scheduled_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });

  const handleDictate = () => {
    if (isRecording) {
      stopRecording();
      return;
    }
    setEditing(true);
    startRecording((transcript) => {
      setNotes(prev => prev ? prev + " " + transcript : transcript);
      setSaved(false);
    });
  };

  // Auto-focus textarea when editing opens
  useEffect(() => {
    if (editing) textareaRef.current?.focus();
  }, [editing]);

  const save = async () => {
    if (isRecording) stopRecording();
    setSaving(true);
    setSaved(false);
    try {
      await fetch(`${API}/doctor/appointments/${apt.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({ status, notes }),
      });
      setSaved(true);
      setEditing(false);
      onUpdate();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      background: "#fff",
      borderRadius: 12,
      padding: 18,
      boxShadow: "0 1px 4px rgba(0,0,0,0.07)",
      borderLeft: `4px solid ${sc.color}`,
      display: "flex",
      flexDirection: "column",
      gap: 10,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>{apt.patient_name}</div>
          <div style={{ fontSize: 12, color: "#64748b" }}>{apt.patient_phone}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontWeight: 700, fontSize: 16, color: "#0f766e" }}>{time}</div>
          <span style={{ background: sc.bg, color: sc.color, fontSize: 11, fontWeight: 700, padding: "2px 10px", borderRadius: 20 }}>
            {status}
          </span>
        </div>
      </div>

      {apt.reason && (
        <div style={{ fontSize: 13, background: "#f8fafc", borderRadius: 8, padding: "8px 12px", color: "#475569" }}>
          <span style={{ fontWeight: 600 }}>Reason: </span>{apt.reason}
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        {["confirmed", "completed", "no_show"].map(s => (
          <button
            key={s}
            onClick={() => { setStatus(s); setSaved(false); }}
            style={{
              fontSize: 12,
              padding: "4px 12px",
              borderRadius: 20,
              border: `1px solid ${status === s ? STATUS_COLORS[s]?.color : "#e2e8f0"}`,
              background: status === s ? (STATUS_COLORS[s]?.bg || "#f1f5f9") : "#fff",
              color: status === s ? (STATUS_COLORS[s]?.color || "#1e293b") : "#64748b",
              cursor: "pointer",
              fontWeight: status === s ? 700 : 400,
            }}
          >
            {s === "completed" ? "✓ Completed" : s === "no_show" ? "✗ No Show" : "✓ Confirmed"}
          </button>
        ))}

        <button
          onClick={() => { setEditing(v => !v); if (isRecording) stopRecording(); }}
          style={{ fontSize: 12, padding: "4px 12px", borderRadius: 20, border: "1px solid #e2e8f0", background: editing ? "#f1f5f9" : "#fff", cursor: "pointer", color: "#475569" }}
        >
          {editing ? "✕ Cancel" : "📝 Notes"}
        </button>

        {/* Mic button — only shown if browser supports it */}
        {supported && (
          <button
            onClick={handleDictate}
            title={isRecording ? "Stop recording" : "Dictate notes"}
            style={{
              fontSize: 12,
              padding: "4px 12px",
              borderRadius: 20,
              border: `1px solid ${isRecording ? "#dc2626" : "#e2e8f0"}`,
              background: isRecording ? "#fee2e2" : "#fff",
              color: isRecording ? "#dc2626" : "#475569",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontWeight: isRecording ? 700 : 400,
              animation: isRecording ? "pulse 1.2s infinite" : "none",
            }}
          >
            <span style={{ fontSize: 14 }}>{isRecording ? "⏹" : "🎤"}</span>
            {isRecording ? "Stop" : "Dictate"}
          </button>
        )}
      </div>

      {/* Recording indicator */}
      {isRecording && (
        <div style={{
          fontSize: 12,
          color: "#dc2626",
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 10px",
          background: "#fff5f5",
          borderRadius: 8,
          border: "1px solid #fecaca",
        }}>
          <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "#dc2626", animation: "pulse 1s infinite" }} />
          Listening… speak your notes clearly
        </div>
      )}

      {/* Notes textarea */}
      {editing && (
        <textarea
          ref={textareaRef}
          value={notes}
          onChange={e => { setNotes(e.target.value); setSaved(false); }}
          placeholder="Consultation notes, diagnosis, prescription… or use 🎤 Dictate"
          rows={4}
          style={{
            width: "100%",
            padding: "8px 12px",
            borderRadius: 8,
            border: isRecording ? "1px solid #dc2626" : "1px solid #e2e8f0",
            fontSize: 13,
            resize: "vertical",
            fontFamily: "inherit",
            boxSizing: "border-box",
            transition: "border-color 0.2s",
          }}
        />
      )}

      {/* Existing saved notes (read view) */}
      {!editing && notes && (
        <div style={{ fontSize: 13, background: "#fffbeb", borderRadius: 8, padding: "8px 12px", color: "#78350f", whiteSpace: "pre-wrap" }}>
          <span style={{ fontWeight: 600 }}>Notes: </span>{notes}
        </div>
      )}

      {(status !== apt.status || notes !== (apt.notes || "")) && !saved && (
        <button
          onClick={save}
          disabled={saving}
          style={{ background: "#0f766e", color: "#fff", border: "none", borderRadius: 8, padding: "9px", fontWeight: 700, cursor: "pointer", fontSize: 13 }}
        >
          {saving ? "Saving…" : "Save Changes"}
        </button>
      )}
      {saved && <div style={{ fontSize: 12, color: "#16a34a", textAlign: "center" }}>✓ Saved</div>}
    </div>
  );
}

export default function DoctorPortal() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("doctor_token"));
  const [doctorName, setDoctorName] = useState(() => localStorage.getItem("doctor_name") || "");
  const [specialty, setSpecialty] = useState(() => localStorage.getItem("doctor_specialty") || "");
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"today" | "week">("today");

  const login = (t: string, name: string, spec: string) => {
    localStorage.setItem("doctor_token", t);
    localStorage.setItem("doctor_name", name);
    localStorage.setItem("doctor_specialty", spec);
    setToken(t);
    setDoctorName(name);
    setSpecialty(spec);
  };

  const logout = () => {
    localStorage.removeItem("doctor_token");
    localStorage.removeItem("doctor_name");
    localStorage.removeItem("doctor_specialty");
    setToken(null);
    setAppointments([]);
  };

  const fetchAppointments = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const days = tab === "today" ? 1 : 7;
      const res = await fetch(`${API}/doctor/appointments?days=${days}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { logout(); return; }
      const data = await res.json();
      setAppointments(Array.isArray(data) ? data : []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAppointments(); }, [token, tab]);

  if (!token) return <LoginScreen onLogin={login} />;

  const todayStr = new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });
  const todayApts = appointments.filter(a => {
    const d = new Date(a.scheduled_at).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });
    return d === todayStr;
  });
  const grouped = groupByDay(appointments);

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Dr. {doctorName}</h1>
          <div style={{ fontSize: 13, color: "#64748b", marginTop: 3 }}>{specialty || "Doctor"}</div>
        </div>
        <button
          onClick={logout}
          style={{ fontSize: 12, padding: "6px 14px", borderRadius: 8, border: "1px solid #e2e8f0", background: "#fff", cursor: "pointer", color: "#64748b" }}
        >
          Sign Out
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Today", value: todayApts.length, color: "#0f766e" },
          { label: tab === "today" ? "Completed" : "This Week", value: tab === "today" ? todayApts.filter(a => a.status === "completed").length : appointments.length, color: "#16a34a" },
          { label: "No Shows", value: appointments.filter(a => a.status === "no_show").length, color: "#dc2626" },
        ].map(s => (
          <div key={s.label} style={{ background: "#fff", borderRadius: 12, padding: "16px 20px", borderLeft: `4px solid ${s.color}`, boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 0, marginBottom: 20, background: "#fff", borderRadius: 10, padding: 4, boxShadow: "0 1px 4px rgba(0,0,0,0.07)", width: "fit-content" }}>
        {(["today", "week"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "8px 24px", borderRadius: 8, border: "none",
              background: tab === t ? "#0f766e" : "transparent",
              color: tab === t ? "#fff" : "#64748b",
              fontWeight: tab === t ? 700 : 400,
              cursor: "pointer", fontSize: 13,
            }}
          >
            {t === "today" ? "Today" : "This Week"}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ padding: 24, color: "#64748b" }}>Loading…</div>
      ) : appointments.length === 0 ? (
        <div style={{ background: "#fff", borderRadius: 12, padding: 32, textAlign: "center", color: "#94a3b8", boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🗓️</div>
          <div style={{ fontWeight: 600 }}>No appointments {tab === "today" ? "today" : "this week"}</div>
        </div>
      ) : tab === "today" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {todayApts.length === 0 ? (
            <div style={{ padding: 24, color: "#94a3b8", textAlign: "center" }}>No appointments today</div>
          ) : todayApts.map(a => (
            <AppointmentCard key={a.id} apt={a} token={token} onUpdate={fetchAppointments} />
          ))}
        </div>
      ) : (
        Object.entries(grouped).map(([day, apts]) => (
          <div key={day} style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#475569", marginBottom: 10, display: "flex", alignItems: "center", gap: 8 }}>
              {day}
              {day === todayStr && <span style={{ background: "#ccfbf1", color: "#0f766e", fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 20 }}>TODAY</span>}
              <span style={{ fontWeight: 400, color: "#94a3b8" }}>· {apts.length} appointment{apts.length !== 1 ? "s" : ""}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {apts.map(a => <AppointmentCard key={a.id} apt={a} token={token} onUpdate={fetchAppointments} />)}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
