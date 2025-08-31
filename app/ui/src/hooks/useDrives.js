import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useApi } from './useApi'
import toast from 'react-hot-toast'

// Get drive status from environment-configured drives
export function useDrives() {
  const { api } = useApi()
  
  return useQuery({
    queryKey: ['drives', 'status'],
    queryFn: async () => {
      const response = await api.get('/drives/status')
      return response.data || []
    },
    refetchInterval: 10000, // Refresh every 10 seconds
    staleTime: 5000
  })
}

// Get discovered drives
export function useDiscoveredDrives() {
  const { api } = useApi()
  
  return useQuery({
    queryKey: ['drives', 'discovered'],
    queryFn: async () => {
      const response = await api.get('/drives/discovered')
      return response.data || []
    },
    staleTime: 30000
  })
}

// Assign role to a drive
export function useAssignRole() {
  const queryClient = useQueryClient()
  const { api } = useApi()
  
  return useMutation({
    mutationFn: async ({ role, root_id, subpath = '', watch = true }) => {
      const response = await api.post('/drives/assign-role', {
        role,
        root_id,
        subpath,
        watch
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drives'] })
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      toast.success('Role assigned successfully')
    },
    onError: (error) => {
      const message = error.response?.data?.detail || 'Failed to assign role'
      toast.error(message)
    }
  })
}

// Get role assignments
export function useRoleAssignments() {
  const { api } = useApi()
  
  return useQuery({
    queryKey: ['roles'],
    queryFn: async () => {
      const response = await api.get('/drives/roles')
      return response.data
    },
    staleTime: 30000
  })
}

// Remove role assignment
export function useRemoveRole() {
  const queryClient = useQueryClient()
  const { api } = useApi()
  
  return useMutation({
    mutationFn: async (role) => {
      const response = await api.delete(`/drives/roles/${role}`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drives'] })
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      toast.success('Role removed successfully')
    },
    onError: (error) => {
      const message = error.response?.data?.detail || 'Failed to remove role'
      toast.error(message)
    }
  })
}