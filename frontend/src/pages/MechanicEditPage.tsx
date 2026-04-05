import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Wrench, Loader2, MapPin } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/Button";
import { getMechanicProfile, updateMechanicProfile } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";

export function MechanicEditPage() {
  const navigate = useNavigate();
  const session = useAuthStore((s) => s.session);
  const userId = session?.user?.id ?? "anon-mechanic";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [bio, setBio] = useState("");
  const [skills, setSkills] = useState("");
  const [serviceRadius, setServiceRadius] = useState(25);
  const [hourlyRate, setHourlyRate] = useState("");
  const [latitude, setLatitude] = useState<number | null>(null);
  const [longitude, setLongitude] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMechanicProfile(userId).then((p) => {
      if (p) {
        setName(p.name);
        setEmail(p.email ?? "");
        setPhone(p.phone ?? "");
        setBio(p.bio ?? "");
        setSkills(p.skills ?? "");
        setServiceRadius(p.service_radius_mi ?? 25);
        setHourlyRate(p.hourly_rate_cents != null ? String(p.hourly_rate_cents / 100) : "");
        setLatitude(p.latitude ?? null);
        setLongitude(p.longitude ?? null);
      } else {
        setLoadError("Not registered");
      }
    }).catch(() => setLoadError("Could not load profile"));
  }, [userId]);

  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      setError("Geolocation not supported");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatitude(pos.coords.latitude);
        setLongitude(pos.coords.longitude);
        setError(null);
      },
      () => setError("Could not get location"),
      { enableHighAccuracy: true }
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await updateMechanicProfile(
        {
          name: name.trim(),
          email: email.trim() || undefined,
          phone: phone.trim() || undefined,
          bio: bio.trim() || undefined,
          skills: skills.trim() || undefined,
          service_radius_mi: serviceRadius,
          hourly_rate_cents: hourlyRate ? Math.round(parseFloat(hourlyRate) * 100) : undefined,
          latitude: latitude ?? undefined,
          longitude: longitude ?? undefined,
        },
        userId
      );
      navigate("/mechanic/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setLoading(false);
    }
  };

  if (loadError) {
    return (
      <div className="min-h-screen bg-base text-text flex flex-col">
        <Header />
        <main className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
          <div className="rounded-lg p-6 border border-surface1 bg-surface0 text-center">
            <p className="text-subtext mb-4">{loadError}</p>
            <Button variant="primary" onClick={() => navigate("/mechanic/register")}>
              Register as mechanic
            </Button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-base text-text flex flex-col">
      <Header />
      <main className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
        <div className="flex items-center gap-2 mb-6">
          <div className="p-2 rounded-lg bg-primary/10">
            <Wrench size={24} className="text-primary" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">Edit profile</h1>
            <p className="text-sm text-subtext">Update your mechanic profile.</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your business or display name"
              className="w-full px-3 py-2.5 rounded-lg bg-mantle border border-surface1 text-text placeholder:text-overlay1 focus:outline-none focus:ring-2 focus:ring-primary/50"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="contact@example.com"
              className="w-full px-3 py-2.5 rounded-lg bg-mantle border border-surface1 text-text placeholder:text-overlay1 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">Phone</label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+1 (555) 000-0000"
              className="w-full px-3 py-2.5 rounded-lg bg-mantle border border-surface1 text-text placeholder:text-overlay1 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">Service radius (miles)</label>
            <input
              type="number"
              min={5}
              max={100}
              value={serviceRadius}
              onChange={(e) => setServiceRadius(parseInt(e.target.value, 10) || 25)}
              className="w-full px-3 py-2.5 rounded-lg bg-mantle border border-surface1 text-text focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">Hourly rate ($)</label>
            <input
              type="number"
              min={0}
              step={0.01}
              value={hourlyRate}
              onChange={(e) => setHourlyRate(e.target.value)}
              placeholder="e.g. 75.00"
              className="w-full px-3 py-2.5 rounded-lg bg-mantle border border-surface1 text-text placeholder:text-overlay1 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">Skills (comma-separated)</label>
            <input
              type="text"
              value={skills}
              onChange={(e) => setSkills(e.target.value)}
              placeholder="brakes, engine, electrical"
              className="w-full px-3 py-2.5 rounded-lg bg-mantle border border-surface1 text-text placeholder:text-overlay1 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">Bio</label>
            <textarea
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder="Brief description of your experience"
              rows={3}
              className="w-full px-3 py-2.5 rounded-lg bg-mantle border border-surface1 text-text placeholder:text-overlay1 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
          <div>
            <p className="text-sm font-medium text-text mb-1.5">Location</p>
            <Button type="button" variant="secondary" size="sm" onClick={handleGetLocation}>
              <MapPin size={14} />
              Use my location
            </Button>
            {latitude != null && longitude != null && (
              <p className="text-xs text-green mt-1">Set: {latitude.toFixed(4)}, {longitude.toFixed(4)}</p>
            )}
          </div>
          {error && <p className="text-sm text-red">{error}</p>}
          <Button type="submit" variant="primary" className="w-full" disabled={loading}>
            {loading ? <Loader2 size={18} className="animate-spin" /> : <Wrench size={18} />}
            {loading ? "Saving…" : "Save changes"}
          </Button>
        </form>
      </main>
    </div>
  );
}
