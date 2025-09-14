"use client"

import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Clock, Users, Loader2, AlertCircle } from "lucide-react"

interface TimeSelectionPopupProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSelectTime: (seconds: number) => void
  children: React.ReactNode
  selectedData?: { 
    timeWindow: number; 
    peopleCount: number;
    vehiclesPassed?: number;
    message?: string;
  } | null
  isLoading?: boolean
}

export function TimeSelectionPopup({
  open,
  onOpenChange,
  onSelectTime,
  children,
  selectedData,
  isLoading,
}: TimeSelectionPopupProps) {
  const timeOptions = [
    { label: "30 sec", seconds: 30 },
    { label: "1 min", seconds: 60 },
    { label: "5 min", seconds: 300 },
  ]

  const formatTimeWindow = (seconds: number) => {
    if (seconds < 60) return `${seconds} seconds`
    return `${seconds / 60} minute${seconds / 60 > 1 ? 's' : ''}`
  }

  const getCongestionLevel = (peopleCount: number, timeWindow: number) => {
    // Determine congestion level based on how many vehicles stayed (realistic thresholds)
    if (timeWindow === 300) { // 5 minutes
      if (peopleCount > 5) return { level: "Heavy", color: "text-red-600", bgColor: "bg-red-50", icon: "🔴" }
      if (peopleCount > 1) return { level: "Moderate", color: "text-orange-600", bgColor: "bg-orange-50", icon: "🟠" }
      return { level: "Light", color: "text-green-600", bgColor: "bg-green-50", icon: "🟢" }
    } else if (timeWindow === 60) { // 1 minute
      if (peopleCount > 10) return { level: "Heavy", color: "text-red-600", bgColor: "bg-red-50", icon: "🔴" }
      if (peopleCount > 3) return { level: "Moderate", color: "text-orange-600", bgColor: "bg-orange-50", icon: "🟠" }
      return { level: "Light", color: "text-green-600", bgColor: "bg-green-50", icon: "🟢" }
    } else { // 30 seconds
      if (peopleCount > 15) return { level: "Heavy", color: "text-red-600", bgColor: "bg-red-50", icon: "🔴" }
      if (peopleCount > 5) return { level: "Moderate", color: "text-orange-600", bgColor: "bg-orange-50", icon: "🟠" }
      return { level: "Light", color: "text-green-600", bgColor: "bg-green-50", icon: "🟢" }
    }
  }

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent className="w-auto p-3" align="center" sideOffset={5}>
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Clock className="h-4 w-4" />
            <span>Check Traffic Congestion</span>
          </div>
          <div className="flex gap-1">
            {timeOptions.map((option) => (
              <Button
                key={option.seconds}
                variant={selectedData?.timeWindow === option.seconds ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  onSelectTime(option.seconds)
                }}
                disabled={isLoading}
                className="min-w-[60px] h-7 text-xs"
              >
                {option.label}
              </Button>
            ))}
          </div>
          
          {/* Results section */}
          {(isLoading || selectedData) && (
            <div className="border-t pt-3">
              {isLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Loading data...</span>
                </div>
              ) : selectedData ? (() => {
                const congestion = getCongestionLevel(selectedData.peopleCount, selectedData.timeWindow)
                
                // If no vehicles stayed but some passed through
                if (selectedData.peopleCount === 0 && selectedData.vehiclesPassed) {
                  return (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Users className="h-4 w-4 text-blue-600" />
                        <span className="text-sm font-medium">Traffic Analysis</span>
                      </div>
                      <div className="bg-blue-50 rounded-md p-2">
                        <div className="text-lg font-bold text-blue-600">
                          {selectedData.vehiclesPassed} vehicles passed
                        </div>
                        <div className="text-xs text-gray-600">
                          No vehicles stayed ≥{formatTimeWindow(selectedData.timeWindow)}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          Traffic is flowing freely
                        </div>
                      </div>
                    </div>
                  )
                }
                
                // Normal display when vehicles stayed
                return (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <AlertCircle className={`h-4 w-4 ${congestion.color}`} />
                        <span className="text-sm font-medium">Traffic Analysis</span>
                      </div>
                      <span className="text-xs">{congestion.icon} {congestion.level}</span>
                    </div>
                    <div className={`${congestion.bgColor} rounded-md p-2`}>
                      <div className={`text-2xl font-bold ${congestion.color}`}>
                        {selectedData.peopleCount.toLocaleString()}
                      </div>
                      <div className="text-xs font-medium text-gray-700">
                        vehicles stayed ≥{formatTimeWindow(selectedData.timeWindow)}
                      </div>
                      <div className="text-xs text-gray-600 mt-1">
                        {congestion.level === "Heavy" 
                          ? "Significant congestion detected"
                          : congestion.level === "Moderate"
                          ? "Some traffic delays expected"
                          : "Traffic flowing normally"}
                      </div>
                    </div>
                  </div>
                )
              })() : null}
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}