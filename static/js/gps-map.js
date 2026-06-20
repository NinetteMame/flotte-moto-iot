const mapElement = document.getElementById("gpsMap");
const senegalBounds = L.latLngBounds(
  [12.0, -17.7],
  [16.8, -11.2]
);
const map = L.map("gpsMap", {
  maxBounds: senegalBounds,
  maxBoundsViscosity: 1.0,
  minZoom: 6,
}).setView([14.4974, -14.4524], 7);
const markers = new Map();
let historyLine = null;
let historyPointLayer = null;

const streetLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
  maxZoom: 19,
  attribution: "Tiles &copy; Esri",
});
const satelliteLayer = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 19, attribution: "Tiles &copy; Esri" }
);
streetLayer.addTo(map);
L.control.layers(
  { "Plan": streetLayer, "Satellite": satelliteLayer },
  {},
  { collapsed: false, position: "topright" }
).addTo(map);

function markerIcon() {
  return L.divIcon({
    className: "moto-marker",
    html: '<span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 17a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm14 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM5 14h4l3-6h3l2 3h2m-9 3 4 0-3-5H8"/></svg></span>',
    iconSize: [42, 42],
    iconAnchor: [21, 21],
  });
}

function isInsideSenegal(coordinates) {
  return senegalBounds.contains(L.latLng(coordinates[0], coordinates[1]));
}

function formatDate(value) {
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

async function showHistory(position) {
  return loadMotoHistory(position.moto, position.moto_immatriculation);
}

async function loadMotoHistory(motoId, immatriculation) {
  const response = await fetch(
    `/api/gps/motos/${motoId}/historique/?limit=200`,
    { headers: { Accept: "application/json" } }
  );
  if (!response.ok) return;
  const history = await response.json();
  renderHistoryPanel(immatriculation, history);
  const route = history
    .slice()
    .reverse()
    .map((item) => [Number(item.latitude), Number(item.longitude)])
    .filter(isInsideSenegal);
  if (historyLine) map.removeLayer(historyLine);
  if (historyPointLayer) map.removeLayer(historyPointLayer);
  if (route.length > 1) {
    historyLine = L.polyline(route, {
      color: "#c65d2e",
      weight: 4,
      opacity: 0.75,
      dashArray: "8 7",
    }).addTo(map);
    map.fitBounds(historyLine.getBounds(), { padding: [40, 40], maxZoom: 17 });
  }
  if (route.length) {
    historyPointLayer = L.layerGroup(
      route.slice(-20).map((coordinates, index) =>
        L.circleMarker(coordinates, {
          radius: index === route.slice(-20).length - 1 ? 6 : 4,
          color: "#ffffff",
          weight: 2,
          fillColor: index === route.slice(-20).length - 1 ? "#247052" : "#e0a126",
          fillOpacity: 0.9,
        })
      )
    ).addTo(map);
  }
}

function renderHistoryPanel(immatriculation, history) {
  const title = document.getElementById("mapHistoryTitle");
  const summary = document.getElementById("mapHistorySummary");
  const list = document.getElementById("mapHistoryList");
  const validHistory = history
    .filter((item) =>
      isInsideSenegal([Number(item.latitude), Number(item.longitude)])
    )
    .slice(0, 12);

  title.textContent = `Moto ${immatriculation}`;
  summary.innerHTML = `<strong>${history.length}</strong><span>position${history.length > 1 ? "s" : ""} enregistrée${history.length > 1 ? "s" : ""}</span>`;

  if (!validHistory.length) {
    list.innerHTML = '<p class="empty">Aucun historique disponible pour cette moto.</p>';
    return;
  }

  list.innerHTML = "";
  validHistory.forEach((item, index) => {
    const coordinates = [Number(item.latitude), Number(item.longitude)];
    const button = document.createElement("button");
    button.className = "map-history-item";
    button.innerHTML = `
      <span class="history-rank">${index + 1}</span>
      <span>
        <strong>${formatDate(item.recue_le)}</strong>
        <small>${coordinates[0].toFixed(6)}, ${coordinates[1].toFixed(6)}</small>
      </span>
    `;
    button.addEventListener("click", () => {
      map.setView(coordinates, 17);
    });
    list.appendChild(button);
  });
}

document.querySelectorAll(".tracked-moto-item").forEach((button) => {
  button.addEventListener("click", () => {
    document
      .querySelectorAll(".tracked-moto-item")
      .forEach((item) => item.classList.remove("is-selected"));
    button.classList.add("is-selected");
    loadMotoHistory(button.dataset.motoId, button.dataset.motoImmat);
  });
});

async function refreshPositions() {
  try {
    const response = await fetch(mapElement.dataset.url, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error("Réponse serveur invalide");
    const positions = await response.json();
    const bounds = [];
    const list = document.getElementById("mapPositionList");
    list.innerHTML = "";

    positions.filter((position) => {
      return isInsideSenegal([
        Number(position.latitude),
        Number(position.longitude),
      ]);
    }).forEach((position) => {
      const coordinates = [
        Number(position.latitude),
        Number(position.longitude),
      ];
      bounds.push(coordinates);
      let marker = markers.get(position.moto);
      if (!marker) {
        marker = L.marker(coordinates, { icon: markerIcon() }).addTo(map);
        markers.set(position.moto, marker);
      } else {
        marker.setLatLng(coordinates);
      }
      marker.bindPopup(
        `<strong>${position.moto_immatriculation}</strong><br>${coordinates.join(", ")}<br>${formatDate(position.recue_le)}`
      );

      const item = document.createElement("button");
      item.className = "map-position-item";
      item.innerHTML = `<span class="map-moto-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 17a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm14 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM5 14h4l3-6h3l2 3h2m-9 3 4 0-3-5H8"/></svg></span><span><strong>${position.moto_immatriculation}</strong><small>${formatDate(position.recue_le)}</small></span>`;
      item.addEventListener("click", () => {
        map.setView(coordinates, 17);
        marker.openPopup();
        showHistory(position);
      });
      list.appendChild(item);
    });

    const visibleCount = bounds.length;
    document.getElementById("mapCount").textContent =
      `${visibleCount} moto${visibleCount > 1 ? "s" : ""} localisée${visibleCount > 1 ? "s" : ""}`;
    if (bounds.length && !window.mapInitialFitDone) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
      window.mapInitialFitDone = true;
    }
    if (!visibleCount) {
      list.innerHTML = '<p class="empty">Aucune position GPS reçue au Sénégal.</p>';
    }
  } catch (error) {
    document.getElementById("mapPositionList").innerHTML =
      '<p class="field-error">Impossible de charger les positions.</p>';
  }
}

refreshPositions();
setInterval(refreshPositions, 10000);
