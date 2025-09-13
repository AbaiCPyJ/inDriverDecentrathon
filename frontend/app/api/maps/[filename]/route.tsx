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
        // Initialize map centered on Astana, Kazakhstan  
        var map = L.map('map').setView([51.091385, 71.417226], 13);
        
        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        
        // Add sample markers based on analysis type
        var markers = [];
        
        if ('${type}' === 'popular-routes') {
            // Sample popular route
            var route = [
                [51.091385, 71.417226],
                [51.095385, 71.422226],
                [51.099385, 71.427226],
                [51.103385, 71.432226]
            ];
            L.polyline(route, {color: '#16a34a', weight: 4}).addTo(map);
            L.marker([51.091385, 71.417226]).addTo(map).bindPopup('Popular Route Start - Astana');
            L.marker([51.103385, 71.432226]).addTo(map).bindPopup('Popular Route End - Astana');
        }
        
        if ('${type}' === 'endpoints') {
            // Sample endpoint heatmap points
            for (let i = 0; i < 20; i++) {
                var lat = 51.091385 + (Math.random() - 0.5) * 0.02;
                var lng = 71.417226 + (Math.random() - 0.5) * 0.02;
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
                var startLat = 51.091385 + (Math.random() - 0.5) * 0.02;
                var startLng = 71.417226 + (Math.random() - 0.5) * 0.02;
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
                var lat = 51.091385 + (Math.random() - 0.5) * 0.02;
                var lng = 71.417226 + (Math.random() - 0.5) * 0.02;
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

  try {
    // Try to fetch the actual map from the backend first
    const backendUrl = `http://localhost:8000/api/maps/${filename}`
    
    const response = await fetch(backendUrl)
    
    if (response.ok) {
      // Return the actual backend-generated map (Astana with OpenStreetMap)
      const mapHTML = await response.text()
      return new NextResponse(mapHTML, {
        headers: {
          "Content-Type": "text/html",
          "Cache-Control": "public, max-age=3600",
        },
      })
    }
  } catch (error) {
    console.log("Backend not available, falling back to mock map")
  }

  // Fallback to mock map if backend is not available
  const analysisType = filename.replace(".html", "")
  const mapHTML = generateMockMapHTML(analysisType)

  return new NextResponse(mapHTML, {
    headers: {
      "Content-Type": "text/html",
      "Cache-Control": "public, max-age=3600",
    },
  })
}
