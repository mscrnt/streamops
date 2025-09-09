import { useState, useEffect } from 'react'
import { RefreshCw, Film } from 'lucide-react'
import Button from '@/components/ui/Button'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import AssetRow from '@/components/assets/AssetRow'
import AssetPreviewDrawer from '@/components/assets/AssetPreviewDrawer'


export default function RecentRecordingsPanel() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [previewAssetId, setPreviewAssetId] = useState(null)
  const [showMenu, setShowMenu] = useState(null)
  const [, forceUpdate] = useState({})
  
  // Force re-render every minute to update relative times
  useEffect(() => {
    const interval = setInterval(() => {
      forceUpdate({})
    }, 60000) // Update every 60 seconds
    
    return () => clearInterval(interval)
  }, [])
  
  // Fetch recent assets (API already excludes proxy files by default)
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['assets', 'recent'],
    queryFn: async () => {
      const res = await fetch('/api/assets/?sort=created_at:desc&per_page=10')
      if (!res.ok) throw new Error('Failed to fetch recent assets')
      return res.json()
    },
    staleTime: 1000,
    refetchOnWindowFocus: false
  })
  
  // Auto-refresh every minute to update data
  useEffect(() => {
    const interval = setInterval(() => {
      queryClient.invalidateQueries(['assets', 'recent'])
    }, 60000) // Refresh every 60 seconds
    
    return () => clearInterval(interval)
  }, [queryClient])
  
  const recordings = data?.assets || []
  
  const handleToggleMenu = (assetId) => {
    setShowMenu(showMenu === assetId ? null : assetId)
  }
  
  const handleAction = (action, asset) => {
    if (action === 'preview') {
      setPreviewAssetId(asset.id)
    } else if (action === 'open') {
      navigate(`/recordings/${asset.id}`)
    } else if (action === 'locate') {
      const filename = asset.abs_path?.split('/').pop() || ''
      navigate(`/recordings?search=${encodeURIComponent(filename)}`)
    }
  }
  
  return (
    <div className="rounded-lg border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Recent Recordings</h3>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => refetch()}
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
          <Link to="/recordings?filter=recording&sort=created_at:desc">
            <Button variant="ghost" size="sm">
              View All
            </Button>
          </Link>
        </div>
      </div>
      
      {/* Content with internal scroll */}
      <div className="max-h-[500px] overflow-y-auto scrollbar-thin">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-pulse text-sm text-muted-foreground">Loading recordings...</div>
          </div>
        ) : recordings.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center p-4">
            <Film className="h-8 w-8 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">
              No recent recordings from watched folders.
            </p>
          </div>
        ) : (
          <div className="">
            {recordings.map((asset) => (
              <AssetRow
                key={asset.id}
                asset={asset}
                selected={false}
                onToggleSelect={() => {}}
                onPreview={() => handleAction('preview', asset)}
                onAction={(action) => handleAction(action, asset)}
                showMenu={showMenu === asset.id}
                onToggleMenu={() => handleToggleMenu(asset.id)}
                hideCheckbox={true}
              />
            ))}
          </div>
        )}
      </div>
      
      {/* Preview Drawer */}
      {previewAssetId && (
        <AssetPreviewDrawer
          assetId={previewAssetId}
          onClose={() => setPreviewAssetId(null)}
        />
      )}
    </div>
  )
}