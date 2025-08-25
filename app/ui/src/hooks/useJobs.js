import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useStore, useJobStore } from '@/store/useStore'
import { useApi } from './useApi'
import toast from 'react-hot-toast'

// Jobs listing hook
export const useJobs = (params = {}) => {
  const { jobFilters } = useStore()
  const { api } = useApi()

  // Merge filters with params
  const queryParams = {
    ...jobFilters,
    ...params,
  }

  return useQuery({
    queryKey: ['jobs', queryParams],
    queryFn: async () => {
      const response = await api.get('/jobs', { params: queryParams })
      return response.data
    },
    refetchInterval: 5000, // Refetch every 5 seconds for real-time updates
    staleTime: 1000, // Consider data stale after 1 second
  })
}

// Single job hook
export const useJob = (jobId) => {
  const { api } = useApi()

  return useQuery({
    queryKey: ['jobs', jobId],
    queryFn: async () => {
      const response = await api.get(`/jobs/${jobId}`)
      return response.data
    },
    enabled: !!jobId,
    refetchInterval: 2000, // Refetch every 2 seconds for active jobs
  })
}

// Job creation hook
export const useCreateJob = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async (jobData) => {
      const response = await api.post('/jobs', jobData)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      toast.success(`${data.type} job created successfully`)
    },
    onError: (error) => {
      console.error('Job creation failed:', error)
    }
  })
}

// Job cancellation hook
export const useCancelJob = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async (jobId) => {
      const response = await api.post(`/jobs/${jobId}/cancel`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      toast.success('Job cancelled successfully')
    },
    onError: (error) => {
      console.error('Job cancellation failed:', error)
    }
  })
}

// Job retry hook
export const useRetryJob = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async (jobId) => {
      const response = await api.post(`/jobs/${jobId}/retry`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      toast.success('Job retried successfully')
    },
    onError: (error) => {
      console.error('Job retry failed:', error)
    }
  })
}

// Bulk job operations
export const useBulkJobOperation = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async ({ operation, jobIds }) => {
      const response = await api.post('/jobs/bulk', {
        operation,
        job_ids: jobIds
      })
      return response.data
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      const { operation, jobIds } = variables
      toast.success(`${operation} operation completed for ${jobIds.length} jobs`)
    },
    onError: (error) => {
      console.error('Bulk job operation failed:', error)
    }
  })
}

// Job queue management hooks
export const usePauseQueue = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async () => {
      const response = await api.post('/jobs/queue/pause')
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      toast.success('Job queue paused')
    }
  })
}

export const useResumeQueue = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async () => {
      const response = await api.post('/jobs/queue/resume')
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      toast.success('Job queue resumed')
    }
  })
}

export const useClearQueue = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async () => {
      const response = await api.post('/jobs/queue/clear')
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      toast.success('Job queue cleared')
    }
  })
}

// Job statistics hook
export const useJobStats = (timeRange = '24h') => {
  const { api } = useApi()

  return useQuery({
    queryKey: ['jobs', 'stats', timeRange],
    queryFn: async () => {
      const response = await api.get('/jobs/stats', {
        params: { time_range: timeRange }
      })
      return response.data
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  })
}

// Active jobs hook (running/pending)
export const useActiveJobs = () => {
  const { jobs } = useJobStore()
  const { api } = useApi()

  return useQuery({
    queryKey: ['jobs', 'active'],
    queryFn: async () => {
      const response = await api.get('/jobs/active')
      return response.data
    },
    refetchInterval: 2000, // Refetch every 2 seconds
    initialData: jobs.filter(job => 
      job.status === 'running' || job.status === 'pending'
    ),
  })
}

// Job history hook
export const useJobHistory = (limit = 50) => {
  const { api } = useApi()

  return useQuery({
    queryKey: ['jobs', 'history', limit],
    queryFn: async () => {
      const response = await api.get('/jobs/history', {
        params: { limit }
      })
      return response.data
    },
  })
}

// Job logs hook
export const useJobLogs = (jobId) => {
  const { api } = useApi()

  return useQuery({
    queryKey: ['jobs', jobId, 'logs'],
    queryFn: async () => {
      const response = await api.get(`/jobs/${jobId}/logs`)
      return response.data
    },
    enabled: !!jobId,
    refetchInterval: (data) => {
      // If job is still running, refetch logs every 2 seconds
      return data?.some(log => log.level === 'info' && log.message.includes('running')) ? 2000 : false
    },
  })
}

// Custom hook for job type-specific operations
export const useJobTypeOperations = () => {
  const { api } = useApi()
  const queryClient = useQueryClient()

  // Create remux job
  const createRemuxJob = useMutation({
    mutationFn: async ({ assetId, outputFormat = 'mov' }) => {
      const response = await api.post('/jobs', {
        type: 'remux',
        asset_id: assetId,
        parameters: { output_format: outputFormat }
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      toast.success('Remux job created')
    }
  })

  // Create proxy job
  const createProxyJob = useMutation({
    mutationFn: async ({ assetId, resolution = '1080p' }) => {
      const response = await api.post('/jobs', {
        type: 'proxy',
        asset_id: assetId,
        parameters: { resolution }
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      toast.success('Proxy job created')
    }
  })

  // Create thumbnail job
  const createThumbnailJob = useMutation({
    mutationFn: async ({ assetId }) => {
      const response = await api.post('/jobs', {
        type: 'thumbnail',
        asset_id: assetId,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      toast.success('Thumbnail job created')
    }
  })

  // Create transcode job
  const createTranscodeJob = useMutation({
    mutationFn: async ({ assetId, preset }) => {
      const response = await api.post('/jobs', {
        type: 'transcode',
        asset_id: assetId,
        parameters: { preset }
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      toast.success('Transcode job created')
    }
  })

  return {
    createRemuxJob,
    createProxyJob,
    createThumbnailJob,
    createTranscodeJob,
  }
}

export default useJobs