import { useEventStream } from '@/hooks/useEventStream'
import TopbarMetrics from '@/components/dashboard/TopbarMetrics'
import RecentRecordingsPanel from '@/components/dashboard/RecentRecordingsPanel'
import JobStatsMini from '@/components/dashboard/JobStatsMini'
import DriveStatusPanel from '@/components/dashboard/DriveStatusPanel'

export default function Dashboard() {
  // Enable event stream for real-time updates
  useEventStream()
  
  return (
    <>
      {/* Sticky Top Bar with KPIs */}
      <TopbarMetrics />
      
      {/* Main Dashboard Content */}
      <div className="p-4 md:p-6 space-y-4">
        {/* Top row - Recent Recordings with timeline */}
        <RecentRecordingsPanel />
        
        {/* Bottom row - Jobs and Drives */}
        <div className="grid grid-cols-12 gap-4">
          {/* Jobs stats - span 5 */}
          <div className="col-span-12 lg:col-span-5">
            <JobStatsMini />
          </div>
          
          {/* Drive status - span 7 */}
          <div className="col-span-12 lg:col-span-7">
            <DriveStatusPanel />
          </div>
        </div>
      </div>
    </>
  )
}