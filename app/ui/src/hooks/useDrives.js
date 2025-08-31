import { useQuery } from '@tanstack/react-query'
import { useApi } from './useApi'

export function useDrives() {
  const { api } = useApi()
  
  return useQuery({
    queryKey: ['drives', 'status'],
    queryFn: async () => {
      const response = await api.get('/drives/status')
      return response.data
    },
    refetchInterval: 10000, // Refresh every 10 seconds
    staleTime: 5000
  })
}