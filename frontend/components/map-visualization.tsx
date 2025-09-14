"use client"

import { useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Loader2, RefreshCw, Download, Maximize2 } from "lucide-react"
import type { Job } from "@/lib/api"

interface MapVisualizationProps {
  type: "popular-routes" | "endpoints" | "trajectories" | "speed" | "ghg"
  status: "idle" | "running" | "completed" | "error"
  job?: Job | null // Job object with results
}

export function MapVisualization({ type, status, job }: MapVisualizationProps) {
  const [mapUrl, setMapUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Mock map URLs for demonstration
  const mockMapUrls = {
    "popular-routes": "/api/maps/popular-routes.html",
    endpoints: "/api/maps/endpoints.html",
    trajectories: "/api/maps/trajectories.html",
    speed: "/api/maps/speed.html",
    ghg: "/api/maps/ghg.html",
  }

  useEffect(() => {
    if (status === "completed" && job?.results?.mapUrl) {
      // Add cache-busting timestamp for fresh completed jobs
      const url = job.results.mapUrl.includes('?ts=') 
        ? job.results.mapUrl 
        : `${job.results.mapUrl}?ts=${Date.now()}`
      setMapUrl(url)
      setError(null)
    } else if (status === "completed") {
      // Fallback to mock URL if no job results
      setMapUrl(mockMapUrls[type])
      setError(null)
    } else if (status === "error") {
      setError(job?.error || "Failed to generate map visualization")
      setMapUrl(null)
    } else if (status === "running" || status === "idle") {
      // Keep existing map URL if available for instant tab switching
      if (!mapUrl) {
        setMapUrl(null)
      }
      setError(null)
    }
  }, [status, type, job])

  const handleRefresh = () => {
    setIsLoading(true)
    // Simulate refresh delay
    setTimeout(() => {
      const url = job?.results?.mapUrl || mockMapUrls[type]
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
      case "ghg":
        return "Shows greenhouse gas emissions intensity across different route segments"
      default:
        return "Interactive map visualization"
    }
  }

  const getMapTitle = () => {
    if (type === "speed" && job?.results?.statistics?.speedPercentiles) {
      return "Average Speed Heat Map"
    }
    switch (type) {
      case "popular-routes":
        return "Popular Routes Visualization"
      case "endpoints":
        return "Trip Endpoints Heatmap"
      case "trajectories":
        return "Trip Trajectories Map"
      case "speed":
        return "Traffic Congestion Map"
      case "ghg":
        return "GHG Emissions Heatmap"
      default:
        return "Map Visualization"
    }
  }

  const getAnalysisNote = () => {
    if (type === "ghg") {
      return "Acid color palette: higher intensity = more kg CO₂e"
    }
    if (type === "speed" && job?.results?.statistics?.speedPercentiles) {
      return "Legend shows Average Speed (km/h)"
    }
    return null
  }

  return (
    <div className="space-y-4">
      {/* Map Controls */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">{getMapTitle()}</h3>
          <p className="text-sm text-muted-foreground">{getMapDescription()}</p>
          {getAnalysisNote() && (
            <p className="text-sm text-blue-600 font-medium mt-1">{getAnalysisNote()}</p>
          )}
          {job?.id && <p className="text-xs text-muted-foreground">Job ID: {job.id}</p>}
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
          {status === "running" && !mapUrl && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm">
              <div className="text-center space-y-4">
                <Loader2 className="h-8 w-8 animate-spin mx-auto text-green-600" />
                <div>
                  <p className="font-medium">Generating {type.replace("-", " ")} visualization...</p>
                  <p className="text-sm text-muted-foreground">This may take a few moments</p>
                  {job?.progress && job.progress > 0 && (
                    <div className="mt-2">
                      <div className="w-48 mx-auto bg-muted rounded-full h-2">
                        <div
                          className="bg-green-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">{job.progress}% complete</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {status === "running" && mapUrl && (
            <div className="absolute top-4 right-4 z-10">
              <Badge variant="secondary" className="gap-1 bg-blue-100 text-blue-800">
                <Loader2 className="h-3 w-3 animate-spin" />
                Processing {job?.progress || 0}%
              </Badge>
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
      {status === "completed" && job?.results?.statistics && (
        <div className="space-y-4">
          {/* Primary v2.0.0 Statistics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Distance */}
            {job.results.statistics.totalDistanceKm !== undefined && (
              <Card className="p-4">
                <div className="text-2xl font-bold text-green-600">
                  {job.results.statistics.totalDistanceKm.toFixed(1)} km
                </div>
                <div className="text-sm text-muted-foreground">Total Distance</div>
              </Card>
            )}

            {/* Total Emissions */}
            {job.results.statistics.totalEmissionsKgCO2e !== undefined && (
              <Card className="p-4">
                <div className="text-2xl font-bold text-orange-600">
                  {job.results.statistics.totalEmissionsKgCO2e.toFixed(2)} kg
                </div>
                <div className="text-sm text-muted-foreground">Total Emissions (CO₂e)</div>
              </Card>
            )}

            {/* Emissions per Vehicle */}
            {job.results.statistics.emissionsPerVehicleKgCO2e !== undefined && (
              <Card className="p-4">
                <div className="text-2xl font-bold text-red-600">
                  {job.results.statistics.emissionsPerVehicleKgCO2e.toFixed(3)} kg
                </div>
                <div className="text-sm text-muted-foreground">Emissions per Vehicle (CO₂e)</div>
              </Card>
            )}

            {/* Congestion Areas */}
            {job.results.statistics.congestionAreas !== undefined && (
              <Card className="p-4">
                <div className="text-2xl font-bold text-yellow-600">
                  {job.results.statistics.congestionAreas.toLocaleString()}
                </div>
                <div className="text-sm text-muted-foreground">Congestion Areas</div>
              </Card>
            )}
          </div>

          {/* Speed Percentiles */}
          {job.results.statistics.speedPercentiles && (
            <Card className="p-4">
              <h4 className="text-lg font-medium mb-3">Speed Percentiles</h4>
              <div className="grid grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-xl font-bold text-blue-600">
                    {job.results.statistics.speedPercentiles.p25.toFixed(1)} km/h
                  </div>
                  <div className="text-sm text-muted-foreground">P25</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-bold text-blue-600">
                    {job.results.statistics.speedPercentiles.p50.toFixed(1)} km/h
                  </div>
                  <div className="text-sm text-muted-foreground">P50 (Median)</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-bold text-blue-600">
                    {job.results.statistics.speedPercentiles.p75.toFixed(1)} km/h
                  </div>
                  <div className="text-sm text-muted-foreground">P75</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-bold text-blue-600">
                    {job.results.statistics.speedPercentiles.p95.toFixed(1)} km/h
                  </div>
                  <div className="text-sm text-muted-foreground">P95</div>
                </div>
              </div>
            </Card>
          )}

          {/* Legacy Statistics (if new fields not available) */}
          {(!job.results.statistics.totalDistanceKm && !job.results.statistics.speedPercentiles) && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card className="p-4">
                <div className="text-2xl font-bold text-green-600">
                  {job.results.statistics.totalRecords?.toLocaleString() || "N/A"}
                </div>
                <div className="text-sm text-muted-foreground">Records processed</div>
              </Card>

              <Card className="p-4">
                <div className="text-2xl font-bold">
                  {job.results.statistics.uniqueVehicles?.toLocaleString() || "N/A"}
                </div>
                <div className="text-sm text-muted-foreground">Unique vehicles</div>
              </Card>

              <Card className="p-4">
                <div className="text-2xl font-bold">
                  {job.results.statistics.avgSpeed ? `${job.results.statistics.avgSpeed} km/h` : "N/A"}
                </div>
                <div className="text-sm text-muted-foreground">Average speed</div>
              </Card>

              <Card className="p-4">
                <div className="text-2xl font-bold">
                  {job.results.statistics.maxSpeed ? `${job.results.statistics.maxSpeed} km/h` : "N/A"}
                </div>
                <div className="text-sm text-muted-foreground">Max speed</div>
              </Card>
            </div>
          )}

          {/* Additional Statistics (any other fields) */}
          {Object.entries(job.results.statistics).filter(([key]) => 
            !['totalDistanceKm', 'totalEmissionsKgCO2e', 'emissionsPerVehicleKgCO2e', 'speedPercentiles', 'congestionAreas', 'totalRecords', 'uniqueVehicles', 'avgSpeed', 'maxSpeed', 'note'].includes(key)
          ).length > 0 && (
            <Card className="p-4">
              <h4 className="text-lg font-medium mb-3">Additional Statistics</h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {Object.entries(job.results.statistics)
                  .filter(([key]) => 
                    !['totalDistanceKm', 'totalEmissionsKgCO2e', 'emissionsPerVehicleKgCO2e', 'speedPercentiles', 'congestionAreas', 'totalRecords', 'uniqueVehicles', 'avgSpeed', 'maxSpeed', 'note'].includes(key)
                  )
                  .map(([key, value]) => (
                    <div key={key} className="text-center">
                      <div className="text-lg font-bold text-gray-600">
                        {typeof value === 'number' ? value.toLocaleString() : String(value)}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}
                      </div>
                    </div>
                  ))}
              </div>
            </Card>
          )}
        </div>
      )}
      
      {/* Show note if data was sampled */}
      {status === "completed" && job?.results?.statistics?.note && (
        <Card className="p-4 bg-blue-50 border-blue-200">
          <div className="flex items-center gap-2">
            <span className="text-blue-600 text-sm">ℹ️</span>
            <p className="text-sm text-blue-800">{job.results.statistics.note}</p>
          </div>
        </Card>
      )}
    </div>
  )
}
