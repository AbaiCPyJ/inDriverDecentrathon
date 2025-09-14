"use client"

import { useState, useEffect, useCallback } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Sidebar } from "@/components/sidebar"
import { MapVisualization } from "@/components/map-visualization"
import { JobStatus } from "@/components/job-status"
import { JobManager } from "@/components/job-manager"
import { Play, Square, RotateCcw, History, Loader2 } from "lucide-react"
import { useJobs, useJobPolling } from "@/lib/hooks/use-api"
import { api, type JobConfig, type Job } from "@/lib/api"

// Define the analysis types with consistent ordering
const ANALYSIS_TYPES: Array<{ 
  id: JobConfig["analysisType"], 
  label: string 
}> = [
  { id: "popular-routes", label: "Popular Routes" },
  { id: "endpoints", label: "Endpoints" },
  { id: "trajectories", label: "Trajectories" },
  { id: "speed", label: "Speed Analysis" },
  { id: "ghg", label: "GHG Emissions" },
]

export function DashboardLayout() {
  const [activeTab, setActiveTab] = useState<JobConfig["analysisType"]>("popular-routes")
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [showJobManager, setShowJobManager] = useState(false)
  const [isRunningBatch, setIsRunningBatch] = useState(false)
  
  // Track jobs per analysis type
  const [jobsByType, setJobsByType] = useState<Record<JobConfig["analysisType"], Job | null>>({
    "popular-routes": null,
    "endpoints": null,
    "trajectories": null,
    "speed": null,
    "ghg": null,
  })

  // Track map URL cache with timestamps for cache busting
  const [mapCache, setMapCache] = useState<Record<string, { url: string, timestamp: number }>>({})

  const { jobs, loading: jobsLoading, refetch: refetchJobs } = useJobs()

  // Update jobsByType when jobs change
  useEffect(() => {
    const newJobsByType = { ...jobsByType }
    
    // Find the latest job for each analysis type
    ANALYSIS_TYPES.forEach(({ id }) => {
      const typeJobs = jobs.filter(job => job.config.analysisType === id)
      if (typeJobs.length > 0) {
        // Get the most recent job
        const latestJob = typeJobs.sort((a, b) => 
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        )[0]
        newJobsByType[id] = latestJob
      }
    })
    
    setJobsByType(newJobsByType)
  }, [jobs])

  // Update map cache when jobs complete
  useEffect(() => {
    const newCache = { ...mapCache }
    let cacheUpdated = false

    Object.entries(jobsByType).forEach(([type, job]) => {
      if (job?.status === "completed" && job.results?.mapUrl) {
        const cacheKey = `${type}-${job.id}`
        if (!newCache[cacheKey]) {
          newCache[cacheKey] = {
            url: `${job.results.mapUrl}?ts=${Date.now()}`,
            timestamp: Date.now()
          }
          cacheUpdated = true
        }
      }
    })

    if (cacheUpdated) {
      setMapCache(newCache)
    }
  }, [jobsByType])

  // Poll for updates on running jobs
  const runningJobs = Object.values(jobsByType).filter(job => 
    job && (job.status === "pending" || job.status === "running")
  )

  useEffect(() => {
    if (runningJobs.length === 0) return

    const pollInterval = setInterval(async () => {
      await refetchJobs()
    }, 2000)

    return () => clearInterval(pollInterval)
  }, [runningJobs.length, refetchJobs])

  const handleRunAnalysis = async () => {
    // Get uploaded file
    const uploadedFile = (window as any).uploadedCsvFile
    if (!uploadedFile) {
      alert("Please upload a CSV file first")
      return
    }

    setIsRunningBatch(true)
    
    try {
      // Create all analysis jobs in parallel
      const response = await api.createBatchJobs(
        uploadedFile,
        ANALYSIS_TYPES.map(t => t.id),
        {
          city: "all",
          minTrips: 10,
          maxDistance: 50,
        },
        {
          showHeatmap: true,
          showClusters: false,
          intensity: "medium",
        }
      )

      if (response.success && response.data) {
        // Refresh jobs to get the new batch
        await refetchJobs()
      } else {
        alert(`Failed to create batch jobs: ${response.error}`)
      }
    } catch (error) {
      alert(`Error creating batch jobs: ${error}`)
    } finally {
      setIsRunningBatch(false)
    }
  }

  const handleCancelAllJobs = async () => {
    const runningJobIds = Object.values(jobsByType)
      .filter(job => job && (job.status === "pending" || job.status === "running"))
      .map(job => job!.id)

    if (runningJobIds.length === 0) return

    try {
      await Promise.all(runningJobIds.map(id => api.cancelJob(id)))
      await refetchJobs()
    } catch (error) {
      console.error("Error cancelling jobs:", error)
    }
  }

  const handleReset = () => {
    setJobsByType({
      "popular-routes": null,
      "endpoints": null,
      "trajectories": null,
      "speed": null,
      "ghg": null,
    })
    setMapCache({})
  }

  const getTabStatus = (type: JobConfig["analysisType"]) => {
    const job = jobsByType[type]
    if (!job) return "idle"
    if (job.status === "pending" || job.status === "running") return "running"
    if (job.status === "completed") return "completed"
    return "error"
  }

  const getTabProgress = (type: JobConfig["analysisType"]) => {
    const job = jobsByType[type]
    return job?.progress || 0
  }

  const getMapJob = (type: JobConfig["analysisType"]) => {
    return jobsByType[type]
  }

  const anyJobsRunning = Object.values(jobsByType).some(job => 
    job && (job.status === "pending" || job.status === "running")
  )

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="flex h-16 items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded bg-green-600 flex items-center justify-center">
                <span className="text-white font-bold text-sm">iD</span>
              </div>
              <h1 className="text-xl font-semibold">inDrive Geotracks Dashboard</h1>
            </div>
            <Badge variant="secondary" className="bg-green-50 text-green-700 border-green-200">
              Beta
            </Badge>
          </div>

          <div className="flex items-center gap-2">
            {anyJobsRunning ? (
              <Badge variant="secondary" className="gap-1">
                <Loader2 className="h-3 w-3 animate-spin" />
                Processing ({runningJobs.length} jobs)
              </Badge>
            ) : (
              <Badge variant="outline">Ready</Badge>
            )}

            <Button variant="outline" size="sm" onClick={() => setShowJobManager(!showJobManager)} className="gap-2">
              <History className="h-4 w-4" />
              Jobs ({jobs.length})
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={anyJobsRunning ? handleCancelAllJobs : handleRunAnalysis}
              disabled={jobsLoading || isRunningBatch}
              className="gap-2 bg-transparent"
            >
              {isRunningBatch ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Starting...
                </>
              ) : anyJobsRunning ? (
                <>
                  <Square className="h-4 w-4" />
                  Stop All
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Run Analysis
                </>
              )}
            </Button>
            <Button variant="ghost" size="sm" onClick={handleReset} className="gap-2">
              <RotateCcw className="h-4 w-4" />
              Reset
            </Button>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <Sidebar collapsed={sidebarCollapsed} onCollapsedChange={setSidebarCollapsed} activeTab={activeTab} />

        {/* Job Manager Overlay */}
        {showJobManager && (
          <JobManager
            jobs={jobs}
            currentJobId={null}
            onClose={() => setShowJobManager(false)}
            onSelectJob={() => {}}
            onCancelJob={async (jobId) => {
              try {
                await api.cancelJob(jobId)
                await refetchJobs()
                return true
              } catch {
                return false
              }
            }}
          />
        )}

        {/* Main Content */}
        <main className={`flex-1 transition-all duration-300 ${sidebarCollapsed ? "ml-16" : "ml-80"}`}>
          <div className="p-6">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
              <TabsList className="grid w-full grid-cols-5 bg-muted/50">
                {ANALYSIS_TYPES.map(({ id, label }) => {
                  const status = getTabStatus(id)
                  const progress = getTabProgress(id)
                  
                  return (
                    <TabsTrigger
                      key={id}
                      value={id}
                      className="data-[state=active]:bg-green-600 data-[state=active]:text-white relative"
                    >
                      <div className="flex items-center gap-2">
                        <span>{label}</span>
                        {status === "running" && (
                          <div className="flex items-center gap-1">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            <span className="text-xs">({progress}%)</span>
                          </div>
                        )}
                        {status === "completed" && (
                          <div className="h-2 w-2 bg-green-400 rounded-full" />
                        )}
                        {status === "error" && (
                          <div className="h-2 w-2 bg-red-400 rounded-full" />
                        )}
                      </div>
                    </TabsTrigger>
                  )
                })}
              </TabsList>

              {ANALYSIS_TYPES.map(({ id, label }) => (
                <TabsContent key={id} value={id} className="space-y-4">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        {label}
                        <Badge variant="outline" className="text-xs">
                          {getTabStatus(id) === "completed" ? "Updated" : 
                           getTabStatus(id) === "running" ? `Processing ${getTabProgress(id)}%` :
                           getTabStatus(id) === "error" ? "Error" : "Pending"}
                        </Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <MapVisualization 
                        type={id} 
                        status={getTabStatus(id)} 
                        job={getMapJob(id)} 
                      />
                    </CardContent>
                  </Card>
                </TabsContent>
              ))}
            </Tabs>
          </div>
        </main>
      </div>
    </div>
  )
}
