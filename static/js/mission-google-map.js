window.initMotoTrackMissionMap = function () {
  const element = document.getElementById("missionMap");
  const hasDestination =
    element.dataset.destinationLat !== "" &&
    element.dataset.destinationLng !== "";
  const destination = hasDestination
    ? {
        lat: Number(element.dataset.destinationLat),
        lng: Number(element.dataset.destinationLng),
      }
    : { lat: 14.4974, lng: -14.4524 };
  const map = new google.maps.Map(element, {
    center: destination,
    zoom: hasDestination ? 14 : 7,
    minZoom: 6,
    restriction: {
      latLngBounds: { north: 16.8, south: 12.0, west: -17.7, east: -11.3 },
      strictBounds: true,
    },
    mapTypeControl: true,
    mapTypeControlOptions: { mapTypeIds: ["roadmap", "satellite", "hybrid"] },
    streetViewControl: false,
  });
  let motoMarker = null;
  let routeLine = null;
  let directionMarker = null;
  let currentMotoPosition = null;
  let directionsRenderer = null;

  if (hasDestination) {
    const destinationMarker = new google.maps.Marker({
      map,
      position: destination,
      title: element.dataset.client,
      label: { text: "D", color: "white", fontWeight: "700" },
    });
    const infoWindow = new google.maps.InfoWindow({
      content: `<div class="google-map-popup"><strong>${element.dataset.client}</strong><span>${element.dataset.address}</span></div>`,
    });
    destinationMarker.addListener("click", () =>
      infoWindow.open({ anchor: destinationMarker, map })
    );
  }

  function setRouteStatus(message, type = "waiting") {
    const status = document.getElementById("missionRouteStatus");
    if (!status) return;
    status.textContent = message;
    status.className = `mission-route-status is-${type}`;
  }

  function updateRouteLinks(position) {
    const routeUrl =
      `https://www.google.com/maps/dir/?api=1&origin=${position.lat},${position.lng}` +
      `&destination=${destination.lat},${destination.lng}&travelmode=driving`;
    const externalButton = document.getElementById("missionExternalRouteButton");
    if (externalButton) externalButton.href = routeUrl;
  }

  function midpoint(start, end) {
    return {
      lat: (start.lat + end.lat) / 2,
      lng: (start.lng + end.lng) / 2,
    };
  }

  function bearing(start, end) {
    const lat1 = start.lat * Math.PI / 180;
    const lat2 = end.lat * Math.PI / 180;
    const deltaLng = (end.lng - start.lng) * Math.PI / 180;
    const y = Math.sin(deltaLng) * Math.cos(lat2);
    const x =
      Math.cos(lat1) * Math.sin(lat2) -
      Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLng);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  }

  function clearDirectionalMarker() {
    if (directionMarker) {
      directionMarker.setMap(null);
      directionMarker = null;
    }
  }

  function clearDirections() {
    if (directionsRenderer) {
      directionsRenderer.setMap(null);
      directionsRenderer = null;
    }
  }

  function clearRoute() {
    clearDirections();
    if (routeLine) {
      routeLine.setMap(null);
      routeLine = null;
    }
    clearDirectionalMarker();
  }

  function drawRoadRoute(position) {
    clearRoute();
    setRouteStatus("Calcul de la route reelle...", "loading");
    const service = new google.maps.DirectionsService();
    directionsRenderer = directionsRenderer || new google.maps.DirectionsRenderer({
      map,
      suppressMarkers: true,
      preserveViewport: false,
      polylineOptions: {
        strokeColor: "#247052",
        strokeOpacity: 0.95,
        strokeWeight: 4,
      },
    });
    directionsRenderer.setMap(map);
    service.route(
      {
        origin: position,
        destination,
        travelMode: google.maps.TravelMode.DRIVING,
      },
      (result, status) => {
        if (status === "OK" && result) {
          directionsRenderer.setDirections(result);
          setRouteStatus("Itineraire routier affiche", "ok");
        } else {
          clearRoute();
          setRouteStatus("Route routiere indisponible pour ces points", "error");
        }
      }
    );
  }

  async function refreshMoto() {
    if (!hasDestination) return;
    const response = await fetch(`/api/missions/${element.dataset.missionId}/`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return;
    const mission = await response.json();
    if (!mission.last_position) return;
    const position = {
      lat: Number(mission.last_position.latitude),
      lng: Number(mission.last_position.longitude),
    };
    currentMotoPosition = position;
    if (!motoMarker) {
      motoMarker = new google.maps.Marker({
        map,
        position,
        title: element.dataset.moto,
        label: { text: "M", color: "white", fontWeight: "700" },
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          fillColor: "#247052",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 3,
          scale: 17,
        },
      });
    } else {
      motoMarker.setPosition(position);
    }
    updateRouteLinks(position);
    drawRoadRoute(position);
  }

  refreshMoto();
  window.setInterval(refreshMoto, 10000);
};
