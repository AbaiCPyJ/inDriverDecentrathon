// API client for inDrive Geotracks backend integration

export interface JobConfig {
  analysisType: "popular-routes" | "endpoints" | "trajectories" | "speed" | "ghg"
  csvFile?: File
  maxProcessRows?: number
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

export interface JobStatistics {
  // v2.0.0 new fields - strongly typed
  totalDistanceKm?: number
  totalEmissionsKgCO2e?: number
  emissionsPerVehicleKgCO2e?: number
  speedPercentiles?: {
    p25: number
    p50: number
    p75: number
    p95: number
  }
  congestionAreas?: number
  
  // Legacy fields (still supported)
  totalRecords?: number
  uniqueVehicles?: number
  avgSpeed?: number
  maxSpeed?: number
  note?: string
  
  // Any other fields
  [key: string]: any
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
    statistics: JobStatistics
  }
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  message?: string
}

export interface GeodataRecord {
  randomized_id: string
  lat: number
  lng: number
  alt: number
  spd: number
  azm: number
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

  async createJob(config: JobConfig): Promise<ApiResponse<Job>> {
    if (!config.csvFile) {
      return {
        success: false,
        error: "CSV file is required",
      }
    }

    const formData = new FormData()
    formData.append("csvFile", config.csvFile)
    formData.append("analysisType", config.analysisType)
    formData.append("filters", JSON.stringify(config.filters))
    formData.append("visualization", JSON.stringify(config.visualization))
    if (config.maxProcessRows) {
      formData.append("maxProcessRows", config.maxProcessRows.toString())
    }

    const response = await fetch(`${this.baseUrl}/api/jobs`, {
      method: "POST",
      body: formData,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      return {
        success: false,
        error: errorData.detail || `HTTP ${response.status}`,
      }
    }

    const data = await response.json()
    return {
      success: true,
      data,
    }
  }

  async createBatchJobs(csvFile: File, analysisTypes: JobConfig["analysisType"][], filters: JobConfig["filters"], visualization: JobConfig["visualization"], maxProcessRows?: number): Promise<ApiResponse<Job[]>> {
    if (!csvFile) {
      return {
        success: false,
        error: "CSV file is required",
      }
    }

    try {
      const jobs: Job[] = []
      const errors: string[] = []

      // Create all jobs in parallel
      const promises = analysisTypes.map(analysisType => 
        this.createJob({
          analysisType,
          csvFile,
          filters,
          visualization,
          maxProcessRows
        })
      )

      const results = await Promise.allSettled(promises)
      
      results.forEach((result, index) => {
        if (result.status === 'fulfilled' && result.value.success && result.value.data) {
          jobs.push(result.value.data)
        } else {
          const error = result.status === 'fulfilled' ? result.value.error : result.reason
          errors.push(`${analysisTypes[index]}: ${error}`)
        }
      })

      if (jobs.length === 0) {
        return {
          success: false,
          error: `All jobs failed: ${errors.join(', ')}`
        }
      }

      return {
        success: true,
        data: jobs
      }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : "Batch job creation failed"
      }
    }
  }

  async validateCSV(file: File): Promise<
    ApiResponse<{
      isValid: boolean
      recordCount: number
      uniqueIds: number
      errors?: string[]
    }>
  > {
    try {
      const text = await file.text()
      const lines = text.split("\n").filter((line) => line.trim())

      if (lines.length < 2) {
        return {
          success: false,
          error: "CSV file must contain at least a header and one data row",
        }
      }

      const header = lines[0].toLowerCase()
      const expectedColumns = ["randomized_id", "lat", "lng", "alt", "spd", "azm"]
      const hasAllColumns = expectedColumns.every((col) => header.includes(col))

      if (!hasAllColumns) {
        return {
          success: false,
          error: `CSV must contain columns: ${expectedColumns.join(", ")}`,
        }
      }

      const records = lines.slice(1)
      const uniqueIds = new Set(records.map((line) => line.split(",")[0])).size

      return {
        success: true,
        data: {
          isValid: true,
          recordCount: records.length,
          uniqueIds,
        },
      }
    } catch (error) {
      return {
        success: false,
        error: "Failed to parse CSV file",
      }
    }
  }

  async getJob(jobId: string): Promise<ApiResponse<Job>> {
    return this.request<Job>(`/api/jobs/${jobId}`)
  }

  async listJobs(): Promise<ApiResponse<Job[]>> {
    return this.request<Job[]>("/api/jobs")
  }

  async cancelJob(jobId: string): Promise<ApiResponse<void>> {
    return this.request<void>(`/api/jobs/${jobId}`, {
      method: "DELETE",
    })
  }

  async deleteJob(jobId: string): Promise<ApiResponse<void>> {
    return this.request<void>(`/api/jobs/${jobId}`, {
      method: "DELETE",
    })
  }

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

  async healthCheck(): Promise<ApiResponse<{ status: string; version: string }>> {
    return this.request<{ status: string; version: string }>("/api/health")
  }

  async getDataStats(): Promise<
    ApiResponse<{
      totalRecords: number
      uniqueIds: number
      fileSize: number
      lastUpdated: string
    }>
  > {
    return this.request("/api/data/stats")
  }
}

export const api = new GeotracksAPI()
