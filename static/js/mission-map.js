const missionMapElement = document.getElementById("missionMap");
const destinationLatitude = Number(missionMapElement.dataset.destinationLat);
const destinationLongitude = Number(missionMapElement.dataset.destinationLng);
const hasDestination =
  missionMapElement.dataset.destinationLat !== "" &&
  missionMapElement.dataset.destinationLng !== "";
const senegalMissionBounds = L.latLngBounds([12.0, -17.7], [16.8, -11.3]);
const missionMap = L.map("missionMap", {
  maxBounds: senegalMissionBounds,
  maxBoundsViscosity: 1.0,
  minZoom: 6,
}).setView(
  hasDestination
    ? [destinationLatitude, destinationLongitude]
    : [14.4974, -14.4524],
  hasDestination ? 14 : 7
);
let motoMarker = null;
let routeLine = null;
let directionArrow = null;
let currentMotoPosition = null;

const missionStreetLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
  maxZoom: 19,
  attribution: "Tiles &copy; Esri",
});
const missionSatelliteLayer = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 19, attribution: "Tiles &copy; Esri" }
);
missionStreetLayer.addTo(missionMap);
L.control.layers(
  { "Plan": missionStreetLayer, "Satellite": missionSatelliteLayer },
  {},
  { collapsed: false, position: "topright" }
).addTo(missionMap);

if (hasDestination) {
  L.marker([destinationLatitude, destinationLongitude], {
    icon: L.divIcon({
      className: "destination-marker",
      html: '<span><i class="fa-solid fa-location-dot"></i></span>',
      iconSize: [42, 42],
      iconAnchor: [21, 40],
    }),
  })
    .addTo(missionMap)
    .bindPopup(
      `<strong>${missionMapElement.dataset.client}</strong><br>${missionMapElement.dataset.address}`
    )
    .openPopup();
}

function setRouteStatus(message, type = "waiting") {
  const status = document.getElementById("missionRouteStatus");
  if (!status) return;
  status.textContent = message;
  status.className = `mission-route-status is-${type}`;
}

function updateRouteLinks(motoPosition) {
  const routeUrl =
    `https://www.google.com/maps/dir/?api=1&origin=${motoPosition[0]},${motoPosition[1]}` +
    `&destination=${destinationLatitude},${destinationLongitude}&travelmode=driving`;
  const externalButton = document.getElementById("missionExternalRouteButton");
  if (externalButton) externalButton.href = routeUrl;
}

function midpoint(start, end) {
  return [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2];
}

function bearing(start, end) {
  const lat1 = start[0] * Math.PI / 180;
  const lat2 = end[0] * Math.PI / 180;
  const deltaLng = (end[1] - start[1]) * Math.PI / 180;
  const y = Math.sin(deltaLng) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLng);
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

function updateDirectionArrow(start, end) {
  if (directionArrow) missionMap.removeLayer(directionArrow);
  const angle = bearing(start, end);
  directionArrow = L.marker(midpoint(start, end), {
    icon: L.divIcon({
      className: "route-arrow-marker",
      html: `<span style="transform: rotate(${angle}deg)"><i class="fa-solid fa-location-arrow"></i></span>`,
      iconSize: [40, 40],
      iconAnchor: [20, 20],
    }),
  }).addTo(missionMap);
}

function clearRoute() {
  if (routeLine) {
    missionMap.removeLayer(routeLine);
    routeLine = null;
  }
  if (directionArrow) {
    missionMap.removeLayer(directionArrow);
    directionArrow = null;
  }
}

function drawRoute(path, options = {}) {
  clearRoute();
  routeLine = L.polyline(path, {
    color: options.color || "#c65d2e",
    weight: options.weight || 4,
    opacity: 0.9,
    dashArray: options.dashArray || null,
  }).addTo(missionMap);

  const middleIndex = Math.max(1, Math.floor(path.length / 2));
  updateDirectionArrow(path[middleIndex - 1], path[middleIndex]);
  missionMap.fitBounds(routeLine.getBounds(), { padding: [45, 45], maxZoom: 16 });
}

async function drawRoadRoute(start) {
  const destination = [destinationLatitude, destinationLongitude];
  setRouteStatus("Calcul de la route reelle...", "loading");
  const url =
    "https://router.project-osrm.org/route/v1/driving/" +
    `${start[1]},${start[0]};${destination[1]},${destination[0]}` +
    "?overview=full&geometries=geojson";

  try {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("Itinéraire indisponible");
    const data = await response.json();
    const coordinates = data.routes?.[0]?.geometry?.coordinates || [];
    const path = coordinates.map((point) => [point[1], point[0]]);
    if (path.length < 2) throw new Error("Trajet incomplet");
    drawRoute(path, { color: "#247052", weight: 5 });
    setRouteStatus("Itineraire routier affiche", "ok");
    return true;
  } catch (error) {
    clearRoute();
    setRouteStatus("Route routiere indisponible pour ces points", "error");
    return false;
  }
}

function motoIcon() {
  return L.divIcon({
    className: "moto-marker",
    html: '<span><svg viewBox="0 0 24 24"><path d="M5 17a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm14 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM5 14h4l3-6h3l2 3h2m-9 3 4 0-3-5H8"/></svg></span>',
    iconSize: [42, 42],
    iconAnchor: [21, 21],
  });
}

async function refreshMissionMoto() {
  if (!hasDestination) return;
  const response = await fetch(
    `/api/missions/${missionMapElement.dataset.missionId}/`,
    { headers: { Accept: "application/json" } }
  );
  if (!response.ok) return;
  const mission = await response.json();
  if (!mission.last_position) return;

  const motoPosition = [
    Number(mission.last_position.latitude),
    Number(mission.last_position.longitude),
  ];
  if (!senegalMissionBounds.contains(L.latLng(...motoPosition))) return;
  currentMotoPosition = motoPosition;

  if (!motoMarker) {
    motoMarker = L.marker(motoPosition, { icon: motoIcon() })
      .addTo(missionMap)
      .bindPopup(`<strong>${missionMapElement.dataset.moto}</strong>`);
  } else {
    motoMarker.setLatLng(motoPosition);
  }

  updateRouteLinks(motoPosition);
  await drawRoadRoute(motoPosition);
}

refreshMissionMoto();
setInterval(refreshMissionMoto, 10000);
