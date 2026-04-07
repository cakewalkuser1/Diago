import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Truck, MapPin, Loader2, Wrench, ChevronRight, Star, Check, X } from "lucide-react";
import { useJsApiLoader, Autocomplete } from "@react-google-maps/api";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/Button";
import { dispatchRunDirect, dispatchContinue, geocodeAddress } from "@/lib/api";
import type { DispatchResponse, DispatchMechanic } from "@/types";

const GOOGLE_MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY as string | undefined;
const LIBRARIES: ("places" | "geometry")[] = ["places"];

const REPAIR_SUGGESTIONS = [
  "Brake pad replacement", "Oil change", "Battery replacement", "Spark plug replacement",
  "Serpentine belt replacement", "Wheel bearing", "Alternator", "Fuel pump",
  "Motor mount", "Transmission fluid change", "Power steering pump", "A/C compressor",
  "Timing belt", "Water pump", "Ignition coil", "CV axle", "Exhaust repair",
  "Suspension bushing", "Belt tensioner", "Idler pulley", "Heat shield",
  "Transmission gears", "Differential gears", "Drive shaft support bearing",
];

function getGeolocationError(e: unknown): string {
  const err = e as { code?: number; message?: string };
  if (err.code === 1) return "Location permission denied";
  if (err.code === 2) return "Location unavailable";
  if (err.code === 3) return "Location request timed out";
  return err.message || "Location unavailable";
}

// ─── Step indicator ───────────────────────────────────────────────────────────

const STEPS = ["Service", "Location", "Mechanic"];

