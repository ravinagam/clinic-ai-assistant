import React, { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8080";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

interface Doctor {
  id: number;
  name: string;
  specialty: string | null;
  phone: string | null;
  email: string | null;
}

interface Availability {
  id: number;
  day_of_week: number;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
}

export default function Doctors() {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", specialty: "", phone: "", email: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selDoctor, setSelDoctor] = useState<number | null>(null);
  const [availability, setAvailability] = useState<Availability[]>([]);
  const [avSaving, setAvSaving] = useState(false);
  const [avSuccess, setAvSuccess] = useState(false);
  const [avForm, setAvForm] = useState({
    day_of_week: 0,
    start_time: "09:00",
    end_time: "17:00",
    slot_duration_minutes: 20,
  });

  // PIN management
  const [pinDoctor, setPinDoctor] = useState<number | null>(null);
  const [pin, setPin] = useState("");
  const [pinMsg, setPinMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const fetchDoctors = async () => {
    try {
      const res = await fetch(`${API}/staff/doctors`);
      const data = await res.json();
      setDoctors(Array.isArray(data) ? data : []);
    } finally {
      setLoading(false);
    }
  };

  const fetchAvailability = async (doctorId: number) => {
    const res = await fetch(`${API}/staff/availability/${doctorId}`);
    const data = await res.json();
    setAvailability(Array.isArray(data) ? data : []);
  };

  useEffect(() => { fetchDoctors(); }, []);

  const selectDoctor = (id: number) => {
    if (selDoctor === id) {
      setSelDoctor(null);
      setAvailability([]);
    } else {
      setSelDoctor(id);
      setAvailability([]);
      fetchAvailability(id);
    }
  };

  const addDoctor = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API}/staff/doctors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      setForm({ name: "", specialty: "", phone: "", email: "" });
      await fetchDoctors();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect. Check ALLOWED_ORIGINS in .env.");
    } finally {
      setSaving(false);
    }
  };

  const savePin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pinDoctor) return;
    setPinMsg(null);
    try {
      const res = await fetch(`${API}/staff/doctors/${pinDoctor}/set-pin`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to set PIN.");
      setPinMsg({ ok: true, text: data.message });
      setPin("");
    } catch (err) {
      setPinMsg({ ok: false, text: err instanceof Error ? err.message : "Error" });
    }
  };

  const addAvailability = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selDoctor) return;
    setAvSaving(true);
    setAvSuccess(false);
    try {
      const res = await fetch(`${API}/staff/availability`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...avForm, doctor_id: selDoctor }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      setAvSuccess(true);
      await fetchAvailability(selDoctor);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save availability.");
    } finally {
      setAvSaving(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    padding: "8px 12px",
    borderRadius: 8,
    border: "1px solid #e2e8f0",
    fontSize: 14,
    width: "100%",
  };

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24 }}>Doctors</h1>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>

        {/* Add Doctor */}
        <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Add Doctor</h2>
          {error && (
            <div style={{ background: "#fee2e2", color: "#dc2626", padding: "10px 12px", borderRadius: 8, fontSize: 13, marginBottom: 12 }}>
              {error}
            </div>
          )}
          <form onSubmit={addDoctor} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <input required placeholder="Full name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={inputStyle} />
            <input placeholder="Specialty" value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} style={inputStyle} />
            <input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} style={inputStyle} />
            <input type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} style={inputStyle} />
            <button type="submit" disabled={saving}
              style={{ background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, padding: "10px", cursor: "pointer", fontWeight: 600 }}>
              {saving ? "Saving…" : "Add Doctor"}
            </button>
          </form>
        </div>

        {/* Doctor List */}
        <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Current Doctors</h2>
          {loading ? <p style={{ color: "#64748b" }}>Loading…</p> : doctors.length === 0 ? (
            <p style={{ color: "#64748b" }}>No doctors added yet.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {doctors.map((d) => (
                <div key={d.id} style={{ padding: "12px 14px", borderRadius: 8, background: selDoctor === d.id ? "#eff6ff" : "#f8fafc", border: `1px solid ${selDoctor === d.id ? "#bfdbfe" : "transparent"}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>Dr. {d.name}</div>
                    <div style={{ fontSize: 12, color: "#64748b" }}>{d.specialty || "General"}</div>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button onClick={() => selectDoctor(d.id)}
                      style={{ fontSize: 12, padding: "4px 10px", borderRadius: 6, border: "1px solid #e2e8f0", background: selDoctor === d.id ? "#2563eb" : "#fff", color: selDoctor === d.id ? "#fff" : "#1e293b", cursor: "pointer" }}>
                      {selDoctor === d.id ? "✓ Selected" : "Set Availability"}
                    </button>
                    <button onClick={() => { setPinDoctor(d.id === pinDoctor ? null : d.id); setPinMsg(null); setPin(""); }}
                      style={{ fontSize: 12, padding: "4px 10px", borderRadius: 6, border: "1px solid #e2e8f0", background: pinDoctor === d.id ? "#7c3aed" : "#fff", color: pinDoctor === d.id ? "#fff" : "#1e293b", cursor: "pointer" }}>
                      🔑 PIN
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Set PIN Panel */}
        {pinDoctor && (
          <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.07)", gridColumn: "1 / -1" }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
              Set Doctor PIN — Dr. {doctors.find((d) => d.id === pinDoctor)?.name}
            </h2>
            <p style={{ fontSize: 13, color: "#64748b", marginBottom: 16 }}>
              The doctor will use this 4–6 digit PIN to log in to their personal schedule view.
            </p>
            {pinMsg && (
              <div style={{ background: pinMsg.ok ? "#f0fdf4" : "#fee2e2", color: pinMsg.ok ? "#16a34a" : "#dc2626", padding: "10px 12px", borderRadius: 8, fontSize: 13, marginBottom: 12 }}>
                {pinMsg.text}
              </div>
            )}
            <form onSubmit={savePin} style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
              <div>
                <label style={{ fontSize: 12, color: "#64748b", display: "block", marginBottom: 6 }}>New PIN (4–6 digits)</label>
                <input
                  type="password"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="e.g. 1234"
                  value={pin}
                  onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
                  required
                  style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 16, letterSpacing: 6, width: 140 }}
                />
              </div>
              <button type="submit"
                style={{ background: "#7c3aed", color: "#fff", border: "none", borderRadius: 8, padding: "9px 20px", cursor: "pointer", fontWeight: 600, fontSize: 14 }}>
                Save PIN
              </button>
            </form>
          </div>
        )}

        {/* Availability Panel */}
        {selDoctor && (
          <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.07)", gridColumn: "1 / -1" }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>
              Weekly Availability — Dr. {doctors.find((d) => d.id === selDoctor)?.name}
            </h2>

            {/* Existing availability table */}
            {availability.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#64748b", marginBottom: 8 }}>Current Schedule</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {availability
                    .slice()
                    .sort((a, b) => a.day_of_week - b.day_of_week)
                    .map((av) => (
                      <div key={av.id} style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: "8px 14px", fontSize: 13 }}>
                        <strong>{DAYS[av.day_of_week]}</strong>
                        {" "}{av.start_time.slice(0, 5)} – {av.end_time.slice(0, 5)}
                        {" "}· {av.slot_duration_minutes} min slots
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Add new availability */}
            <div style={{ fontSize: 13, fontWeight: 600, color: "#64748b", marginBottom: 8 }}>Add Availability Window</div>
            {avSuccess && (
              <div style={{ background: "#f0fdf4", color: "#16a34a", padding: "10px 12px", borderRadius: 8, fontSize: 13, marginBottom: 12 }}>
                ✓ Availability saved successfully!
              </div>
            )}
            <form onSubmit={addAvailability} style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, alignItems: "end" }}>
              <div>
                <label style={{ fontSize: 12, color: "#64748b", display: "block", marginBottom: 6 }}>Day</label>
                <select value={avForm.day_of_week} onChange={(e) => { setAvForm({ ...avForm, day_of_week: +e.target.value }); setAvSuccess(false); }} style={inputStyle}>
                  {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, color: "#64748b", display: "block", marginBottom: 6 }}>Start Time</label>
                <input type="time" value={avForm.start_time} onChange={(e) => { setAvForm({ ...avForm, start_time: e.target.value }); setAvSuccess(false); }} style={inputStyle} />
              </div>
              <div>
                <label style={{ fontSize: 12, color: "#64748b", display: "block", marginBottom: 6 }}>End Time</label>
                <input type="time" value={avForm.end_time} onChange={(e) => { setAvForm({ ...avForm, end_time: e.target.value }); setAvSuccess(false); }} style={inputStyle} />
              </div>
              <div>
                <label style={{ fontSize: 12, color: "#64748b", display: "block", marginBottom: 6 }}>Slot (mins)</label>
                <input type="number" min={10} max={60} value={avForm.slot_duration_minutes} onChange={(e) => { setAvForm({ ...avForm, slot_duration_minutes: +e.target.value }); setAvSuccess(false); }} style={inputStyle} />
              </div>
              <button type="submit" disabled={avSaving}
                style={{ gridColumn: "1 / -1", background: "#16a34a", color: "#fff", border: "none", borderRadius: 8, padding: 10, cursor: "pointer", fontWeight: 600 }}>
                {avSaving ? "Saving…" : "Save Availability"}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
