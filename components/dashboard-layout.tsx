"use client"

import { useState, useEffect } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Sidebar } from "@/components/sidebar"
import { MapVisualization } from "@/components/map-visualization"
import { JobStatus } from "@/components/job-status"
import { JobManager } from "@/components/job-manager"
import { Play, Square, RotateCcw, History } from "lucide-react"
import { useJobs } from "@/lib/hooks/use-api"
import type { JobConfig } from "@/lib/api"

export function DashboardLayout() {
  const [activeTab, setActiveTab] = useState("popular-routes")
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<"idle" | "running" | "completed" | "error">("idle")
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [showJobManager, setShowJobManager] = useState(false)

  const { jobs, createJob, cancelJob, loading: jobsLoading } = useJobs()

  useEffect(() => {
    if (currentJobId) {
      const currentJob = jobs.find((job) => job.id === currentJobId)
      if (currentJob) {
        switch (currentJob.status) {
          case "pending":
          case "running":
            setJobStatus("running")
            break
          case "completed":
            setJobStatus("completed")
            break
          case "failed":
            setJobStatus("error")
            break
        }
      }
    }
  }, [jobs, currentJobId])

  const handleRunAnalysis = async () => {
    if (jobStatus === "running" && currentJobId) {
      // Cancel current job
      const success = await cancelJob(currentJobId)
      if (success) {
        setJobStatus("idle")
        setCurrentJobId(null)
      }
      return
    }

    // Create new job
    const jobConfig: JobConfig = {
      analysisType: activeTab as any,
      dateRange: {
        start: "2024-01-01",
        end: "2024-01-31",
      },
      timeRange: {
        start: 6,
        end: 22,
      },
      filters: {
        city: "all",
        minTrips: 10,
        maxDistance: 50,
      },
      visualization: {
        showHeatmap: true,
        showClusters: false,
        intensity: "medium",
      },
    }

    const newJob = await createJob(jobConfig)
    if (newJob) {
      setCurrentJobId(newJob.id)
      setJobStatus("running")
    }
  }

  const handleReset = () => {
    setJobStatus("idle")
    setCurrentJobId(null)
  }

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
            <JobStatus status={jobStatus} />

            <Button variant="outline" size="sm" onClick={() => setShowJobManager(!showJobManager)} className="gap-2">
              <History className="h-4 w-4" />
              Jobs ({jobs.length})
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleRunAnalysis}
              disabled={jobsLoading}
              className="gap-2 bg-transparent"
            >
              {jobStatus === "running" ? (
                <>
                  <Square className="h-4 w-4" />
                  Stop
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
            currentJobId={currentJobId}
            onClose={() => setShowJobManager(false)}
            onSelectJob={setCurrentJobId}
            onCancelJob={cancelJob}
          />
        )}

        {/* Main Content */}
        <main className={`flex-1 transition-all duration-300 ${sidebarCollapsed ? "ml-16" : "ml-80"}`}>
          <div className="p-6">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
              <TabsList className="grid w-full grid-cols-4 bg-muted/50">
                <TabsTrigger
                  value="popular-routes"
                  className="data-[state=active]:bg-green-600 data-[state=active]:text-white"
                >
                  Popular Routes
                </TabsTrigger>
                <TabsTrigger
                  value="endpoints"
                  className="data-[state=active]:bg-green-600 data-[state=active]:text-white"
                >
                  Endpoints
                </TabsTrigger>
                <TabsTrigger
                  value="trajectories"
                  className="data-[state=active]:bg-green-600 data-[state=active]:text-white"
                >
                  Trajectories
                </TabsTrigger>
                <TabsTrigger value="speed" className="data-[state=active]:bg-green-600 data-[state=active]:text-white">
                  Speed Analysis
                </TabsTrigger>
              </TabsList>

              <TabsContent value="popular-routes" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      Popular Routes Analysis
                      <Badge variant="outline" className="text-xs">
                        {jobStatus === "completed" ? "Updated" : "Pending"}
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <MapVisualization type="popular-routes" status={jobStatus} jobId={currentJobId} />
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="endpoints" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      Trip Endpoints Heatmap
                      <Badge variant="outline" className="text-xs">
                        {jobStatus === "completed" ? "Updated" : "Pending"}
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <MapVisualization type="endpoints" status={jobStatus} jobId={currentJobId} />
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="trajectories" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      Trip Trajectories
                      <Badge variant="outline" className="text-xs">
                        {jobStatus === "completed" ? "Updated" : "Pending"}
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <MapVisualization type="trajectories" status={jobStatus} jobId={currentJobId} />
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="speed" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      Speed Analysis
                      <Badge variant="outline" className="text-xs">
                        {jobStatus === "completed" ? "Updated" : "Pending"}
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <MapVisualization type="speed" status={jobStatus} jobId={currentJobId} />
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        </main>
      </div>
    </div>
  )
}
