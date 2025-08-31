import { useQuery } from '@tanstack/react-query'
import { useApi } from './useApi'

export function useJobStats({ window = '24h' } = {}) {
  const { api } = useApi()
  
  return useQuery({
    queryKey: ['jobs', 'stats', window],
    queryFn: async () => {
      const response = await api.get('/jobs/stats', {
        params: { window }
      })
      return response.data
    },
    refetchInterval: 30000, // Refresh every 30 seconds
    staleTime: 10000
  })
}