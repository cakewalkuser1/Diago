import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Wrench, Loader2, MapPin, Camera, Edit2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/Button";
import { getMechanicProfile, uploadMechanicPhoto } from "@/lib/api";
import { getApiBase } from "@/lib/env";
import { useAuthStore } from "@/stores/authStore";

export function MechanicDashboard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const session = useAuthStore((s) => s.session);
  const userId = session?.user?.id ?? "anon-mechanic";

  const { data: profile, isLoading, error } = useQuery({
    queryKey: ["mechanic-profile", userId],
    queryFn: () => getMechanicProfile(userId),
    retry: (_, err) => err instanceof Error && !err.message.includes("404"),
  });

  const photoMutation = useMutation({
    mutationFn: (file: File) => uploadMechanicPhoto(file, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["mechanic-profile", userId] }),
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-base text-text flex flex-col">
        <Header />
        <main className="flex-1 flex items-center justify-center p-6">
          <Loader2 size={32} className="animate-spin text-primary" />
        </main>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="min-h-screen bg-base text-text flex flex-col">
        <Header />
        <main className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
          <div className="rounded-lg p-6 border border-surface1 bg-surface0 text-center">
            <p className="text-subtext mb-4">
              {error ? "Could not load profile." : "You are not registered as a mechanic."}
            </p>
            <Button variant="primary" onClick={() => navigate("/mechanic/register")}>
              <Wrench size={18} />
              Register as mechanic
            </Button>
          </div>
        </main>
      </div>
    );
  }

  const photoUrl = profile.profile_photo_url
    ? `${getApiBase()}${profile.profile_photo_url}`
    : null;

  return (
    <div className="min-h-screen bg-base text-text flex flex-col">
      <Header />
      <main className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
        <div className="flex items-center gap-2 mb-6">
          <div className="p-2 rounded-lg bg-primary/10">
            <Wrench size={24} className="text-primary" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">Mechanic dashboard</h1>
            <p className="text-sm text-subtext">Manage your profile and jobs.</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg p-4 border border-surface1 bg-surface0">
            <div className="flex items-start gap-4">
              <div className="relative">
                {photoUrl ? (
                  <img
                    src={photoUrl}
                    alt="Profile"
                    className="w-16 h-16 rounded-full object-cover border border-surface1"
                  />
                ) : (
                  <div className="w-16 h-16 rounded-full bg-surface1 flex items-center justify-center">
                    <Wrench size={24} className="text-overlay0" />
                  </div>
                )}
                <label className="absolute bottom-0 right-0 p-1 rounded-full bg-primary cursor-pointer">
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) photoMutation.mutate(f);
                    }}
                    disabled={photoMutation.isPending}
                  />
                  <Camera size={14} className="text-base" />
                </label>
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="font-semibold text-text">{profile.name}</h2>
                {profile.rating != null && profile.rating > 0 && (
                  <p className="text-sm text-subtext">★ {profile.rating.toFixed(1)}</p>
                )}
                {profile.service_radius_mi != null && (
                  <p className="text-xs text-overlay0 flex items-center gap-1">
                    <MapPin size={12} /> {profile.service_radius_mi} mi radius
                  </p>
                )}
                {profile.hourly_rate_cents != null && (
                  <p className="text-xs text-overlay0">
                    ${(profile.hourly_rate_cents / 100).toFixed(2)}/hr
                  </p>
                )}
              </div>
            </div>
            {profile.bio && <p className="mt-3 text-sm text-subtext">{profile.bio}</p>}
            {profile.skills && (
              <p className="mt-1 text-xs text-overlay0">Skills: {profile.skills}</p>
            )}
          </div>

          <div className="flex gap-2">
            <Link to="/mechanic/edit">
              <Button variant="secondary" size="sm">
                <Edit2 size={14} />
                Edit profile
              </Button>
            </Link>
            <Link to="/find-mechanic">
              <Button variant="secondary" size="sm">
                Find mechanic (customer view)
              </Button>
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
