"use client"

import { useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Loader2, RefreshCw, Download, Maximize2 } from "lucide-react"

interface MapVisualizationProps {
  type: "popular-routes" | "endpoints" | "trajectories" | "speed"
  status: "idle" | "running" | "completed" | "error"
  jobId?: string | null // Added jobId prop for job-specific maps
}

export function MapVisualization({ type, status, jobId }: MapVisualizationProps) {
  const [mapUrl, setMapUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Mock map URLs for demonstration
  const mockMapUrls = {
    "popular-routes": "/api/maps/popular-routes.html",
    endpoints: "/api/maps/endpoints.html",
    trajectories: "/api/maps/trajectories.html",
    speed: "/api/maps/speed.html",
  }

  useEffect(() => {
    if (status === "completed") {
      const url = jobId ? `/api/maps/${jobId}.html` : mockMapUrls[type]
      setMapUrl(url)
      setError(null)
    } else if (status === "error") {
      setError("Failed to generate map visualization")
      setMapUrl(null)
    } else if (status === "running") {
      setMapUrl(null)
      setError(null)
    }
  }, [status, type, jobId])

  const handleRefresh = () => {
    setIsLoading(true)
    // Simulate refresh delay
    setTimeout(() => {
      const url = jobId ? `/api/maps/${jobId}.html` : mockMapUrls[type]
      setMapUrl(url)
      setIsLoading(false)
    }, 1000)
  }

  const handleDownload = () => {
    if (mapUrl) {
      const link = document.createElement("a")
      link.href = mapUrl
      link.download = `${type}-map.html`
      link.click()
    }
  }

  const getMapTitle = () => {
    switch (type) {
      case "popular-routes":
        return "Popular Routes Visualization"
      case "endpoints":
        return "Trip Endpoints Heatmap"
      case "trajectories":
        return "Trip Trajectories Map"
      case "speed":
        return "Speed Analysis Map"
      default:
        return "Map Visualization"
    }
  }

  const getMapDescription = () => {
    switch (type) {
      case "popular-routes":
        return "Displays the most frequently used routes based on anonymized trip data"
      case "endpoints":
        return "Shows pickup and dropoff locations as a heatmap overlay"
      case "trajectories":
        return "Visualizes actual trip paths and route variations"
      case "speed":
        return "Analyzes speed patterns across different road segments"
      default:
        return "Interactive map visualization"
    }
  }

  return (
    <div className="space-y-4">
      {/* Map Controls */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">{getMapTitle()}</h3>
          <p className="text-sm text-muted-foreground">{getMapDescription()}</p>
          {jobId && <p className="text-xs text-muted-foreground">Job ID: {jobId}</p>}
        </div>

        <div className="flex items-center gap-2">
          <Badge variant={status === "completed" ? "default" : "secondary"}>
            {status === "running" && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </Badge>

          {mapUrl && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={isLoading}
                className="gap-1 bg-transparent"
              >
                <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                Refresh
              </Button>

              <Button variant="outline" size="sm" onClick={handleDownload} className="gap-1 bg-transparent">
                <Download className="h-4 w-4" />
                Export
              </Button>

              <Button variant="outline" size="sm" className="gap-1 bg-transparent">
                <Maximize2 className="h-4 w-4" />
                Fullscreen
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Map Container */}
      <Card className="overflow-hidden">
        <div className="relative h-[600px] bg-muted/20">
          {status === "running" && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm">
              <div className="text-center space-y-4">
                <Loader2 className="h-8 w-8 animate-spin mx-auto text-green-600" />
                <div>
                  <p className="font-medium">Generating {type.replace("-", " ")} visualization...</p>
                  <p className="text-sm text-muted-foreground">This may take a few moments</p>
                </div>
              </div>
            </div>
          )}

          {status === "idle" && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center space-y-4">
                <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center mx-auto">
                  <div className="h-8 w-8 rounded bg-green-600 flex items-center justify-center">
                    <span className="text-white font-bold text-sm">iD</span>
                  </div>
                </div>
                <div>
                  <p className="font-medium">Ready to generate visualization</p>
                  <p className="text-sm text-muted-foreground">Click "Run Analysis" to start processing</p>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center space-y-4">
                <div className="h-16 w-16 rounded-full bg-red-100 flex items-center justify-center mx-auto">
                  <span className="text-red-600 text-2xl">⚠</span>
                </div>
                <div>
                  <p className="font-medium text-red-600">Error generating visualization</p>
                  <p className="text-sm text-muted-foreground">{error}</p>
                </div>
              </div>
            </div>
          )}

          {mapUrl && !isLoading && (
            <iframe
              src={mapUrl}
              className="w-full h-full border-0"
              title={getMapTitle()}
              sandbox="allow-scripts allow-same-origin"
              onError={() => setError("Failed to load map visualization")}
            />
          )}
        </div>
      </Card>

      {/* Map Statistics */}
      {status === "completed" && (
        <div className="grid grid-cols-4 gap-4">
          <Card className="p-4">
            <div className="text-2xl font-bold text-green-600">
              {type === "popular-routes"
                ? "1,247"
                : type === "endpoints"
                  ? "3,892"
                  : type === "trajectories"
                    ? "856"
                    : "2,341"}
            </div>
            <div className="text-sm text-muted-foreground">
              {type === "popular-routes"
                ? "Routes analyzed"
                : type === "endpoints"
                  ? "Endpoints mapped"
                  : type === "trajectories"
                    ? "Trajectories plotted"
                    : "Speed segments"}
            </div>
          </Card>

          <Card className="p-4">
            <div className="text-2xl font-bold">
              {type === "popular-routes"
                ? "89%"
                : type === "endpoints"
                  ? "94%"
                  : type === "trajectories"
                    ? "76%"
                    : "82%"}
            </div>
            <div className="text-sm text-muted-foreground">Coverage rate</div>
          </Card>

          <Card className="p-4">
            <div className="text-2xl font-bold">
              {type === "popular-routes"
                ? "12.3km"
                : type === "endpoints"
                  ? "45.2km²"
                  : type === "trajectories"
                    ? "8.7km"
                    : "67.1km"}
            </div>
            <div className="text-sm text-muted-foreground">
              {type === "endpoints" ? "Area covered" : "Avg distance"}
            </div>
          </Card>

          <Card className="p-4">
            <div className="text-2xl font-bold">
              {type === "popular-routes"
                ? "15min"
                : type === "endpoints"
                  ? "8min"
                  : type === "trajectories"
                    ? "22min"
                    : "18min"}
            </div>
            <div className="text-sm text-muted-foreground">Processing time</div>
          </Card>
        </div>
      )}
    </div>
  )
}
