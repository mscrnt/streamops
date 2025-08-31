import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useApi } from './useApi'
import toast from 'react-hot-toast'

export function useJobActions() {
  const { api } = useApi()
  const queryClient = useQueryClient()
  
  const pauseJob = useMutation({
    mutationFn: async (jobId) => {
      const response = await api.post(`/jobs/${jobId}/pause`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['jobs'])
      toast.success('Job paused')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to pause job')
    }
  })
  
  const resumeJob = useMutation({
    mutationFn: async (jobId) => {
      const response = await api.post(`/jobs/${jobId}/resume`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['jobs'])
      toast.success('Job resumed')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to resume job')
    }
  })
  
  const cancelJob = useMutation({
    mutationFn: async (jobId) => {
      const response = await api.post(`/jobs/${jobId}/cancel`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['jobs'])
      toast.success('Job cancelled')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to cancel job')
    }
  })
  
  const retryJob = useMutation({
    mutationFn: async (jobId) => {
      const response = await api.post(`/jobs/${jobId}/retry`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['jobs'])
      toast.success('Job retried')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to retry job')
    }
  })
  
  return {
    pauseJob,
    resumeJob,
    cancelJob,
    retryJob
  }
}