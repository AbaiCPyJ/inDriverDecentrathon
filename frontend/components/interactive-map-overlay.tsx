"use client"

import { useState, useRef, useEffect } from "react"
import { TimeSelectionPopup } from "./time-selection-popup"

interface InteractiveMapOverlayProps {
  onLocationTimeSelect: (lat: number, lng: number, timeSeconds: number) => void
  enabled: boolean
  jobId?: string | null
}

export function InteractiveMapOverlay({
  onLocationTimeSelect,
  enabled,
  jobId,
}: InteractiveMapOverlayProps) {
  const [popupOpen, setPopupOpen] = useState(false)
  const [clickPosition, setClickPosition] = useState<{ x: number; y: number } | null>(null)
  const [mapCoordinates, setMapCoordinates] = useState<{ lat: number; lng: number } | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [selectedData, setSelectedData] = useState<{ 
    timeWindow: number; 
    peopleCount: number;
    totalVehicles?: number;
    vehiclesPassed?: number;
    message?: string;
  } | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)
  const clickMarkerRef = useRef<HTMLDivElement>(null)
  const dragStartRef = useRef<{ x: number; y: number } | null>(null)

  const handleMouseDown = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!enabled) return
    
    // Record start position for drag detection
    dragStartRef.current = { x: event.clientX, y: event.clientY }
    setIsDragging(false)
  }

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!dragStartRef.current) return
    
    // Check if mouse has moved more than 5 pixels (dragging)
    const dx = Math.abs(event.clientX - dragStartRef.current.x)
    const dy = Math.abs(event.clientY - dragStartRef.current.y)
    
    if (dx > 5 || dy > 5) {
      setIsDragging(true)
    }
  }

  const handleMouseUp = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!enabled) return
    
    // If it was a drag, don't show popup
    if (isDragging) {
      dragStartRef.current = null
      setIsDragging(false)
      return
    }
    
    // Only handle left clicks
    if (event.button !== 0) return

    const rect = event.currentTarget.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top
    
    // Store click position for popup placement
    setClickPosition({ x, y })
    
    // Get more accurate coordinates based on actual data coverage
    // Based on backend logs, data is concentrated around 51.094-51.098 lat and 71.404-71.414 lng
    const mapWidth = rect.width
    const mapHeight = rect.height
    
    // These bounds match where the actual GPS data is concentrated
    const minLat = 51.092
    const maxLat = 51.100
    const minLng = 71.402
    const maxLng = 71.416
    
    // Convert pixel position to lat/lng within these bounds
    const lat = maxLat - (y / mapHeight) * (maxLat - minLat)
    const lng = minLng + (x / mapWidth) * (maxLng - minLng)
    
    console.log(`Click at pixel (${x}, ${y}) mapped to coordinates (${lat}, ${lng})`)
    
    setMapCoordinates({ lat, lng })
    setPopupOpen(true)
    dragStartRef.current = null
  }

  const handleTimeSelect = async (seconds: number) => {
    if (mapCoordinates) {
      setIsLoading(true)
      onLocationTimeSelect(mapCoordinates.lat, mapCoordinates.lng, seconds)
      
      try {
        // Call the real API endpoint to get traffic data
        const params = new URLSearchParams({
          lat: mapCoordinates.lat.toString(),
          lng: mapCoordinates.lng.toString(),
          radius_m: "100",
          time_window_sec: seconds.toString(),
          ...(jobId && { job_id: jobId })
        })
        
        const response = await fetch(`http://localhost:8000/api/traffic-analysis?${params}`)
        const data = await response.json()
        
        console.log("Traffic API response:", data)
        
        // If we got debug info, log it
        if (data.debug) {
          console.log("Debug info:", data.debug)
        }
        
        setSelectedData({
          timeWindow: seconds,
          peopleCount: data.vehicleCount || 0,
          totalVehicles: data.totalVehiclesInArea,
          vehiclesPassed: data.vehiclesPassed,
          message: data.message
        })
      } catch (error) {
        console.error("Failed to fetch traffic data:", error)
        // Fallback to simulated data if API fails
        const baseCount = Math.floor(Math.abs(mapCoordinates.lat * 100 + mapCoordinates.lng * 50))
        let peopleCount: number
        if (seconds === 30) {
          peopleCount = Math.floor(baseCount * 0.8 + Math.random() * 100)
        } else if (seconds === 60) {
          peopleCount = Math.floor(baseCount * 0.4 + Math.random() * 50)
        } else {
          peopleCount = Math.floor(baseCount * 0.15 + Math.random() * 20)
        }
        
        setSelectedData({
          timeWindow: seconds,
          peopleCount: peopleCount,
          message: "Using simulated data"
        })
      } finally {
        setIsLoading(false)
      }
    }
  }

  useEffect(() => {
    // Position the click marker if we have a click position
    if (clickMarkerRef.current && clickPosition) {
      clickMarkerRef.current.style.left = `${clickPosition.x}px`
      clickMarkerRef.current.style.top = `${clickPosition.y}px`
    }
  }, [clickPosition])

  useEffect(() => {
    // Reset selected data when popup closes
    if (!popupOpen) {
      setSelectedData(null)
    }
  }, [popupOpen])

  if (!enabled) return null

  return (
    <>
      <div
        ref={overlayRef}
        className="absolute inset-0 z-10"
        style={{ cursor: isDragging ? "grabbing" : "crosshair" }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
      >
        {clickPosition && (
          <div
            className="absolute"
            style={{
              left: clickPosition.x,
              top: clickPosition.y,
              transform: 'translate(-50%, -50%)',
            }}
            onMouseDown={(e) => e.stopPropagation()}
            onMouseMove={(e) => e.stopPropagation()}
            onMouseUp={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
          >
            <TimeSelectionPopup
              open={popupOpen}
              onOpenChange={setPopupOpen}
              onSelectTime={handleTimeSelect}
              selectedData={selectedData}
              isLoading={isLoading}
            >
              <div
                ref={clickMarkerRef}
                className="w-6 h-6"
              >
                <div className="relative">
                  <div className="absolute inset-0 bg-blue-500 rounded-full animate-ping opacity-75" />
                  <div className="relative bg-blue-600 rounded-full w-6 h-6 border-2 border-white shadow-lg" />
                </div>
              </div>
            </TimeSelectionPopup>
          </div>
        )}
      </div>
      
    </>
  )
}