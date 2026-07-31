(async function () {
  const mapContainer = document.getElementById("map");
  if (!mapContainer || typeof L === "undefined") return;

  if (mapContainer._leaflet_id) {
    mapContainer._leaflet_id = null;
    mapContainer.innerHTML = "";
  }

  const fallbackCenter = [13.3409, 77.1010];
  const map = L.map("map").setView(fallbackCenter, 11);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  function colorFor(aqi) {
    const value = Number(aqi);
    if (value === 1) return "#239b56";
    if (value === 2) return "#d4ac0d";
    if (value === 3) return "#e67e22";
    if (value === 4) return "#d64541";
    if (value === 5) return "#7d3c98";
    return "#7f8c8d";
  }

  function labelFor(aqi) {
    const value = Number(aqi);
    if (value === 1) return "Good";
    if (value === 2) return "Fair";
    if (value === 3) return "Moderate";
    if (value === 4) return "Poor";
    if (value === 5) return "Very Poor";
    return "Unknown";
  }

  try {
    const res = await fetch("/api/aqi-zones");
    const points = await res.json();

    if (!Array.isArray(points) || points.length === 0) {
      console.warn("No AQI zone data found.");
      return;
    }

    const bounds = [];

    points.forEach((p) => {
      if (p.lat == null || p.lon == null) return;

      const color = colorFor(p.aqi);
      const marker = L.circleMarker([p.lat, p.lon], {
        radius: 8,
        color: color,
        fillColor: color,
        fillOpacity: 0.82,
        weight: 2
      }).addTo(map);

      marker.bindPopup(`
        <div style="font-weight:700; font-size:14px; margin-bottom:6px;">
          ${p.city || "Unknown area"}
        </div>
        <div><strong>AQI:</strong> ${p.aqi} (${labelFor(p.aqi)})</div>
        <div style="margin-top:6px; font-size:12px; color:#5f6b66;">
          Updated: ${p.ts || "N/A"}
        </div>
      `);

      bounds.push([p.lat, p.lon]);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [28, 28] });
    }
  } catch (err) {
    console.error("Map loading error:", err);
  }
})();
