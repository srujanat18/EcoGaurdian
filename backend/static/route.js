(function () {
  const mapContainer = document.getElementById("routeMap");
  if (!mapContainer || typeof L === "undefined") return;

  const resultBox = document.getElementById("result");

  if (mapContainer._leaflet_id) {
    mapContainer._leaflet_id = null;
    mapContainer.innerHTML = "";
  }

  const map = L.map("routeMap").setView([13.3409, 77.1010], 11);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  let routeLayer = null;
  let startMarker = null;
  let endMarker = null;

  function setMessage(message, tone) {
    if (!resultBox) return;
    resultBox.className = "pill" + (tone ? " " + tone : "");
    resultBox.textContent = message;
  }

  function parseCoordinate(id, label) {
    const raw = document.getElementById(id)?.value.trim();
    const value = Number(raw);

    if (!raw || Number.isNaN(value)) {
      throw new Error(`Enter a valid ${label}.`);
    }

    return value;
  }

  function clearRoute() {
    if (routeLayer) {
      map.removeLayer(routeLayer);
      routeLayer = null;
    }
    if (startMarker) {
      map.removeLayer(startMarker);
      startMarker = null;
    }
    if (endMarker) {
      map.removeLayer(endMarker);
      endMarker = null;
    }
  }

  window.scoreRoute = function scoreRoute() {
    try {
      const startLat = parseCoordinate("start_lat", "start latitude");
      const startLon = parseCoordinate("start_lon", "start longitude");
      const endLat = parseCoordinate("end_lat", "end latitude");
      const endLon = parseCoordinate("end_lon", "end longitude");

      clearRoute();

      startMarker = L.marker([startLat, startLon]).addTo(map).bindPopup("Start").openPopup();
      endMarker = L.marker([endLat, endLon]).addTo(map).bindPopup("End");

      routeLayer = L.polyline(
        [
          [startLat, startLon],
          [endLat, endLon]
        ],
        {
          color: "#1e6b43",
          weight: 5,
          opacity: 0.85
        }
      ).addTo(map);

      map.fitBounds(routeLayer.getBounds(), { padding: [30, 30] });

      setMessage(
        "Basic route preview only. Backend route scoring API is not connected yet.",
        "mid"
      );
    } catch (error) {
      setMessage(error.message, "bad");
    }
  };

  setMessage("Enter start and end coordinates to preview a route.", "");
})();
