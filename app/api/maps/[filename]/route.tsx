import { type NextRequest, NextResponse } from "next/server"

// Mock map HTML content for demonstration
const generateMockMapHTML = (type: string) => {
  return `
<!DOCTYPE html>
<html>
<head>
    <title>inDrive Geotracks - ${type}</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body { margin: 0; padding: 0; }
        #map { height: 100vh; width: 100%; }
        .info-box {
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info-box">
        <h4>inDrive Geotracks</h4>
        <p><strong>Analysis:</strong> ${type}</p>
        <p><strong>Status:</strong> Demo Mode</p>
    </div>
    
    <script>
        // Initialize map centered on Moscow
        var map = L.map('map').setView([55.7558, 37.6176], 11);
        
        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        
        // Add sample markers based on analysis type
        var markers = [];
        
        if ('${type}' === 'popular-routes') {
            // Sample popular route
            var route = [
                [55.7558, 37.6176],
                [55.7608, 37.6256],
                [55.7658, 37.6336],
                [55.7708, 37.6416]
            ];
            L.polyline(route, {color: '#16a34a', weight: 4}).addTo(map);
            L.marker([55.7558, 37.6176]).addTo(map).bindPopup('Popular Route Start');
            L.marker([55.7708, 37.6416]).addTo(map).bindPopup('Popular Route End');
        }
        
        if ('${type}' === 'endpoints') {
            // Sample endpoint heatmap points
            for (let i = 0; i < 20; i++) {
                var lat = 55.7558 + (Math.random() - 0.5) * 0.1;
                var lng = 37.6176 + (Math.random() - 0.5) * 0.1;
                L.circleMarker([lat, lng], {
                    radius: Math.random() * 10 + 5,
                    fillColor: '#16a34a',
                    color: '#16a34a',
                    weight: 1,
                    opacity: 0.8,
                    fillOpacity: 0.6
                }).addTo(map);
            }
        }
        
        if ('${type}' === 'trajectories') {
            // Sample trajectory paths
            for (let i = 0; i < 5; i++) {
                var startLat = 55.7558 + (Math.random() - 0.5) * 0.05;
                var startLng = 37.6176 + (Math.random() - 0.5) * 0.05;
                var endLat = startLat + (Math.random() - 0.5) * 0.02;
                var endLng = startLng + (Math.random() - 0.5) * 0.02;
                
                L.polyline([[startLat, startLng], [endLat, endLng]], {
                    color: '#16a34a',
                    weight: 2,
                    opacity: 0.7
                }).addTo(map);
            }
        }
        
        if ('${type}' === 'speed') {
            // Sample speed analysis segments
            var speedColors = ['#ef4444', '#f97316', '#eab308', '#16a34a'];
            for (let i = 0; i < 10; i++) {
                var lat = 55.7558 + (Math.random() - 0.5) * 0.08;
                var lng = 37.6176 + (Math.random() - 0.5) * 0.08;
                var endLat = lat + (Math.random() - 0.5) * 0.01;
                var endLng = lng + (Math.random() - 0.5) * 0.01;
                
                L.polyline([[lat, lng], [endLat, endLng]], {
                    color: speedColors[Math.floor(Math.random() * speedColors.length)],
                    weight: 4,
                    opacity: 0.8
                }).addTo(map);
            }
        }
    </script>
</body>
</html>
  `.trim()
}

export async function GET(request: NextRequest, { params }: { params: { filename: string } }) {
  const filename = params.filename

  // Extract analysis type from filename (e.g., "popular-routes.html")
  const analysisType = filename.replace(".html", "")

  // In a real implementation, this would fetch the actual map file
  // For demo purposes, we generate a mock Leaflet map
  const mapHTML = generateMockMapHTML(analysisType)

  return new NextResponse(mapHTML, {
    headers: {
      "Content-Type": "text/html",
      "Cache-Control": "public, max-age=3600",
    },
  })
}
