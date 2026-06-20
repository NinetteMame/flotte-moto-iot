const latitudeInput = document.getElementById("id_destination_latitude");
const longitudeInput = document.getElementById("id_destination_longitude");
const pickerNote = document.getElementById("destinationPickerNote");
const senegalBounds = L.latLngBounds([12.0, -17.7], [16.8, -11.3]);
const pickerMap = L.map("destinationPicker", {
  maxBounds: senegalBounds,
  maxBoundsViscosity: 1.0,
  minZoom: 6,
}).setView([14.4974, -14.4524], 7);
let destinationMarker = null;

const pickerStreetLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
  maxZoom: 19,
  attribution: "Tiles &copy; Esri",
});
const pickerSatelliteLayer = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 19, attribution: "Tiles &copy; Esri" }
);
pickerStreetLayer.addTo(pickerMap);
L.control.layers(
  { "Plan": pickerStreetLayer, "Satellite": pickerSatelliteLayer },
  {},
  { collapsed: false, position: "topright" }
).addTo(pickerMap);

function setDestination(latitude, longitude) {
  const coordinates = L.latLng(Number(latitude), Number(longitude));
  if (!senegalBounds.contains(coordinates)) return;
  latitudeInput.value = coordinates.lat.toFixed(7);
  longitudeInput.value = coordinates.lng.toFixed(7);
  pickerNote.textContent =
    `Destination : ${coordinates.lat.toFixed(5)}, ${coordinates.lng.toFixed(5)}`;
  if (!destinationMarker) {
    destinationMarker = L.marker(coordinates, { draggable: true }).addTo(pickerMap);
    destinationMarker.on("dragend", (event) => {
      const point = event.target.getLatLng();
      if (senegalBounds.contains(point)) setDestination(point.lat, point.lng);
    });
  } else {
    destinationMarker.setLatLng(coordinates);
  }
}

pickerMap.on("click", (event) => {
  setDestination(event.latlng.lat, event.latlng.lng);
});

[latitudeInput, longitudeInput].forEach((input) => {
  input.addEventListener("change", () => {
    if (latitudeInput.value && longitudeInput.value) {
      setDestination(latitudeInput.value, longitudeInput.value);
    }
  });
});

if (latitudeInput.value && longitudeInput.value) {
  setDestination(latitudeInput.value, longitudeInput.value);
  pickerMap.setView(
    [Number(latitudeInput.value), Number(longitudeInput.value)],
    14
  );
}
