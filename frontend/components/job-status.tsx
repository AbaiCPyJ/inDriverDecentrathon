import { Badge } from "@/components/ui/badge"
import { Loader2, CheckCircle, XCircle, Clock } from "lucide-react"

interface JobStatusProps {
  status: "idle" | "running" | "completed" | "error"
}

export function JobStatus({ status }: JobStatusProps) {
  const statusConfig = {
    idle: {
      icon: Clock,
      label: "Ready",
      variant: "secondary" as const,
      className: "bg-gray-100 text-gray-700",
    },
    running: {
      icon: Loader2,
      label: "Processing...",
      variant: "default" as const,
      className: "bg-blue-100 text-blue-700 animate-pulse",
    },
    completed: {
      icon: CheckCircle,
      label: "Completed",
      variant: "default" as const,
      className: "bg-green-100 text-green-700",
    },
    error: {
      icon: XCircle,
      label: "Error",
      variant: "destructive" as const,
      className: "bg-red-100 text-red-700",
    },
  }

  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <Badge variant={config.variant} className={`gap-1 ${config.className}`}>
      <Icon className={`h-3 w-3 ${status === "running" ? "animate-spin" : ""}`} />
      {config.label}
    </Badge>
  )
}
