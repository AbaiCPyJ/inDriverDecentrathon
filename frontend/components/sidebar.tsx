"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { ChevronLeft, ChevronRight, Upload, Filter, CheckCircle, AlertCircle } from "lucide-react"

interface SidebarProps {
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
  activeTab: string
}

export function Sidebar({ collapsed, onCollapsedChange, activeTab }: SidebarProps) {
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [uploadStatus, setUploadStatus] = useState<"idle" | "uploading" | "success" | "error">("idle")
  const [fileStats, setFileStats] = useState<{ totalRecords: number; uniqueIds: number } | null>(null)
  const [maxProcessRows, setMaxProcessRows] = useState<number>(50000)

  // Store uploaded file and settings globally for job creation
  useEffect(() => {
    if (csvFile && uploadStatus === "success") {
      console.log('Storing file in window:', csvFile.name, 'with max rows:', maxProcessRows)
      // Store in window object for access by dashboard
      ;(window as any).uploadedCsvFile = csvFile
      ;(window as any).maxProcessRows = maxProcessRows
    }
  }, [csvFile, uploadStatus, maxProcessRows])

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (!file.name.endsWith(".csv")) {
      setUploadStatus("error")
      return
    }

    setCsvFile(file)
    setUploadStatus("uploading")

    try {
      // Parse CSV to get basic stats
      const text = await file.text()
      const lines = text.split("\n").filter((line) => line.trim())
      const records = lines.length - 1 // Subtract header
      const uniqueIds = new Set(lines.slice(1).map((line) => line.split(",")[0])).size

      setFileStats({ totalRecords: records, uniqueIds })
      setUploadStatus("success")

      console.log("[v0] CSV uploaded successfully, triggering immediate processing")
      // Here you would trigger the actual processing/analysis
    } catch (error) {
      setUploadStatus("error")
      setFileStats(null)
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
            <Upload className="h-4 w-4" />
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
            Upload & Process
          </h2>
          <Button variant="ghost" size="sm" onClick={() => onCollapsedChange(true)} className="p-2">
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Upload className="h-4 w-4" />
              Upload Geodata CSV
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <Label className="text-xs">CSV File (randomized_id, lat, lng, alt, spd, azm)</Label>
              <Input
                type="file"
                accept=".csv"
                onChange={handleFileUpload}
                className="file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-xs file:bg-green-50 file:text-green-700 hover:file:bg-green-100"
              />
            </div>

            {uploadStatus === "uploading" && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-green-600"></div>
                Processing file...
              </div>
            )}

            {uploadStatus === "success" && csvFile && fileStats && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm text-green-600">
                  <CheckCircle className="h-4 w-4" />
                  {csvFile.name} - Processing started automatically
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <Badge variant="secondary">{fileStats.totalRecords.toLocaleString()} records</Badge>
                  <Badge variant="secondary">{fileStats.uniqueIds.toLocaleString()} unique IDs</Badge>
                </div>
              </div>
            )}

            {uploadStatus === "error" && (
              <div className="flex items-center gap-2 text-sm text-red-600">
                <AlertCircle className="h-4 w-4" />
                Invalid CSV file
              </div>
            )}
          </CardContent>
        </Card>

        {/* Processing Settings */}
        {uploadStatus === "success" && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Processing Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label className="text-xs">Max Records to Process</Label>
                <Input
                  type="number"
                  value={maxProcessRows}
                  onChange={(e) => setMaxProcessRows(Number(e.target.value) || 50000)}
                  min={1000}
                  max={500000}
                  step={1000}
                  className="text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  Higher values = better accuracy, longer processing time. 
                  {fileStats && fileStats.totalRecords > maxProcessRows && (
                    <span className="text-orange-600">
                      {" "}Data will be sampled from {fileStats.totalRecords.toLocaleString()} total records.
                    </span>
                  )}
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {uploadStatus === "idle" && (
          <div className="text-center py-8 text-muted-foreground">
            <Upload className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p className="text-sm">Upload a CSV file to start processing geodata</p>
          </div>
        )}
      </div>
    </div>
  )
}
