import { useQuery } from '@tanstack/react-query'
import { useApi } from './useApi'

// Main system summary hook (used by TopbarMetrics)
export const useSystem = () => {
  const { api } = useApi()
  
  return useQuery({
    queryKey: ['system', 'summary'],
    queryFn: async () => {
      const response = await api.get('/system/summary')
      return response.data
    },
    refetchInterval: 5000,
    staleTime: 2000
  })
}

// Get system stats
export const useSystemStats = (refetchInterval = 5000) => {
  const { api } = useApi()
  
  return useQuery({
    queryKey: ['system', 'stats'],
    queryFn: async () => {
      const response = await api.get('/system/stats')
      return response.data
    },
    refetchInterval, // Auto-refresh every 5 seconds by default
    staleTime: 2000, // Consider data stale after 2 seconds
  })
}

// Get system health
export const useSystemHealth = () => {
  const { api } = useApi()
  
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: async () => {
      const response = await api.get('/system/health')
      return response.data
    },
    refetchInterval: 10000, // Check health every 10 seconds
  })
}

// Get system metrics over time
export const useSystemMetrics = (period = '1h') => {
  const { api } = useApi()
  
  return useQuery({
    queryKey: ['system', 'metrics', period],
    queryFn: async () => {
      const response = await api.get('/system/metrics', {
        params: { period }
      })
      return response.data
    },
    refetchInterval: 30000, // Update every 30 seconds
  })
}

// Get running processes
export const useSystemProcesses = () => {
  const { api } = useApi()
  
  return useQuery({
    queryKey: ['system', 'processes'],
    queryFn: async () => {
      const response = await api.get('/system/processes')
      return response.data
    },
    refetchInterval: 10000,
  })
}

// Get resource usage
export const useResourceUsage = (resource = 'all') => {
  const { api } = useApi()
  
  return useQuery({
    queryKey: ['system', 'resources', resource],
    queryFn: async () => {
      const response = await api.get('/system/resource-usage', {
        params: { resource }
      })
      return response.data
    },
    refetchInterval: 5000,
  })
}