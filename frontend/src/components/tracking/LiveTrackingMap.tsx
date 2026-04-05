import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix default marker icons in react-leaflet (webpack/vite)
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

function FitBounds({ userLat, userLng, mechanicLat, mechanicLng }: {
  userLat: number | null;
  userLng: number | null;
  mechanicLat: number | null;
  mechanicLng: number | null;
}) {
  const map = useMap();
  useEffect(() => {
    const points: [number, number][] = [];
    if (userLat != null && userLng != null) points.push([userLat, userLng]);
    if (mechanicLat != null && mechanicLng != null) points.push([mechanicLat, mechanicLng]);
    if (points.length >= 2) {
      map.fitBounds(points as [number, number][], { padding: [40, 40] });
    } else if (points.length === 1) {
      map.setView(points[0], 14);
    }
  }, [map, userLat, userLng, mechanicLat, mechanicLng]);
  return null;
}

export function LiveTrackingMap({
  userLat,
  userLng,
  mechanicLat,
  mechanicLng,
  mechanicName,
  className = "",
}: {
  userLat: number | null;
  userLng: number | null;
  mechanicLat: number | null;
  mechanicLng: number | null;
  mechanicName?: string | null;
  className?: string;
}) {
  const centerLat = userLat ?? mechanicLat ?? 34.05;
  const centerLng = userLng ?? mechanicLng ?? -118.25;

  return (
    <div className={`rounded-lg overflow-hidden border border-surface1 ${className}`} style={{ minHeight: 280 }}>
      <MapContainer
        center={[centerLat, centerLng]}
        zoom={12}
        className="w-full h-full"
        style={{ height: 280 }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds
          userLat={userLat}
          userLng={userLng}
          mechanicLat={mechanicLat}
          mechanicLng={mechanicLng}
        />
        {userLat != null && userLng != null && (
          <Marker position={[userLat, userLng]}>
            <Popup>Your location</Popup>
          </Marker>
        )}
        {mechanicLat != null && mechanicLng != null && (
          <Marker position={[mechanicLat, mechanicLng]}>
            <Popup>{mechanicName || "Mechanic"}</Popup>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}
