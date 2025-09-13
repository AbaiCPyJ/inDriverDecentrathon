"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { ChevronLeft, ChevronRight, Calendar, MapPin, Clock, Filter, Settings } from "lucide-react"

interface SidebarProps {
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
  activeTab: string
}

export function Sidebar({ collapsed, onCollapsedChange, activeTab }: SidebarProps) {
  const [dateRange, setDateRange] = useState({ start: "2024-01-01", end: "2024-01-31" })
  const [timeRange, setTimeRange] = useState([6, 22]) // 6 AM to 10 PM
  const [minTrips, setMinTrips] = useState([10])
  const [maxDistance, setMaxDistance] = useState([50])
  const [showHeatmap, setShowHeatmap] = useState(true)
  const [showClusters, setShowClusters] = useState(false)
  const [selectedCity, setSelectedCity] = useState("all")

  const getTabSpecificControls = () => {
    switch (activeTab) {
      case "popular-routes":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Minimum Trip Count</Label>
              <Slider value={minTrips} onValueChange={setMinTrips} max={100} min={1} step={1} className="w-full" />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>1</span>
                <span className="font-medium">{minTrips[0]} trips</span>
                <span>100</span>
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Route Clustering</Label>
              <div className="flex items-center space-x-2">
                <Switch id="clustering" checked={showClusters} onCheckedChange={setShowClusters} />
                <Label htmlFor="clustering" className="text-sm">
                  Enable clustering
                </Label>
              </div>
            </div>
          </div>
        )

      case "endpoints":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Heatmap Intensity</Label>
              <Select defaultValue="medium">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Show Heatmap</Label>
              <div className="flex items-center space-x-2">
                <Switch id="heatmap" checked={showHeatmap} onCheckedChange={setShowHeatmap} />
                <Label htmlFor="heatmap" className="text-sm">
                  Display heatmap overlay
                </Label>
              </div>
            </div>
          </div>
        )

      case "trajectories":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Max Distance (km)</Label>
              <Slider
                value={maxDistance}
                onValueChange={setMaxDistance}
                max={100}
                min={1}
                step={1}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>1km</span>
                <span className="font-medium">{maxDistance[0]}km</span>
                <span>100km</span>
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Trajectory Type</Label>
              <Select defaultValue="all">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All trajectories</SelectItem>
                  <SelectItem value="direct">Direct routes</SelectItem>
                  <SelectItem value="detoured">With detours</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )

      case "speed":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Speed Range (km/h)</Label>
              <div className="grid grid-cols-2 gap-2">
                <Input type="number" placeholder="Min" defaultValue="0" />
                <Input type="number" placeholder="Max" defaultValue="120" />
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Road Type</Label>
              <Select defaultValue="all">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All roads</SelectItem>
                  <SelectItem value="highway">Highways</SelectItem>
                  <SelectItem value="arterial">Arterial roads</SelectItem>
                  <SelectItem value="local">Local streets</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )

      default:
        return null
    }
  }

  if (collapsed) {
    return (
      <div className="fixed left-0 top-16 h-[calc(100vh-4rem)] w-16 bg-card border-r flex flex-col items-center py-4 space-y-4">
        <Button variant="ghost" size="sm" onClick={() => onCollapsedChange(false)} className="p-2">
          <ChevronRight className="h-4 w-4" />
        </Button>

        <div className="flex flex-col space-y-2">
          <Button variant="ghost" size="sm" className="p-2">
            <Filter className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" className="p-2">
            <Calendar className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" className="p-2">
            <MapPin className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" className="p-2">
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed left-0 top-16 h-[calc(100vh-4rem)] w-80 bg-card border-r overflow-y-auto">
      <div className="p-4 space-y-6">
        {/* Sidebar Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters & Controls
          </h2>
          <Button variant="ghost" size="sm" onClick={() => onCollapsedChange(true)} className="p-2">
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>

        {/* Date Range */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              Date Range
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs">Start Date</Label>
                <Input
                  type="date"
                  value={dateRange.start}
                  onChange={(e) => setDateRange((prev) => ({ ...prev, start: e.target.value }))}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">End Date</Label>
                <Input
                  type="date"
                  value={dateRange.end}
                  onChange={(e) => setDateRange((prev) => ({ ...prev, end: e.target.value }))}
                />
              </div>
            </div>
            <Badge variant="secondary" className="text-xs">
              {Math.ceil(
                (new Date(dateRange.end).getTime() - new Date(dateRange.start).getTime()) / (1000 * 60 * 60 * 24),
              )}{" "}
              days selected
            </Badge>
          </CardContent>
        </Card>

        {/* Time Range */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Time Range
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Slider value={timeRange} onValueChange={setTimeRange} max={23} min={0} step={1} className="w-full" />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>12 AM</span>
              <span className="font-medium">
                {timeRange[0]}:00 - {timeRange[1]}:00
              </span>
              <span>11 PM</span>
            </div>
          </CardContent>
        </Card>

        {/* Location Filter */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <MapPin className="h-4 w-4" />
              Location
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Select value={selectedCity} onValueChange={setSelectedCity}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Cities</SelectItem>
                <SelectItem value="moscow">Moscow</SelectItem>
                <SelectItem value="spb">St. Petersburg</SelectItem>
                <SelectItem value="kazan">Kazan</SelectItem>
                <SelectItem value="novosibirsk">Novosibirsk</SelectItem>
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Separator />

        {/* Tab-specific Controls */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Settings className="h-4 w-4" />
              {activeTab.charAt(0).toUpperCase() + activeTab.slice(1).replace("-", " ")} Settings
            </CardTitle>
          </CardHeader>
          <CardContent>{getTabSpecificControls()}</CardContent>
        </Card>

        {/* Data Summary */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Data Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Total Trips:</span>
              <span className="font-medium">24,891</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Filtered:</span>
              <span className="font-medium text-green-600">18,247</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Coverage:</span>
              <span className="font-medium">73.3%</span>
            </div>
          </CardContent>
        </Card>

        {/* Apply Filters Button */}
        <Button className="w-full bg-green-600 hover:bg-green-700">Apply Filters</Button>
      </div>
    </div>
  )
}
