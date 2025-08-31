import { useEventStream } from '@/hooks/useEventStream'
import TopbarMetrics from '@/components/dashboard/TopbarMetrics'
import ActiveJobsPanel from '@/components/dashboard/ActiveJobsPanel'
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
        {/* Two-column main grid */}
        <div className="grid grid-cols-12 gap-4">
          {/* Left column - span 7 */}
          <div className="col-span-12 lg:col-span-7 space-y-4">
            <ActiveJobsPanel />
            <RecentRecordingsPanel />
          </div>
          
          {/* Right column - span 5 */}
          <div className="col-span-12 lg:col-span-5 space-y-4">
            <JobStatsMini />
            <DriveStatusPanel />
          </div>
        </div>
      </div>
    </>
  )
}