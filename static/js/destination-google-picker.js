window.initMotoTrackDestinationPicker = function () {
  const latitudeInput = document.getElementById("id_destination_latitude");
  const longitudeInput = document.getElementById("id_destination_longitude");
  const note = document.getElementById("destinationPickerNote");
  const initialPosition =
    latitudeInput.value && longitudeInput.value
      ? { lat: Number(latitudeInput.value), lng: Number(longitudeInput.value) }
      : { lat: 14.4974, lng: -14.4524 };
  const map = new google.maps.Map(
    document.getElementById("destinationPicker"),
    {
      center: initialPosition,
      zoom: latitudeInput.value ? 14 : 7,
      minZoom: 6,
      restriction: {
        latLngBounds: { north: 16.8, south: 12.0, west: -17.7, east: -11.3 },
        strictBounds: true,
      },
      mapTypeControl: true,
      mapTypeControlOptions: { mapTypeIds: ["roadmap", "satellite", "hybrid"] },
      streetViewControl: false,
    }
  );
  let marker = null;

  function setDestination(position) {
    latitudeInput.value = position.lat.toFixed(7);
    longitudeInput.value = position.lng.toFixed(7);
    note.textContent =
      `Destination : ${position.lat.toFixed(5)}, ${position.lng.toFixed(5)}`;
    if (!marker) {
      marker = new google.maps.Marker({
        map,
        position,
        draggable: true,
        title: "Destination de livraison",
      });
      marker.addListener("dragend", () => {
        const point = marker.getPosition();
        setDestination({ lat: point.lat(), lng: point.lng() });
      });
    } else {
      marker.setPosition(position);
    }
  }

  map.addListener("click", (event) => {
    setDestination({ lat: event.latLng.lat(), lng: event.latLng.lng() });
  });
  [latitudeInput, longitudeInput].forEach((input) => {
    input.addEventListener("change", () => {
      if (latitudeInput.value && longitudeInput.value) {
        const position = {
          lat: Number(latitudeInput.value),
          lng: Number(longitudeInput.value),
        };
        setDestination(position);
        map.panTo(position);
      }
    });
  });
  if (latitudeInput.value && longitudeInput.value) setDestination(initialPosition);
};
