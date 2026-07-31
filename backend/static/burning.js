(async function () {
  const mapContainer = document.getElementById("hotmap");
  if (!mapContainer || typeof L === "undefined") return;

  if (mapContainer._leaflet_id) {
    mapContainer._leaflet_id = null;
    mapContainer.innerHTML = "";
  }

  const map = L.map("hotmap").setView([13.3409, 77.1010], 11);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  try {
    const res = await fetch("/api/burn-reports");
    const reports = await res.json();

    if (!Array.isArray(reports) || reports.length === 0) {
      console.warn("No burn reports found.");
      return;
    }

    const bounds = [];

    reports.forEach((r) => {
      if (r.lat == null || r.lon == null) return;

      const color = r.label === "Likely Burning" ? "#d64541" : "#e67e22";

      const marker = L.circleMarker([r.lat, r.lon], {
        radius: 9,
        color: color,
        fillColor: color,
        fillOpacity: 0.88,
        weight: 2
      }).addTo(map);

      marker.bindPopup(`
        <div style="font-weight:700; font-size:14px; margin-bottom:6px;">
          ${r.area || "Unknown area"}
        </div>
        <div><strong>Status:</strong> ${r.status || "Pending"}</div>
        <div><strong>AI Check:</strong> ${r.label || "Unknown"} (${r.confidence || 0})</div>
        <div><strong>Note:</strong> ${r.note || "-"}</div>
        <div style="margin-top:6px; font-size:12px; color:#5f6b66;">
          ${r.ts || ""}
        </div>
      `);

      bounds.push([r.lat, r.lon]);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [28, 28] });
    }
  } catch (err) {
    console.error("Burning map error:", err);
  }
})();
