import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Truck, MapPin, Loader2, Wrench } from "lucide-react";
import { StarRating } from "@/components/ui/StarRating";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/Button";
import { dispatchRunDirect, dispatchContinue, geocodeAddress } from "@/lib/api";
import type { DispatchResponse, DispatchMechanic } from "@/types";

const REPAIR_SUGGESTIONS = [
  "Brake pad replacement",
  "Oil change",
  "Battery replacement",
  "Spark plug replacement",
  "Serpentine belt replacement",
  "Wheel bearing",
  "Alternator",
  "Fuel pump",
  "Motor mount",
  "Transmission fluid change",
  "Power steering pump",
  "A/C compressor",
  "Timing belt",
  "Water pump",
  "Ignition coil",
  "CV axle",
  "Exhaust repair",
  "Suspension bushing",
  "Belt tensioner",
  "Idler pulley",
  "Heat shield",
  "Transmission gears",
  "Differential gears",
  "Drive shaft support bearing",
];

function getGeolocationError(e: unknown): string {
  const err = e as { code?: number; message?: string };
  if (err.code === 1) return "Location permission denied";
  if (err.code === 2) return "Location unavailable";
  if (err.code === 3) return "Location request timed out";
  return err.message || "Location unavailable";
}

export function FindMechanicView() {
  const navigate = useNavigate();
  const [partInfo, setPartInfo] = useState("");
  const [addressInput, setAddressInput] = useState("");
  const [userLatitude, setUserLatitude] = useState<number | null>(null);
  const [userLongitude, setUserLongitude] = useState<number | null>(null);
  const [locationLoading, setLocationLoading] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dispatchResponse, setDispatchResponse] = useState<DispatchResponse | null>(null);
  const [selectedMechanicId, setSelectedMechanicId] = useState<number | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredSuggestions = partInfo.length >= 1
    ? REPAIR_SUGGESTIONS.filter((s) =>
        s.toLowerCase().includes(partInfo.toLowerCase())
      ).slice(0, 8)
    : [];

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleFindMechanics = async () => {
    if (!partInfo.trim()) {
      setError("Describe what needs to be done");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await dispatchRunDirect({
        part_info: partInfo.trim(),
        user_latitude: userLatitude ?? undefined,
        user_longitude: userLongitude ?? undefined,
        user_address: addressInput.trim() || undefined,
      });
      setDispatchResponse(res);
      if (res.mechanic_list && res.mechanic_list.length > 0) {
        setSelectedMechanicId(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to find mechanics");
    } finally {
      setLoading(false);
    }
  };

  const handleLocationThenContinue = async (lat: number, lng: number) => {
    if (!dispatchResponse?.thread_id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await dispatchContinue({
        thread_id: dispatchResponse.thread_id,
        action: "get_parts",
        user_latitude: lat,
        user_longitude: lng,
      });
      setDispatchResponse(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to find mechanics");
    } finally {
      setLoading(false);
    }
  };

  const handleSendToMechanic = async () => {
    if (!dispatchResponse?.thread_id || selectedMechanicId === null) return;
    setLoading(true);
    setError(null);
    try {
      const res = await dispatchContinue({
        thread_id: dispatchResponse.thread_id,
        action: "mechanic_selected",
        selected_mechanic_id: selectedMechanicId,
        user_latitude: userLatitude ?? undefined,
        user_longitude: userLongitude ?? undefined,
        user_address: addressInput.trim() || undefined,
      });
      setDispatchResponse(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send job");
    } finally {
      setLoading(false);
    }
  };

  const needsLocationToFind =
    dispatchResponse?.current_step === "awaiting_find_mechanics" &&
    userLatitude == null &&
    userLongitude == null;

  const showMechanicList =
    dispatchResponse?.mechanic_list &&
    dispatchResponse.mechanic_list.length > 0 &&
    dispatchResponse.current_step === "awaiting_mechanic_selection";

  const showWaiting =
    dispatchResponse?.current_step === "awaiting_mechanic_response" ||
    dispatchResponse?.current_step === "dispatched";

  const showNoMechanic = dispatchResponse?.current_step === "no_mechanic_accepted";

  return (
    <div className="min-h-screen bg-base text-text flex flex-col">
      <Header />
      <main className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
        <div className="flex items-center gap-2 mb-6">
          <div className="p-2 rounded-lg bg-primary/10">
            <Truck size={24} className="text-primary" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">Find a mechanic</h1>
            <p className="text-sm text-subtext">
              Already know what&apos;s wrong? Skip diagnosis and connect with a mechanic.
            </p>
          </div>
        </div>

        {!dispatchResponse ? (
          <div className="space-y-4">
            <div className="relative">
              <label className="block text-sm font-medium text-text mb-1.5">
                What needs to be done?
              </label>
              <input
                ref={inputRef}
                type="text"
                placeholder="e.g. brake pad replacement, oil change"
                value={partInfo}
                onChange={(e) => {
                  setPartInfo(e.target.value);
                  setShowSuggestions(true);
                }}
                onFocus={() => setShowSuggestions(true)}
                className="w-full px-3 py-2.5 rounded-lg bg-mantle border border-surface1 text-text placeholder:text-overlay1 focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
              {showSuggestions && filteredSuggestions.length > 0 && (
                <div
                  ref={suggestionsRef}
                  className="absolute z-10 w-full mt-1 py-1 rounded-lg bg-mantle border border-surface1 shadow-lg max-h-48 overflow-y-auto"
                >
                  {filteredSuggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className="w-full text-left px-3 py-2 text-sm text-text hover:bg-surface0"
                      onClick={() => {
                        setPartInfo(s);
                        setShowSuggestions(false);
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div>
              <p className="text-xs font-medium text-text mb-1.5">
                Your location (optional — helps find nearby mechanics)
              </p>
              <div className="flex gap-2 mb-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={locationLoading}
                  onClick={async () => {
                    if (!navigator.geolocation) {
                      setLocationError("Geolocation not supported (try HTTPS or enter address)");
                      return;
                    }
                    setLocationLoading(true);
                    setLocationError(null);
                    try {
                      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(resolve, reject, {
                          enableHighAccuracy: true,
                          timeout: 10000,
                        });
                      });
                      setUserLatitude(pos.coords.latitude);
                      setUserLongitude(pos.coords.longitude);
                    } catch (e) {
                      setLocationError(getGeolocationError(e));
                    } finally {
                      setLocationLoading(false);
                    }
                  }}
                >
                  {locationLoading ? <Loader2 size={14} className="animate-spin" /> : <MapPin size={14} />}
                  {locationLoading ? "Getting…" : "Use my location"}
                </Button>
                <div className="flex-1 flex gap-1">
                  <input
                    type="text"
                    placeholder="Or enter address"
                    value={addressInput}
                    onChange={(e) => setAddressInput(e.target.value)}
                    className="flex-1 min-w-0 px-2 py-1.5 rounded-md text-sm bg-mantle border border-surface1 text-text placeholder:text-overlay1"
                  />
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={locationLoading || !addressInput.trim()}
                    onClick={async () => {
                      if (!addressInput.trim()) return;
                      setLocationLoading(true);
                      setLocationError(null);
                      try {
                        const res = await geocodeAddress(addressInput.trim());
                        setUserLatitude(res.latitude);
                        setUserLongitude(res.longitude);
                      } catch (e) {
                        setLocationError(e instanceof Error ? e.message : "Address not found");
                      } finally {
                        setLocationLoading(false);
                      }
                    }}
                  >
                    {locationLoading ? <Loader2 size={14} className="animate-spin" /> : "Find"}
                  </Button>
                </div>
              </div>
              {(userLatitude != null && userLongitude != null) && (
                <p className="text-xs text-green">
                  Location set: {userLatitude.toFixed(4)}, {userLongitude.toFixed(4)}
                </p>
              )}
              {locationError && <p className="text-xs text-red">{locationError}</p>}
            </div>
            {error && <p className="text-sm text-red">{error}</p>}
            <Button
              size="lg"
              variant="primary"
              className="w-full"
              disabled={loading}
              onClick={handleFindMechanics}
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Wrench size={18} />}
              {loading ? "Finding mechanics…" : "Find mechanic"}
            </Button>
          </div>
        ) : needsLocationToFind ? (
          <div className="space-y-4">
            <p className="text-sm text-subtext">{dispatchResponse.prompt_for_user}</p>
            <div>
              <p className="text-xs font-medium text-text mb-1.5">Share your location</p>
              <div className="flex gap-2 mb-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={locationLoading || loading}
                  onClick={async () => {
                    if (!navigator.geolocation) {
                      setLocationError("Geolocation not supported (try HTTPS or enter address)");
                      return;
                    }
                    setLocationLoading(true);
                    setLocationError(null);
                    try {
                      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(resolve, reject, {
                          enableHighAccuracy: true,
                          timeout: 10000,
                        });
                      });
                      setUserLatitude(pos.coords.latitude);
                      setUserLongitude(pos.coords.longitude);
                      await handleLocationThenContinue(pos.coords.latitude, pos.coords.longitude);
                    } catch (e) {
                      setLocationError(getGeolocationError(e));
                    } finally {
                      setLocationLoading(false);
                    }
                  }}
                >
                  {locationLoading ? <Loader2 size={14} className="animate-spin" /> : <MapPin size={14} />}
                  Use my location
                </Button>
                <div className="flex-1 flex gap-1">
                  <input
                    type="text"
                    placeholder="Or enter address"
                    value={addressInput}
                    onChange={(e) => setAddressInput(e.target.value)}
                    className="flex-1 min-w-0 px-2 py-1.5 rounded-md text-sm bg-mantle border border-surface1 text-text placeholder:text-overlay1"
                  />
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={locationLoading || loading || !addressInput.trim()}
                    onClick={async () => {
                      if (!addressInput.trim()) return;
                      setLocationLoading(true);
                      setLocationError(null);
                      try {
                        const res = await geocodeAddress(addressInput.trim());
                        setUserLatitude(res.latitude);
                        setUserLongitude(res.longitude);
                        await handleLocationThenContinue(res.latitude, res.longitude);
                      } catch (e) {
                        setLocationError(e instanceof Error ? e.message : "Address not found");
                      } finally {
                        setLocationLoading(false);
                      }
                    }}
                  >
                    {locationLoading ? <Loader2 size={14} className="animate-spin" /> : "Find"}
                  </Button>
                </div>
              </div>
              {locationError && <p className="text-xs text-red">{locationError}</p>}
              {error && <p className="text-xs text-red">{error}</p>}
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={async () => {
                if (!dispatchResponse.thread_id) return;
                setLoading(true);
                setError(null);
                try {
                  const res = await dispatchContinue({
                    thread_id: dispatchResponse.thread_id,
                    action: "get_parts",
                  });
                  setDispatchResponse(res);
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Failed");
                } finally {
                  setLoading(false);
                }
              }}
              disabled={loading}
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : "Show all mechanics"}
            </Button>
          </div>
        ) : showMechanicList ? (
          <div className="space-y-4">
            <p className="text-sm text-subtext">{dispatchResponse.prompt_for_user}</p>
            <ul className="space-y-2">
              {(dispatchResponse.mechanic_list as DispatchMechanic[]).map((m) => (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedMechanicId(m.id)}
                    className={`w-full text-left px-4 py-3 rounded-lg border flex items-center justify-between transition-colors ${
                      selectedMechanicId === m.id
                        ? "bg-primary/20 border-primary"
                        : "bg-mantle border-surface1 hover:border-surface2"
                    }`}
                  >
                    <div className="flex flex-col items-start">
                      <span className="font-medium">{m.name}</span>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-overlay0">{m.distance_mi} mi away</span>
                        {"rating" in m && m.rating != null && Number(m.rating) > 0 && (
                          <StarRating rating={Number(m.rating)} size={12} />
                        )}
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
            {error && <p className="text-sm text-red">{error}</p>}
            <Button
              size="lg"
              variant="primary"
              className="w-full"
              disabled={loading || selectedMechanicId === null}
              onClick={handleSendToMechanic}
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Truck size={18} />}
              {loading ? "Sending…" : "Send job to mechanic"}
            </Button>
          </div>
        ) : showWaiting ? (
          <div className="rounded-lg p-4 border border-surface1 bg-surface0">
            <p className="text-sm text-subtext">{dispatchResponse.prompt_for_user}</p>
            {dispatchResponse.current_step === "dispatched" && dispatchResponse.job_id && (
              <div className="mt-3 flex gap-2">
                <Button size="sm" variant="primary" onClick={() => navigate(`/tracking/${dispatchResponse.job_id}`)}>
                  <MapPin size={14} />
                  Track mechanic
                </Button>
                <Button size="sm" variant="secondary" onClick={() => navigate("/")}>
                  Back to home
                </Button>
              </div>
            )}
          </div>
        ) : showNoMechanic ? (
          <div className="space-y-3">
            <p className="text-sm text-subtext">{dispatchResponse.prompt_for_user}</p>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setDispatchResponse(null);
                setSelectedMechanicId(null);
              }}
            >
              Try again
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-subtext">{dispatchResponse.prompt_for_user}</p>
            <Button size="sm" variant="secondary" onClick={() => setDispatchResponse(null)}>
              Start over
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}
