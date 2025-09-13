"use client"

import { useState, useEffect, useCallback } from "react"
import { api, type Job, type JobConfig } from "../lib/api"

// Hook for managing multiple jobs
export function useJobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchJobs = useCallback(async () => {
    setLoading(true)
    const response = await api.listJobs()

    if (response.success && response.data) {
      setJobs(response.data)
      setError(null)
    } else {
      setError(response.error || "Failed to fetch jobs")
    }

    setLoading(false)
  }, [])

  const createJob = useCallback(async (config: JobConfig): Promise<Job | null> => {
    const response = await api.createJob(config)

    if (response.success && response.data) {
      setJobs((prev) => [response.data!, ...prev])
      return response.data
    } else {
      setError(response.error || "Failed to create job")
      return null
    }
  }, [])

  const cancelJob = useCallback(async (jobId: string): Promise<boolean> => {
    const response = await api.cancelJob(jobId)

    if (response.success) {
      setJobs((prev) => prev.map((job) => (job.id === jobId ? { ...job, status: "failed" as const } : job)))
      return true
    } else {
      setError(response.error || "Failed to cancel job")
      return false
    }
  }, [])

  const deleteJob = useCallback(async (jobId: string): Promise<boolean> => {
    const response = await api.deleteJob(jobId)

    if (response.success) {
      setJobs((prev) => prev.filter((job) => job.id !== jobId))
      return true
    } else {
      setError(response.error || "Failed to delete job")
      return false
    }
  }, [])

  useEffect(() => {
    fetchJobs()
  }, [fetchJobs])

  return {
    jobs,
    loading,
    error,
    refetch: fetchJobs,
    createJob,
    cancelJob,
    deleteJob,
  }
}

// Hook for managing a single job
export function useJob(jobId: string | null) {
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchJob = useCallback(async () => {
    if (!jobId) return

    setLoading(true)
    const response = await api.getJob(jobId)

    if (response.success && response.data) {
      setJob(response.data)
      setError(null)
    } else {
      setError(response.error || "Failed to fetch job")
    }

    setLoading(false)
  }, [jobId])

  useEffect(() => {
    fetchJob()
  }, [fetchJob])

  return {
    job,
    loading,
    error,
    refetch: fetchJob,
  }
}

// Hook for polling job status
export function useJobPolling(jobId: string | null, interval = 2000) {
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!jobId) return

    const pollJob = async () => {
      const response = await api.getJob(jobId)

      if (response.success && response.data) {
        setJob(response.data)
        setError(null)

        // Stop polling if job is completed or failed
        if (response.data.status === "completed" || response.data.status === "failed") {
          return true // Signal to stop polling
        }
      } else {
        setError(response.error || "Failed to fetch job status")
        return true // Stop polling on error
      }

      return false // Continue polling
    }

    // Initial fetch
    pollJob()

    // Set up polling interval
    const intervalId = setInterval(async () => {
      const shouldStop = await pollJob()
      if (shouldStop) {
        clearInterval(intervalId)
      }
    }, interval)

    return () => clearInterval(intervalId)
  }, [jobId, interval])

  return { job, error }
}
