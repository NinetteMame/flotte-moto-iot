window.initMotoTrackGPSMap = async function () {
  const mapElement = document.getElementById("gpsMap");
  const senegalBounds = {
    north: 16.8,
    south: 12.0,
    west: -17.7,
    east: -11.2,
  };
  const map = new google.maps.Map(mapElement, {
    center: { lat: 14.4974, lng: -14.4524 },
    zoom: 7,
    minZoom: 6,
    restriction: { latLngBounds: senegalBounds, strictBounds: true },
    mapTypeControl: true,
    mapTypeControlOptions: {
      mapTypeIds: ["roadmap", "satellite", "hybrid"],
      position: google.maps.ControlPosition.TOP_RIGHT,
    },
    streetViewControl: false,
    fullscreenControl: true,
    styles: [
      { featureType: "poi.business", stylers: [{ visibility: "off" }] },
      { featureType: "transit", elementType: "labels.icon", stylers: [{ visibility: "off" }] },
    ],
  });
  const markers = new Map();
  let historyLine = null;
  let historyMarkers = [];
  let initialFitDone = false;

  const motoIcon = {
    path: "M2 14a4 4 0 1 0 8 0a4 4 0 0 0-8 0m12 0a4 4 0 1 0 8 0a4 4 0 0 0-8 0M6 14h6l3-8h3l3 5h-4l-3-5H9",
    fillColor: "#c95f2d",
    fillOpacity: 1,
    strokeColor: "#ffffff",
    strokeWeight: 2,
    scale: 1.4,
    anchor: new google.maps.Point(12, 12),
  };

  function insideSenegal(position) {
    return (
      position.lat >= senegalBounds.south &&
      position.lat <= senegalBounds.north &&
      position.lng >= senegalBounds.west &&
      position.lng <= senegalBounds.east
    );
  }

  function formatDate(value) {
    return new Intl.DateTimeFormat("fr-FR", {
      dateStyle: "short",
      timeStyle: "medium",
    }).format(new Date(value));
  }

  function googleMapsUrl(latitude, longitude) {
    return `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;
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
    const path = history
      .slice()
      .reverse()
      .map((item) => ({
        lat: Number(item.latitude),
        lng: Number(item.longitude),
      }))
      .filter(insideSenegal);
    if (historyLine) historyLine.setMap(null);
    historyMarkers.forEach((marker) => marker.setMap(null));
    historyMarkers = [];
    if (path.length > 1) {
      historyLine = new google.maps.Polyline({
        map,
        path,
        strokeColor: "#c95f2d",
        strokeOpacity: 0.85,
        strokeWeight: 5,
      });
      const bounds = new google.maps.LatLngBounds();
      path.forEach((point) => bounds.extend(point));
      map.fitBounds(bounds, 55);
    }
    historyMarkers = path.slice(-20).map((point, index, points) =>
      new google.maps.Marker({
        map,
        position: point,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          fillColor: index === points.length - 1 ? "#247052" : "#e0a126",
          fillOpacity: 0.9,
          strokeColor: "#ffffff",
          strokeWeight: 2,
          scale: index === points.length - 1 ? 7 : 5,
        },
      })
    );
  }

  function renderHistoryPanel(immatriculation, history) {
    const title = document.getElementById("mapHistoryTitle");
    const summary = document.getElementById("mapHistorySummary");
    const list = document.getElementById("mapHistoryList");
    const validHistory = history
      .filter((item) =>
        insideSenegal({
          lat: Number(item.latitude),
          lng: Number(item.longitude),
        })
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
      const coordinates = {
        lat: Number(item.latitude),
        lng: Number(item.longitude),
      };
      const row = document.createElement("div");
      row.className = "map-history-row";
      const button = document.createElement("button");
      button.className = "map-history-item";
      button.innerHTML = `
        <span class="history-rank">${index + 1}</span>
        <span>
          <strong>${formatDate(item.recue_le)}</strong>
          <small>${coordinates.lat.toFixed(6)}, ${coordinates.lng.toFixed(6)}</small>
        </span>
      `;
      button.addEventListener("click", () => {
        map.panTo(coordinates);
        map.setZoom(17);
      });
      const googleLink = document.createElement("a");
      googleLink.className = "map-google-link map-google-link-compact";
      googleLink.href = googleMapsUrl(coordinates.lat, coordinates.lng);
      googleLink.target = "_blank";
      googleLink.rel = "noopener";
      googleLink.title = "Ouvrir cette position dans Google Maps";
      googleLink.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square"></i>';
      row.append(button, googleLink);
      list.appendChild(row);
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
    const list = document.getElementById("mapPositionList");
    try {
      const response = await fetch(mapElement.dataset.url, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("Réponse serveur invalide");
      const positions = await response.json();
      const visible = positions
        .map((position) => ({
          ...position,
          coordinates: {
            lat: Number(position.latitude),
            lng: Number(position.longitude),
          },
        }))
        .filter((position) => insideSenegal(position.coordinates));

      list.innerHTML = "";
      const bounds = new google.maps.LatLngBounds();
      visible.forEach((position) => {
        bounds.extend(position.coordinates);
        let markerData = markers.get(position.moto);
        if (!markerData) {
          const infoWindow = new google.maps.InfoWindow();
          const marker = new google.maps.Marker({
            map,
            position: position.coordinates,
            title: position.moto_immatriculation,
            icon: motoIcon,
          });
          marker.addListener("click", () => {
            infoWindow.open({ anchor: marker, map });
            showHistory(position);
          });
          markerData = { marker, infoWindow };
          markers.set(position.moto, markerData);
        } else {
          markerData.marker.setPosition(position.coordinates);
        }
        markerData.infoWindow.setContent(
          `<div class="google-map-popup"><strong>${position.moto_immatriculation}</strong>` +
          `<span>${formatDate(position.recue_le)}</span>` +
          `<small>${position.coordinates.lat.toFixed(6)}, ${position.coordinates.lng.toFixed(6)}</small>` +
          `<a class="map-popup-google-link" target="_blank" rel="noopener" ` +
          `href="${googleMapsUrl(position.coordinates.lat, position.coordinates.lng)}">` +
          `<i class="fa-solid fa-arrow-up-right-from-square"></i> Ouvrir dans Google Maps</a></div>`
        );

        const row = document.createElement("div");
        row.className = "map-position-row";
        const item = document.createElement("button");
        item.className = "map-position-item";
        item.innerHTML = `<span class="map-moto-icon"><i class="fa-solid fa-motorcycle"></i></span><span><strong>${position.moto_immatriculation}</strong><small>${formatDate(position.recue_le)}</small></span>`;
        item.addEventListener("click", () => {
          map.panTo(position.coordinates);
          map.setZoom(17);
          markerData.infoWindow.open({ anchor: markerData.marker, map });
          showHistory(position);
        });
        const googleLink = document.createElement("a");
        googleLink.className = "map-google-link";
        googleLink.href = googleMapsUrl(
          position.coordinates.lat,
          position.coordinates.lng
        );
        googleLink.target = "_blank";
        googleLink.rel = "noopener";
        googleLink.title = `Ouvrir ${position.moto_immatriculation} dans Google Maps`;
        googleLink.innerHTML =
          '<i class="fa-solid fa-map-location-dot"></i><span>Google Maps</span>';
        row.append(item, googleLink);
        list.appendChild(row);
      });

      const count = visible.length;
      document.getElementById("mapCount").textContent =
        `${count} moto${count > 1 ? "s" : ""} localisée${count > 1 ? "s" : ""}`;
      if (count && !initialFitDone) {
        map.fitBounds(bounds, 55);
        initialFitDone = true;
      }
      if (!count) {
        list.innerHTML = '<p class="empty">Aucune position GPS reçue au Sénégal.</p>';
      }
    } catch (error) {
      list.innerHTML =
        '<p class="field-error">Impossible de charger les positions.</p>';
    }
  }

  refreshPositions();
  window.setInterval(refreshPositions, 10000);
};
