import type { Session } from '@supabase/supabase-js'
import { apiRequest } from '../../lib/api'

export type MonitoredFile = {
  id: string
  original_file_name: string | null
  file_type: string | null
  mime_type: string | null
  file_size_bytes: number | null
  status: string
  extraction_mode: string | null
  error_code: string | null
  error_message: string | null
}

export type MonitoredImport = {
  id: string
  status: string
  created_at: string
  processed_at: string | null
  processing_duration_ms: number | null
  file_type: string | null
  original_file_name: string | null
  file_size_bytes: number | null
  file_count: number
  error_code: string | null
  error_message: string | null
  patient: { id: string; name: string | null } | null
  files: MonitoredFile[]
  ai_usage_count: number
}

export type FileMonitoringData = {
  period_days: number
  scope: 'admin' | 'nutritionist'
  summary: {
    imports: number
    files: number
    processed: number
    failed: number
    average_processing_ms: number | null
    measured_processing_count: number
    ai_usage_count: number
    file_access_count: number
  }
  daily: Array<{ date: string; files: number; failed: number; ai_uses: number }>
  recurring_errors: Array<{ code: string; message: string; count: number }>
  slow_imports: MonitoredImport[]
  imports: MonitoredImport[]
}

export function getFileMonitoring(session: Session | null, days: number) {
  return apiRequest<FileMonitoringData>(`/api/files/monitoring?days=${days}&limit=60`, session)
}
