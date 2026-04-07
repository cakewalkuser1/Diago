import { useEffect, useRef, useCallback } from "react";
import { GoogleMap, useJsApiLoader, Marker } from "@react-google-maps/api";
import { MapContainer, TileLayer, Marker as LeafletMarker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix default Leaflet marker icons in Vite
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

const GOOGLE_MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY as string | undefined;
const LIBRARIES: ("places" | "geometry")[] = ["places"];

// ─── Leaflet fallback ────────────────────────────────────────────────────────

function LeafletFitBounds({ userLat, userLng, mechanicLat, mechanicLng }: {
  userLat: number | null; userLng: number | null;
  mechanicLat: number | null; mechanicLng: number | null;
}) {
  const map = useMap();
  useEffect(() => {
    const points: [number, number][] = [];
    if (userLat != null && userLng != null) points.push([userLat, userLng]);
    if (mechanicLat != null && mechanicLng != null) points.push([mechanicLat, mechanicLng]);
    if (points.length >= 2) {
      map.fitBounds(points, { padding: [40, 40] });
    } else if (points.length === 1) {
      map.setView(points[0], 14);
    }
  }, [map, userLat, userLng, mechanicLat, mechanicLng]);
  return null;
}

function LeafletMap({ userLat, userLng, mechanicLat, mechanicLng, mechanicName, height }: {
  userLat: number | null; userLng: number | null;
  mechanicLat: number | null; mechanicLng: number | null;
  mechanicName?: string | null; height: number;
}) {
  const centerLat = userLat ?? mechanicLat ?? 34.05;
  const centerLng = userLng ?? mechanicLng ?? -118.25;
  return (
    <MapContainer
      center={[centerLat, centerLng]}
      zoom={12}
      className="w-full h-full"
      style={{ height }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <LeafletFitBounds userLat={userLat} userLng={userLng} mechanicLat={mechanicLat} mechanicLng={mechanicLng} />
      {userLat != null && userLng != null && (
        <LeafletMarker position={[userLat, userLng]}>
          <Popup>Your location</Popup>
        </LeafletMarker>
      )}
      {mechanicLat != null && mechanicLng != null && (
        <LeafletMarker position={[mechanicLat, mechanicLng]}>
          <Popup>{mechanicName || "Mechanic"}</Popup>
        </LeafletMarker>
      )}
    </MapContainer>
  );
}

// ─── Google Maps ─────────────────────────────────────────────────────────────

// Custom SVG markers
const USER_ICON: google.maps.Symbol = {
  path: google.maps?.SymbolPath?.CIRCLE ?? 0,
  scale: 10,
  fillColor: "#3b82f6",
  fillOpacity: 1,
  strokeColor: "#ffffff",
  strokeWeight: 2,
};

const MECHANIC_ICON: google.maps.Symbol = {
  path: google.maps?.SymbolPath?.FORWARD_CLOSED_ARROW ?? 1,
  scale: 6,
  fillColor: "#ff5638",
  fillOpacity: 1,
  strokeColor: "#ffffff",
  strokeWeight: 2,
};

function GoogleMapComponent({ userLat, userLng, mechanicLat, mechanicLng, mechanicName, height }: {
  userLat: number | null; userLng: number | null;
  mechanicLat: number | null; mechanicLng: number | null;
  mechanicName?: string | null; height: number;
}) {
  const mapRef = useRef<google.maps.Map | null>(null);

  const onLoad = useCallback((map: google.maps.Map) => {
    mapRef.current = map;
  }, []);

  // Fit bounds whenever locations change
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const bounds = new window.google.maps.LatLngBounds();
    let count = 0;
    if (userLat != null && userLng != null) { bounds.extend({ lat: userLat, lng: userLng }); count++; }
    if (mechanicLat != null && mechanicLng != null) { bounds.extend({ lat: mechanicLat, lng: mechanicLng }); count++; }
    if (count >= 2) {
      map.fitBounds(bounds, 60);
    } else if (count === 1) {
      map.setCenter(bounds.getCenter());
      map.setZoom(14);
    }
  }, [userLat, userLng, mechanicLat, mechanicLng]);

  const center = {
    lat: userLat ?? mechanicLat ?? 34.05,
    lng: userLng ?? mechanicLng ?? -118.25,
  };

  return (
    <GoogleMap
      mapContainerStyle={{ width: "100%", height }}
      center={center}
      zoom={12}
      onLoad={onLoad}
      options={{
        disableDefaultUI: true,
        zoomControl: true,
        styles: [
          { elementType: "geometry", stylers: [{ color: "#1a1a1a" }] },
          { elementType: "labels.text.fill", stylers: [{ color: "#f0f0f0" }] },
          { elementType: "labels.text.stroke", stylers: [{ color: "#1a1a1a" }] },
          { featureType: "road", elementType: "geometry", stylers: [{ color: "#252525" }] },
          { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#ff5638" }] },
          { featureType: "water", elementType: "geometry", stylers: [{ color: "#0e0e0e" }] },
          { featureType: "poi", stylers: [{ visibility: "off" }] },
          { featureType: "transit", stylers: [{ visibility: "off" }] },
        ],
      }}
    >
      {userLat != null && userLng != null && (
        <Marker
          position={{ lat: userLat, lng: userLng }}
          icon={USER_ICON}
          title="Your location"
        />
      )}
      {mechanicLat != null && mechanicLng != null && (
        <Marker
          position={{ lat: mechanicLat, lng: mechanicLng }}
          icon={MECHANIC_ICON}
          title={mechanicName || "Mechanic"}
        />
      )}
    </GoogleMap>
  );
}

function GoogleMapLoader(props: {
  userLat: number | null; userLng: number | null;
  mechanicLat: number | null; mechanicLng: number | null;
  mechanicName?: string | null; height: number;
}) {
  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: GOOGLE_MAPS_KEY!,
    libraries: LIBRARIES,
  });

  if (loadError) {
    return (
      <LeafletMap {...props} />
    );
  }

  if (!isLoaded) {
    return (
      <div className="flex items-center justify-center h-full bg-surface0 text-overlay1 text-sm">
        Loading map…
      </div>
    );
  }

  return <GoogleMapComponent {...props} />;
}

// ─── Public component ─────────────────────────────────────────────────────────

export function LiveTrackingMap({
  userLat,
  userLng,
  mechanicLat,
  mechanicLng,
  mechanicName,
  className = "",
  height = 280,
}: {
  userLat: number | null;
  userLng: number | null;
  mechanicLat: number | null;
  mechanicLng: number | null;
  mechanicName?: string | null;
  className?: string;
  height?: number;
}) {
  return (
    <div
      className={`rounded-xl overflow-hidden border border-surface1 ${className}`}
      style={{ minHeight: height }}
    >
      {GOOGLE_MAPS_KEY ? (
        <GoogleMapLoader
          userLat={userLat}
          userLng={userLng}
          mechanicLat={mechanicLat}
          mechanicLng={mechanicLng}
          mechanicName={mechanicName}
          height={height}
        />
      ) : (
        <LeafletMap
          userLat={userLat}
          userLng={userLng}
          mechanicLat={mechanicLat}
          mechanicLng={mechanicLng}
          mechanicName={mechanicName}
          height={height}
        />
      )}
    </div>
  );
}
