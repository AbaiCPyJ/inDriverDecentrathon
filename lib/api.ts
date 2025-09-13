// API client for inDrive Geotracks backend integration

export interface JobConfig {
  analysisType: "popular-routes" | "endpoints" | "trajectories" | "speed"
  dateRange: {
    start: string
    end: string
  }
  timeRange: {
    start: number
    end: number
  }
  filters: {
    city?: string
    minTrips?: number
    maxDistance?: number
    speedRange?: { min: number; max: number }
    roadType?: string
  }
  visualization: {
    showHeatmap?: boolean
    showClusters?: boolean
    intensity?: "low" | "medium" | "high"
  }
}

export interface Job {
  id: string
  status: "pending" | "running" | "completed" | "failed"
  config: JobConfig
  createdAt: string
  startedAt?: string
  completedAt?: string
  error?: string
  progress?: number
  results?: {
    mapUrl: string
    statistics: Record<string, any>
  }
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  message?: string
}

class GeotracksAPI {
  private baseUrl: string

  constructor() {
    this.baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
        },
        ...options,
      })

      const data = await response.json()

      if (!response.ok) {
        return {
          success: false,
          error: data.error || `HTTP ${response.status}`,
          message: data.message,
        }
      }

      return {
        success: true,
        data,
      }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : "Network error",
      }
    }
  }

  // Job Management
  async createJob(config: JobConfig): Promise<ApiResponse<Job>> {
    // Mock implementation for demo
    const mockJob: Job = {
      id: `job_${Date.now()}`,
      status: "pending",
      config,
      createdAt: new Date().toISOString(),
      progress: 0,
    }

    // Simulate API delay
    await new Promise((resolve) => setTimeout(resolve, 500))

    return {
      success: true,
      data: mockJob,
    }
  }

  async getJob(jobId: string): Promise<ApiResponse<Job>> {
    // Mock implementation for demo
    const mockJob: Job = {
      id: jobId,
      status: "completed",
      config: {
        analysisType: "popular-routes",
        dateRange: { start: "2024-01-01", end: "2024-01-31" },
        timeRange: { start: 6, end: 22 },
        filters: {},
        visualization: {},
      },
      createdAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
      progress: 100,
      results: {
        mapUrl: `/api/maps/${jobId}.html`,
        statistics: { totalTrips: 1247, coverage: 89 },
      },
    }

    return {
      success: true,
      data: mockJob,
    }
  }

  async listJobs(): Promise<ApiResponse<Job[]>> {
    // Mock implementation for demo
    return {
      success: true,
      data: [],
    }
  }

  async cancelJob(jobId: string): Promise<ApiResponse<void>> {
    return {
      success: true,
    }
  }

  async deleteJob(jobId: string): Promise<ApiResponse<void>> {
    return {
      success: true,
    }
  }

  // Map Files
  async getMapUrl(jobId: string): Promise<string> {
    return `${this.baseUrl}/api/maps/${jobId}.html`
  }

  async downloadMap(jobId: string): Promise<Blob | null> {
    try {
      const response = await fetch(`${this.baseUrl}/api/maps/${jobId}.html`)
      if (response.ok) {
        return await response.blob()
      }
      return null
    } catch {
      return null
    }
  }

  // Health Check
  async healthCheck(): Promise<ApiResponse<{ status: string; version: string }>> {
    return this.request<{ status: string; version: string }>("/api/health")
  }

  // Data Statistics
  async getDataStats(): Promise<
    ApiResponse<{
      totalTrips: number
      dateRange: { start: string; end: string }
      cities: string[]
      lastUpdated: string
    }>
  > {
    return this.request("/api/data/stats")
  }
}

export const api = new GeotracksAPI()