function StepBar({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-0 mb-6">
      {STEPS.map((label, i) => (
        <div key={label} className="flex items-center flex-1 last:flex-none">
          <div className="flex flex-col items-center gap-1">
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-colors ${
                i < current
                  ? "bg-green-500 text-white"
                  : i === current
                  ? "bg-primary text-white"
                  : "bg-surface1 text-overlay1"
              }`}
            >
              {i < current ? <Check size={14} /> : i + 1}
            </div>
            <span className={`text-[10px] font-medium ${i === current ? "text-text" : "text-overlay1"}`}>
              {label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={`flex-1 h-px mx-1 mb-4 transition-colors ${i < current ? "bg-green-500" : "bg-surface1"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Mechanic card ────────────────────────────────────────────────────────────

function MechanicCard({
  mechanic,
  selected,
  onSelect,
}: {
  mechanic: DispatchMechanic;
  selected: boolean;
  onSelect: () => void;
}) {
  const initials = mechanic.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full text-left rounded-2xl border p-4 flex items-center gap-4 transition-all ${
        selected
          ? "bg-primary/10 border-primary ring-1 ring-primary"
          : "bg-surface0 border-surface1 hover:border-surface2 active:scale-[0.99]"
      }`}
    >
      {/* Avatar */}
      <div className={`w-12 h-12 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 ${
        selected ? "bg-primary text-white" : "bg-surface1 text-text"
      }`}>
        {initials}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm truncate">{mechanic.name}</p>
        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
          {mechanic.distance_mi != null && (
            <span className="text-xs text-overlay0 flex items-center gap-0.5">
              <MapPin size={10} /> {mechanic.distance_mi} mi away
            </span>
          )}
          {"rating" in mechanic && mechanic.rating != null && Number(mechanic.rating) > 0 && (
            <span className="text-xs text-yellow-400 flex items-center gap-0.5">
              <Star size={10} fill="currentColor" /> {Number(mechanic.rating).toFixed(1)}
            </span>
          )}
          {"hourly_rate" in mechanic && mechanic.hourly_rate != null && (
            <span className="text-xs text-overlay1">${mechanic.hourly_rate}/hr</span>
          )}
        </div>
      </div>

      {selected ? (
        <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
          <Check size={14} className="text-white" />
        </div>
      ) : (
        <ChevronRight size={16} className="text-overlay1 flex-shrink-0" />
      )}
    </button>
  );
}

// ─── Address input (with Places Autocomplete if key available) ────────────────

function AddressInput({
  value,
  onChange,
  onPlaceSelected,
  onUseLocation,
  locationLoading,
  locationSet,
  locationError,
}: {
  value: string;
  onChange: (v: string) => void;
  onPlaceSelected: (lat: number, lng: number, address: string) => void;
  onUseLocation: () => void;
  locationLoading: boolean;
  locationSet: boolean;
  locationError: string | null;
}) {
  const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null);

  const onLoad = useCallback((ac: google.maps.places.Autocomplete) => {
    autocompleteRef.current = ac;
  }, []);

  const onPlaceChanged = useCallback(() => {
    const place = autocompleteRef.current?.getPlace();
    if (place?.geometry?.location) {
      onPlaceSelected(
        place.geometry.location.lat(),
        place.geometry.location.lng(),
        place.formatted_address || value
      );
    }
  }, [onPlaceSelected, value]);

  const inputClass = `w-full px-4 py-3 rounded-xl bg-surface0 border ${
    locationSet ? "border-green-500" : "border-surface1"
  } text-text placeholder:text-overlay1 focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm`;

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={onUseLocation}
        disabled={locationLoading}
        className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-primary/10 border border-primary/30 hover:bg-primary/15 active:scale-[0.99] transition-all"
      >
        {locationLoading ? (
          <Loader2 size={18} className="animate-spin text-primary flex-shrink-0" />
        ) : (
          <MapPin size={18} className="text-primary flex-shrink-0" />
        )}
        <span className="text-sm font-medium text-primary">
          {locationLoading ? "Getting your location…" : locationSet ? "Location detected" : "Use my current location"}
        </span>
        {locationSet && <Check size={16} className="text-green-400 ml-auto" />}
      </button>

      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-surface1" />
        <span className="text-xs text-overlay1">or enter address</span>
        <div className="flex-1 h-px bg-surface1" />
      </div>

      {GOOGLE_MAPS_KEY ? (
        <Autocomplete onLoad={onLoad} onPlaceChanged={onPlaceChanged}>
          <input
            type="text"
            placeholder="Street address, city…"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className={inputClass}
          />
        </Autocomplete>
      ) : (
        <input
          type="text"
          placeholder="Street address, city…"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
        />
      )}

      {locationError && (
        <p className="text-xs text-red flex items-center gap-1">
          <X size={12} /> {locationError}
        </p>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

function FindMechanicContent() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0); // 0=service, 1=location, 2=mechanic
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
    ? REPAIR_SUGGESTIONS.filter((s) => s.toLowerCase().includes(partInfo.toLowerCase())).slice(0, 6)
    : [];

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        suggestionsRef.current && !suggestionsRef.current.contains(e.target as Node) &&
        inputRef.current && !inputRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleUseLocation = async () => {
    if (!navigator.geolocation) {
      setLocationError("Geolocation not supported — enter address instead");
      return;
    }
    setLocationLoading(true);
    setLocationError(null);
    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 });
      });
      setUserLatitude(pos.coords.latitude);
      setUserLongitude(pos.coords.longitude);
    } catch (e) {
      setLocationError(getGeolocationError(e));
    } finally {
      setLocationLoading(false);
    }
  };

  const handlePlaceSelected = (lat: number, lng: number, address: string) => {
    setUserLatitude(lat);
    setUserLongitude(lng);
    setAddressInput(address);
  };

  const handleAddressGeocode = async () => {
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
  };

  const handleFindMechanics = async () => {
    setLoading(true);
    setError(null);

    // If address typed but not geocoded yet, geocode first
    let lat = userLatitude;
    let lng = userLongitude;
    if ((lat == null || lng == null) && addressInput.trim() && !GOOGLE_MAPS_KEY) {
      try {
        const res = await geocodeAddress(addressInput.trim());
        lat = res.latitude;
        lng = res.longitude;
        setUserLatitude(lat);
        setUserLongitude(lng);
      } catch {
        // proceed without location
      }
    }

    try {
      const res = await dispatchRunDirect({
        part_info: partInfo.trim(),
        user_latitude: lat ?? undefined,
        user_longitude: lng ?? undefined,
        user_address: addressInput.trim() || undefined,
      });
      setDispatchResponse(res);
      setSelectedMechanicId(null);
      if (res.mechanic_list && res.mechanic_list.length > 0) {
        setStep(2);
      }
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

  const locationSet = userLatitude != null && userLongitude != null;
  const showWaiting =
    dispatchResponse?.current_step === "awaiting_mechanic_response" ||
    dispatchResponse?.current_step === "dispatched";
  const showNoMechanic = dispatchResponse?.current_step === "no_mechanic_accepted";

  // ── Dispatched / Waiting ──────────────────────────────────────────────────
  if (showWaiting || showNoMechanic) {
    const dispatched = dispatchResponse?.current_step === "dispatched";
    return (
      <div className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
        <div className="rounded-2xl border border-surface1 bg-surface0 p-6 text-center space-y-4">
          <div className={`w-16 h-16 rounded-full mx-auto flex items-center justify-center ${
            dispatched ? "bg-green-500/10" : showNoMechanic ? "bg-red/10" : "bg-primary/10"
          }`}>
            {dispatched ? (
              <Check size={28} className="text-green-400" />
            ) : showNoMechanic ? (
              <X size={28} className="text-red" />
            ) : (
              <Loader2 size={28} className="animate-spin text-primary" />
            )}
          </div>
          <div>
            <p className="font-semibold text-base">{
              dispatched ? "Mechanic on the way!" :
              showNoMechanic ? "No mechanic available" :
              "Waiting for mechanic…"
            }</p>
            <p className="text-sm text-subtext mt-1">{dispatchResponse?.prompt_for_user}</p>
          </div>
          <div className="flex gap-2 justify-center flex-wrap">
            {dispatched && dispatchResponse?.job_id && (
              <Button size="sm" variant="primary" onClick={() => navigate(`/tracking/${dispatchResponse.job_id}`)}>
                <MapPin size={14} /> Track mechanic
              </Button>
            )}
            {(showNoMechanic || dispatched) && (
              <Button size="sm" variant="secondary" onClick={() => navigate("/")}>
                Back to home
              </Button>
            )}
          </div>
          {showNoMechanic && (
            <button
              type="button"
              className="text-xs text-overlay1 underline"
              onClick={() => { setDispatchResponse(null); setStep(0); setSelectedMechanicId(null); }}
            >
              Try again
            </button>
          )}
        </div>
      </div>
    );
  }

  // ── Step 0: Service type ──────────────────────────────────────────────────
  if (step === 0) {
    return (
      <div className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
        <StepBar current={0} />
        <h2 className="text-lg font-semibold mb-1">What needs fixing?</h2>
        <p className="text-sm text-subtext mb-4">Describe the repair or service needed.</p>

        <div className="relative mb-4">
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-surface0 border border-surface1 focus-within:ring-2 focus-within:ring-primary/50">
            <Wrench size={18} className="text-overlay1 flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              placeholder="e.g. brake pad replacement, oil change"
              value={partInfo}
              onChange={(e) => { setPartInfo(e.target.value); setShowSuggestions(true); }}
              onFocus={() => setShowSuggestions(true)}
              className="flex-1 bg-transparent text-text placeholder:text-overlay1 focus:outline-none text-sm"
            />
            {partInfo && (
              <button type="button" onClick={() => setPartInfo("")} className="text-overlay1 hover:text-text">
                <X size={14} />
              </button>
            )}
          </div>
          {showSuggestions && filteredSuggestions.length > 0 && (
            <div
              ref={suggestionsRef}
              className="absolute z-10 w-full mt-1 py-1 rounded-xl bg-mantle border border-surface1 shadow-xl max-h-52 overflow-y-auto"
            >
              {filteredSuggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="w-full text-left px-4 py-2.5 text-sm text-text hover:bg-surface0 flex items-center gap-2"
                  onClick={() => { setPartInfo(s); setShowSuggestions(false); }}
                >
                  <Wrench size={12} className="text-overlay1" /> {s}
                </button>
              ))}
            </div>
          )}
        </div>

        {error && <p className="text-sm text-red mb-3">{error}</p>}

        <Button
          size="lg"
          variant="primary"
          className="w-full"
          disabled={!partInfo.trim()}
          onClick={() => { setError(null); setStep(1); }}
        >
          Continue <ChevronRight size={18} />
        </Button>
      </div>
    );
  }

  // ── Step 1: Location ──────────────────────────────────────────────────────
  if (step === 1) {
    return (
      <div className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
        <StepBar current={1} />
        <h2 className="text-lg font-semibold mb-1">Where are you?</h2>
        <p className="text-sm text-subtext mb-4">We'll find mechanics near you.</p>

        <AddressInput
          value={addressInput}
          onChange={setAddressInput}
          onPlaceSelected={handlePlaceSelected}
          onUseLocation={handleUseLocation}
          locationLoading={locationLoading}
          locationSet={locationSet}
          locationError={locationError}
        />

        {!GOOGLE_MAPS_KEY && addressInput.trim() && !locationSet && (
          <Button
            size="sm"
            variant="secondary"
            className="mt-2 w-full"
            disabled={locationLoading}
            onClick={handleAddressGeocode}
          >
            {locationLoading ? <Loader2 size={14} className="animate-spin" /> : <MapPin size={14} />}
            Find this address
          </Button>
        )}

        {error && <p className="text-sm text-red mt-3">{error}</p>}

        <div className="flex gap-3 mt-5">
          <Button size="lg" variant="secondary" className="flex-1" onClick={() => setStep(0)}>
            Back
          </Button>
          <Button
            size="lg"
            variant="primary"
            className="flex-1"
            disabled={loading}
            onClick={handleFindMechanics}
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : <Wrench size={18} />}
            {loading ? "Finding…" : locationSet ? "Find mechanics" : "Skip & find all"}
          </Button>
        </div>
      </div>
    );
  }

  // ── Step 2: Mechanic selection ────────────────────────────────────────────
  const mechanics = (dispatchResponse?.mechanic_list ?? []) as DispatchMechanic[];

  return (
    <div className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
      <StepBar current={2} />
      <h2 className="text-lg font-semibold mb-1">Choose a mechanic</h2>
      <p className="text-sm text-subtext mb-4">
        {partInfo} · {locationSet ? `${(userLatitude!).toFixed(2)}, ${(userLongitude!).toFixed(2)}` : "any area"}
      </p>

      {mechanics.length === 0 ? (
        <div className="text-center py-10 text-subtext text-sm">
          No mechanics available right now.
          <button
            type="button"
            className="block mx-auto mt-3 text-primary underline text-xs"
            onClick={() => { setDispatchResponse(null); setStep(0); }}
          >
            Start over
          </button>
        </div>
      ) : (
        <ul className="space-y-3 mb-5">
          {mechanics.map((m) => (
            <li key={m.id}>
              <MechanicCard
                mechanic={m}
                selected={selectedMechanicId === m.id}
                onSelect={() => setSelectedMechanicId(m.id)}
              />
            </li>
          ))}
        </ul>
      )}

      {error && <p className="text-sm text-red mb-3">{error}</p>}

      <div className="flex gap-3">
        <Button size="lg" variant="secondary" className="flex-1" onClick={() => setStep(1)}>
          Back
        </Button>
        <Button
          size="lg"
          variant="primary"
          className="flex-1"
          disabled={loading || selectedMechanicId === null}
          onClick={handleSendToMechanic}
        >
          {loading ? <Loader2 size={18} className="animate-spin" /> : <Truck size={18} />}
          {loading ? "Sending…" : "Book mechanic"}
        </Button>
      </div>
    </div>
  );
}

// ─── Wrapper: loads Google Maps SDK if key is set ─────────────────────────────

function FindMechanicWithGoogleMaps() {
  useJsApiLoader({ googleMapsApiKey: GOOGLE_MAPS_KEY!, libraries: LIBRARIES });
  return <FindMechanicContent />;
}

export function FindMechanicView() {
  return (
    <div className="min-h-screen bg-base text-text flex flex-col">
      <Header />
      {GOOGLE_MAPS_KEY ? <FindMechanicWithGoogleMaps /> : <FindMechanicContent />}
    </div>
  );
}
