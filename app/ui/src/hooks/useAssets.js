import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useStore, useAssetStore } from '@/store/useStore'
import { useApi } from './useApi'
import toast from 'react-hot-toast'

// Helper to strip empty values from params
const stripEmpty = (obj) =>
  Object.fromEntries(Object.entries(obj).filter(([_, v]) => v !== undefined && v !== '' && v !== null))

// Assets listing hook
export const useAssets = (passedParams = {}, { override = false } = {}) => {
  const { assetFilters } = useStore()
  const { api } = useApi()

  // Either use passed params only (override) or merge with store filters
  const queryParams = stripEmpty(
    override ? passedParams : { ...assetFilters, ...passedParams }
  )

  return useQuery({
    queryKey: ['assets', queryParams],
    queryFn: async () => {
      // API requires trailing slash for list endpoints
      const response = await api.get('/assets/', { params: queryParams })
      return response.data
    },
    staleTime: 30000, // Consider data stale after 30 seconds
  })
}

// Single asset hook
export const useAsset = (assetId) => {
  const { api } = useApi()

  return useQuery({
    queryKey: ['assets', assetId],
    queryFn: async () => {
      const response = await api.get(`/assets/${assetId}`)
      return response.data
    },
    enabled: !!assetId,
  })
}

// Asset search hook with debouncing
export const useAssetSearch = (searchQuery, options = {}) => {
  const { api } = useApi()
  const { 
    limit = 20, 
    offset = 0,
    type = 'all',
    ...otherOptions 
  } = options

  return useQuery({
    queryKey: ['assets', 'search', searchQuery, options],
    queryFn: async () => {
      if (!searchQuery || searchQuery.length < 2) {
        return { assets: [], total: 0 }
      }

      const response = await api.get('/assets/search', {
        params: {
          q: searchQuery,
          limit,
          offset,
          type,
          ...otherOptions
        }
      })
      return response.data
    },
    enabled: !!(searchQuery && searchQuery.length >= 2),
    staleTime: 10000, // Results are stale after 10 seconds
  })
}

// Asset metadata update hook
export const useUpdateAsset = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async ({ assetId, updates }) => {
      const response = await api.patch(`/assets/${assetId}`, updates)
      return response.data
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['assets'] })
      queryClient.setQueryData(['assets', variables.assetId], data)
      toast.success('Asset updated successfully')
    },
    onError: (error) => {
      console.error('Asset update failed:', error)
    }
  })
}

// Asset deletion hook
export const useDeleteAsset = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async (assetId) => {
      const response = await api.delete(`/assets/${assetId}`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] })
      toast.success('Asset deleted successfully')
    },
    onError: (error) => {
      console.error('Asset deletion failed:', error)
    }
  })
}

// Bulk asset operations
export const useBulkAssetOperation = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async ({ operation, assetIds, parameters = {} }) => {
      const response = await api.post('/assets/bulk', {
        operation,
        asset_ids: assetIds,
        parameters
      })
      return response.data
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['assets'] })
      const { operation, assetIds } = variables
      toast.success(`${operation} operation completed for ${assetIds.length} assets`)
    },
    onError: (error) => {
      console.error('Bulk asset operation failed:', error)
    }
  })
}

// Asset reindex hook
export const useReindexAsset = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async (assetId) => {
      const response = await api.post(`/assets/${assetId}/reindex`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] })
      toast.success('Asset reindexing started')
    }
  })
}

// Thumbnail regeneration removed - videos preview natively

// Asset tags management
export const useAssetTags = (assetId) => {
  const { api } = useApi()

  return useQuery({
    queryKey: ['assets', assetId, 'tags'],
    queryFn: async () => {
      const response = await api.get(`/assets/${assetId}/tags`)
      return response.data
    },
    enabled: !!assetId,
  })
}

export const useUpdateAssetTags = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async ({ assetId, tags }) => {
      const response = await api.put(`/assets/${assetId}/tags`, { tags })
      return response.data
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['assets'] })
      queryClient.invalidateQueries({ queryKey: ['assets', variables.assetId, 'tags'] })
      toast.success('Tags updated successfully')
    }
  })
}

// Asset statistics hook
export const useAssetStats = (timeRange = '24h') => {
  const { api } = useApi()

  return useQuery({
    queryKey: ['assets', 'stats', timeRange],
    queryFn: async () => {
      const response = await api.get('/assets/stats', {
        params: { time_range: timeRange }
      })
      return response.data
    },
    refetchInterval: 60000, // Refetch every minute
  })
}

// Recent assets hook
export const useRecentAssets = (limit = 10) => {
  const { api } = useApi()

  return useQuery({
    queryKey: ['assets', 'recent', limit],
    queryFn: async () => {
      const response = await api.get('/assets/recent', {
        params: { limit }
      })
      return response.data
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  })
}

// Asset types/formats hook
export const useAssetTypes = () => {
  const { api } = useApi()

  return useQuery({
    queryKey: ['assets', 'types'],
    queryFn: async () => {
      const response = await api.get('/assets/types')
      return response.data
    },
    staleTime: Infinity, // Types rarely change
  })
}

// Asset download hook
export const useDownloadAsset = () => {
  const { api } = useApi()

  return useMutation({
    mutationFn: async ({ assetId, variant = 'original' }) => {
      const response = await api.get(`/assets/${assetId}/download`, {
        params: { variant },
        responseType: 'blob'
      })
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      
      // Get filename from Content-Disposition header or use fallback
      const contentDisposition = response.headers['content-disposition']
      let filename = `asset_${assetId}.${variant === 'proxy' ? 'mov' : 'mp4'}`
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/)
        if (filenameMatch) {
          filename = filenameMatch[1]
        }
      }
      
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      
      return response.data
    },
    onSuccess: () => {
      toast.success('Download started')
    },
    onError: (error) => {
      console.error('Download failed:', error)
      toast.error('Download failed')
    }
  })
}

// Asset clip creation hook
export const useCreateAssetClip = () => {
  const queryClient = useQueryClient()
  const { api } = useApi()

  return useMutation({
    mutationFn: async ({ assetId, startTime, endTime, title }) => {
      const response = await api.post(`/assets/${assetId}/clips`, {
        start_time: startTime,
        end_time: endTime,
        title
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] })
      toast.success('Clip creation job started')
    }
  })
}

// Asset preview hook (for video thumbnails/sprites)
export const useAssetPreview = (assetId) => {
  const { api } = useApi()

  return useQuery({
    queryKey: ['assets', assetId, 'preview'],
    queryFn: async () => {
      const response = await api.get(`/assets/${assetId}/preview`)
      return response.data
    },
    enabled: !!assetId,
    staleTime: 300000, // 5 minutes
  })
}

// File browser hook for exploring asset directories
export const useFileBrowser = (path = '') => {
  const { api } = useApi()

  return useQuery({
    queryKey: ['files', path],
    queryFn: async () => {
      const response = await api.get('/files/browse', {
        params: { path }
      })
      return response.data
    },
    enabled: false, // Only run when explicitly fetched
  })
}

export default useAssets