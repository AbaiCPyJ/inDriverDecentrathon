"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { X, Play, Square, Trash2, Download, Clock, CheckCircle, XCircle, Loader2 } from "lucide-react"
import type { Job } from "@/lib/api"
import { formatDistanceToNow } from "date-fns"

interface JobManagerProps {
  jobs: Job[]
  currentJobId: string | null
  onClose: () => void
  onSelectJob: (jobId: string) => void
  onCancelJob: (jobId: string) => Promise<boolean>
}

export function JobManager({ jobs, currentJobId, onClose, onSelectJob, onCancelJob }: JobManagerProps) {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(currentJobId)

  const getStatusIcon = (status: Job["status"]) => {
    switch (status) {
      case "pending":
        return <Clock className="h-4 w-4 text-yellow-500" />
      case "running":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />
    }
  }

  const getStatusColor = (status: Job["status"]) => {
    switch (status) {
      case "pending":
        return "bg-yellow-100 text-yellow-800"
      case "running":
        return "bg-blue-100 text-blue-800"
      case "completed":
        return "bg-green-100 text-green-800"
      case "failed":
        return "bg-red-100 text-red-800"
    }
  }

  const getAnalysisTypeLabel = (type: string) => {
    switch (type) {
      case "popular-routes":
        return "Popular Routes"
      case "endpoints":
        return "Endpoints"
      case "trajectories":
        return "Trajectories"
      case "speed":
        return "Speed Analysis"
      case "ghg":
        return "GHG Emissions"
      default:
        return type
    }
  }

  const selectedJob = jobs.find((job) => job.id === selectedJobId)

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <Card className="w-full max-w-4xl h-[80vh] flex flex-col">
        <CardHeader className="flex-shrink-0">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              Job Management
              <Badge variant="secondary">{jobs.length} jobs</Badge>
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="flex-1 flex gap-6 overflow-hidden">
          {/* Jobs List */}
          <div className="w-1/2 flex flex-col">
            <h3 className="font-medium mb-3">Recent Jobs</h3>
            <ScrollArea className="flex-1">
              <div className="space-y-2">
                {jobs.map((job) => (
                  <Card
                    key={job.id}
                    className={`cursor-pointer transition-colors ${
                      selectedJobId === job.id ? "ring-2 ring-green-500" : ""
                    } ${currentJobId === job.id ? "bg-green-50" : ""}`}
                    onClick={() => setSelectedJobId(job.id)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(job.status)}
                          <span className="font-medium text-sm">{getAnalysisTypeLabel(job.config.analysisType)}</span>
                          {currentJobId === job.id && (
                            <Badge variant="outline" className="text-xs">
                              Current
                            </Badge>
                          )}
                        </div>
                        <Badge className={`text-xs ${getStatusColor(job.status)}`}>{job.status}</Badge>
                      </div>

                      <div className="text-xs text-muted-foreground space-y-1">
                        <div>Created {formatDistanceToNow(new Date(job.createdAt))} ago</div>
                        {job.progress && (
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-muted rounded-full h-1">
                              <div
                                className="bg-green-600 h-1 rounded-full transition-all"
                                style={{ width: `${job.progress}%` }}
                              />
                            </div>
                            <span>{job.progress}%</span>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}

                {jobs.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground">
                    <p>No jobs found</p>
                    <p className="text-sm">Run an analysis to create your first job</p>
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>

          <Separator orientation="vertical" />

          {/* Job Details */}
          <div className="w-1/2 flex flex-col">
            {selectedJob ? (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-medium">Job Details</h3>
                  <div className="flex items-center gap-2">
                    {selectedJob.status === "running" && (
                      <Button variant="outline" size="sm" onClick={() => onCancelJob(selectedJob.id)} className="gap-1">
                        <Square className="h-3 w-3" />
                        Cancel
                      </Button>
                    )}

                    {selectedJob.status === "completed" && (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onSelectJob(selectedJob.id)}
                          className="gap-1"
                        >
                          <Play className="h-3 w-3" />
                          View
                        </Button>
                        <Button variant="outline" size="sm" className="gap-1 bg-transparent">
                          <Download className="h-3 w-3" />
                          Export
                        </Button>
                      </>
                    )}

                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1 text-red-600 hover:text-red-700 bg-transparent"
                    >
                      <Trash2 className="h-3 w-3" />
                      Delete
                    </Button>
                  </div>
                </div>

                <ScrollArea className="flex-1">
                  <div className="space-y-4">
                    {/* Status */}
                    <div>
                      <h4 className="text-sm font-medium mb-2">Status</h4>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(selectedJob.status)}
                        <Badge className={getStatusColor(selectedJob.status)}>{selectedJob.status}</Badge>
                        {selectedJob.progress && (
                          <span className="text-sm text-muted-foreground">{selectedJob.progress}% complete</span>
                        )}
                      </div>
                      {selectedJob.error && <p className="text-sm text-red-600 mt-1">{selectedJob.error}</p>}
                    </div>

                    <Separator />

                    {/* Configuration */}
                    <div>
                      <h4 className="text-sm font-medium mb-2">Configuration</h4>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Analysis Type:</span>
                          <span>{getAnalysisTypeLabel(selectedJob.config.analysisType)}</span>
                        </div>
                        {selectedJob.config.filters.city && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">City:</span>
                            <span>{selectedJob.config.filters.city}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <Separator />

                    {/* Timestamps */}
                    <div>
                      <h4 className="text-sm font-medium mb-2">Timeline</h4>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Created:</span>
                          <span>{new Date(selectedJob.createdAt).toLocaleString()}</span>
                        </div>
                        {selectedJob.startedAt && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Started:</span>
                            <span>{new Date(selectedJob.startedAt).toLocaleString()}</span>
                          </div>
                        )}
                        {selectedJob.completedAt && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Completed:</span>
                            <span>{new Date(selectedJob.completedAt).toLocaleString()}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Results */}
                    {selectedJob.results && (
                      <>
                        <Separator />
                        <div>
                          <h4 className="text-sm font-medium mb-2">Results</h4>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Map URL:</span>
                              <span className="text-green-600">Available</span>
                            </div>
                            {selectedJob.results.statistics && (
                              <div>
                                <span className="text-muted-foreground">Statistics:</span>
                                <div className="mt-2 space-y-2">
                                  {/* v2.0.0 Primary Stats */}
                                  {selectedJob.results.statistics.totalDistanceKm !== undefined && (
                                    <div className="flex justify-between text-xs">
                                      <span>Total Distance:</span>
                                      <span className="font-medium">{selectedJob.results.statistics.totalDistanceKm.toFixed(1)} km</span>
                                    </div>
                                  )}
                                  {selectedJob.results.statistics.totalEmissionsKgCO2e !== undefined && (
                                    <div className="flex justify-between text-xs">
                                      <span>Total Emissions:</span>
                                      <span className="font-medium">{selectedJob.results.statistics.totalEmissionsKgCO2e.toFixed(2)} kg CO₂e</span>
                                    </div>
                                  )}
                                  {selectedJob.results.statistics.emissionsPerVehicleKgCO2e !== undefined && (
                                    <div className="flex justify-between text-xs">
                                      <span>Emissions per Vehicle:</span>
                                      <span className="font-medium">{selectedJob.results.statistics.emissionsPerVehicleKgCO2e.toFixed(3)} kg CO₂e</span>
                                    </div>
                                  )}
                                  {selectedJob.results.statistics.speedPercentiles && (
                                    <div className="text-xs">
                                      <span>Speed Percentiles:</span>
                                      <div className="ml-2 mt-1 space-y-1">
                                        <div className="flex justify-between">
                                          <span>P50 (Median):</span>
                                          <span className="font-medium">{selectedJob.results.statistics.speedPercentiles.p50.toFixed(1)} km/h</span>
                                        </div>
                                        <div className="flex justify-between">
                                          <span>P95:</span>
                                          <span className="font-medium">{selectedJob.results.statistics.speedPercentiles.p95.toFixed(1)} km/h</span>
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                  {selectedJob.results.statistics.congestionAreas !== undefined && (
                                    <div className="flex justify-between text-xs">
                                      <span>Congestion Areas:</span>
                                      <span className="font-medium">{selectedJob.results.statistics.congestionAreas.toLocaleString()}</span>
                                    </div>
                                  )}

                                  {/* Legacy stats as fallback */}
                                  {(!selectedJob.results.statistics.totalDistanceKm && selectedJob.results.statistics.totalRecords) && (
                                    <div className="flex justify-between text-xs">
                                      <span>Records:</span>
                                      <span className="font-medium">{selectedJob.results.statistics.totalRecords.toLocaleString()}</span>
                                    </div>
                                  )}
                                  {(!selectedJob.results.statistics.speedPercentiles && selectedJob.results.statistics.avgSpeed) && (
                                    <div className="flex justify-between text-xs">
                                      <span>Avg Speed:</span>
                                      <span className="font-medium">{selectedJob.results.statistics.avgSpeed} km/h</span>
                                    </div>
                                  )}

                                  {/* Show full JSON for debugging if needed */}
                                  <details className="mt-2">
                                    <summary className="text-xs text-muted-foreground cursor-pointer">Raw Data</summary>
                                    <pre className="text-xs bg-muted p-2 rounded mt-1 overflow-auto">
                                      {JSON.stringify(selectedJob.results.statistics, null, 2)}
                                    </pre>
                                  </details>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </ScrollArea>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-muted-foreground">
                <p>Select a job to view details</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
