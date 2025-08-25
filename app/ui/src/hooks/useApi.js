import axios from 'axios'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useStore } from '@/store/useStore'
import toast from 'react-hot-toast'

// Create axios instance with base configuration
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add any auth headers here if needed
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    const { setOnlineStatus } = useStore.getState()
    
    // Handle network errors
    if (!error.response) {
      setOnlineStatus(false)
      toast.error('Network error - check your connection')
      return Promise.reject(error)
    }
    
    // Handle HTTP errors
    const status = error.response.status
    const message = error.response.data?.message || error.response.data?.detail || 'An error occurred'
    
    if (status === 401) {
      toast.error('Unauthorized access')
    } else if (status === 403) {
      toast.error('Forbidden - insufficient permissions')
    } else if (status === 404) {
      toast.error('Resource not found')
    } else if (status >= 500) {
      toast.error('Server error - please try again later')
    } else if (status >= 400) {
      toast.error(message)
    }
    
    return Promise.reject(error)
  }
)

// Generic API hook
export const useApi = () => {
  return {
    api,
    
    // Generic GET request
    get: (url, config = {}) => api.get(url, config),
    
    // Generic POST request
    post: (url, data = {}, config = {}) => api.post(url, data, config),
    
    // Generic PUT request
    put: (url, data = {}, config = {}) => api.put(url, data, config),
    
    // Generic PATCH request
    patch: (url, data = {}, config = {}) => api.patch(url, data, config),
    
    // Generic DELETE request
    delete: (url, config = {}) => api.delete(url, config),
  }
}

// Health check hook
export const useHealth = () => {
  const { setOnlineStatus } = useStore()
  
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await api.get('/health')
      setOnlineStatus(true)
      return response.data
    },
    refetchInterval: 30000, // Check every 30 seconds
    retry: (failureCount, error) => {
      setOnlineStatus(false)
      return failureCount < 3
    },
    onError: () => {
      setOnlineStatus(false)
    }
  })
}

// System info hook
export const useSystemInfo = () => {
  const { setSystemInfo } = useStore()
  
  return useQuery({
    queryKey: ['system', 'info'],
    queryFn: async () => {
      const response = await api.get('/system/info')
      setSystemInfo(response.data)
      return response.data
    },
    refetchInterval: 60000, // Refresh every minute
  })
}

// Configuration hooks
export const useConfig = () => {
  return useQuery({
    queryKey: ['config'],
    queryFn: async () => {
      const response = await api.get('/config')
      return response.data
    },
  })
}

export const useUpdateConfig = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (config) => {
      const response = await api.put('/config', config)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
      toast.success('Configuration updated successfully')
    },
    onError: (error) => {
      console.error('Config update failed:', error)
    }
  })
}

// Drives hooks
export const useDrives = () => {
  return useQuery({
    queryKey: ['drives'],
    queryFn: async () => {
      const response = await api.get('/drives')
      return response.data
    },
  })
}

export const useUpdateDrive = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ driveId, updates }) => {
      const response = await api.put(`/drives/${driveId}`, updates)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drives'] })
      toast.success('Drive configuration updated')
    }
  })
}

export const useAddDrive = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (driveConfig) => {
      const response = await api.post('/drives', driveConfig)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drives'] })
      toast.success('Drive added successfully')
    }
  })
}

export const useRemoveDrive = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (driveId) => {
      const response = await api.delete(`/drives/${driveId}`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drives'] })
      toast.success('Drive removed successfully')
    }
  })
}

// Rules hooks
export const useRules = () => {
  return useQuery({
    queryKey: ['rules'],
    queryFn: async () => {
      const response = await api.get('/rules')
      return response.data
    },
  })
}

export const useCreateRule = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (rule) => {
      const response = await api.post('/rules', rule)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
      toast.success('Rule created successfully')
    }
  })
}

export const useUpdateRule = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ ruleId, updates }) => {
      const response = await api.put(`/rules/${ruleId}`, updates)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
      toast.success('Rule updated successfully')
    }
  })
}

export const useDeleteRule = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (ruleId) => {
      const response = await api.delete(`/rules/${ruleId}`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
      toast.success('Rule deleted successfully')
    }
  })
}

// Reports hook
export const useReports = (params = {}) => {
  return useQuery({
    queryKey: ['reports', params],
    queryFn: async () => {
      const response = await api.get('/reports', { params })
      return response.data
    },
  })
}

export default api