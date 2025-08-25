import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

// Main application store
export const useStore = create(
  persist(
    (set, get) => ({
      // UI State
      theme: 'light',
      sidebarCollapsed: false,
      
      // System State
      systemInfo: null,
      isOnline: true,
      
      // Filters and Search
      assetFilters: {
        search: '',
        type: 'all',
        status: 'all',
        sortBy: 'created_at',
        sortOrder: 'desc',
      },
      
      jobFilters: {
        status: 'all',
        type: 'all',
        sortBy: 'created_at',
        sortOrder: 'desc',
      },
      
      // Actions
      toggleTheme: () => set((state) => ({ 
        theme: state.theme === 'light' ? 'dark' : 'light' 
      })),
      
      toggleSidebar: () => set((state) => ({ 
        sidebarCollapsed: !state.sidebarCollapsed 
      })),
      
      setSidebarCollapsed: (collapsed) => set({ 
        sidebarCollapsed: collapsed 
      }),
      
      setSystemInfo: (info) => set({ systemInfo: info }),
      
      setOnlineStatus: (status) => set({ isOnline: status }),
      
      // Asset filters
      setAssetFilters: (filters) => set((state) => ({
        assetFilters: { ...state.assetFilters, ...filters }
      })),
      
      resetAssetFilters: () => set({
        assetFilters: {
          search: '',
          type: 'all',
          status: 'all',
          sortBy: 'created_at',
          sortOrder: 'desc',
        }
      }),
      
      // Job filters
      setJobFilters: (filters) => set((state) => ({
        jobFilters: { ...state.jobFilters, ...filters }
      })),
      
      resetJobFilters: () => set({
        jobFilters: {
          status: 'all',
          type: 'all',
          sortBy: 'created_at',
          sortOrder: 'desc',
        }
      }),
    }),
    {
      name: 'streamops-store',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        theme: state.theme,
        sidebarCollapsed: state.sidebarCollapsed,
        assetFilters: state.assetFilters,
        jobFilters: state.jobFilters,
      }),
    }
  )
)

// Job queue store for real-time updates
export const useJobStore = create((set, get) => ({
  jobs: [],
  activeJobs: [],
  jobHistory: [],
  
  // Job management
  setJobs: (jobs) => set({ jobs }),
  
  addJob: (job) => set((state) => ({
    jobs: [job, ...state.jobs]
  })),
  
  updateJob: (jobId, updates) => set((state) => ({
    jobs: state.jobs.map(job => 
      job.id === jobId ? { ...job, ...updates } : job
    )
  })),
  
  removeJob: (jobId) => set((state) => ({
    jobs: state.jobs.filter(job => job.id !== jobId)
  })),
  
  // Active jobs (running/pending)
  setActiveJobs: (jobs) => set({ activeJobs: jobs }),
  
  // Job history
  addToHistory: (job) => set((state) => ({
    jobHistory: [job, ...state.jobHistory.slice(0, 99)] // Keep last 100
  })),
  
  clearHistory: () => set({ jobHistory: [] }),
  
  // Computed getters
  getJobById: (id) => get().jobs.find(job => job.id === id),
  getJobsByStatus: (status) => get().jobs.filter(job => job.status === status),
  getJobsByType: (type) => get().jobs.filter(job => job.type === type),
}))

// Asset store for media files
export const useAssetStore = create((set, get) => ({
  assets: [],
  selectedAssets: [],
  totalAssets: 0,
  
  // Asset management
  setAssets: (assets, total = null) => set({ 
    assets, 
    totalAssets: total !== null ? total : assets.length 
  }),
  
  addAsset: (asset) => set((state) => ({
    assets: [asset, ...state.assets],
    totalAssets: state.totalAssets + 1
  })),
  
  updateAsset: (assetId, updates) => set((state) => ({
    assets: state.assets.map(asset => 
      asset.id === assetId ? { ...asset, ...updates } : asset
    )
  })),
  
  removeAsset: (assetId) => set((state) => ({
    assets: state.assets.filter(asset => asset.id !== assetId),
    totalAssets: Math.max(0, state.totalAssets - 1),
    selectedAssets: state.selectedAssets.filter(id => id !== assetId)
  })),
  
  // Selection management
  selectAsset: (assetId) => set((state) => ({
    selectedAssets: [...state.selectedAssets, assetId]
  })),
  
  deselectAsset: (assetId) => set((state) => ({
    selectedAssets: state.selectedAssets.filter(id => id !== assetId)
  })),
  
  selectAllAssets: () => set((state) => ({
    selectedAssets: state.assets.map(asset => asset.id)
  })),
  
  deselectAllAssets: () => set({ selectedAssets: [] }),
  
  toggleAssetSelection: (assetId) => set((state) => {
    const isSelected = state.selectedAssets.includes(assetId)
    return {
      selectedAssets: isSelected 
        ? state.selectedAssets.filter(id => id !== assetId)
        : [...state.selectedAssets, assetId]
    }
  }),
  
  // Computed getters
  getAssetById: (id) => get().assets.find(asset => asset.id === id),
  getSelectedAssets: () => {
    const { assets, selectedAssets } = get()
    return assets.filter(asset => selectedAssets.includes(asset.id))
  },
}))

// Notification store
export const useNotificationStore = create((set, get) => ({
  notifications: [],
  unreadCount: 0,
  
  addNotification: (notification) => {
    const id = Date.now().toString()
    set((state) => ({
      notifications: [{
        id,
        timestamp: new Date().toISOString(),
        read: false,
        ...notification
      }, ...state.notifications],
      unreadCount: state.unreadCount + 1
    }))
    return id
  },
  
  markAsRead: (id) => set((state) => ({
    notifications: state.notifications.map(notification =>
      notification.id === id 
        ? { ...notification, read: true }
        : notification
    ),
    unreadCount: Math.max(0, state.unreadCount - 1)
  })),
  
  markAllAsRead: () => set((state) => ({
    notifications: state.notifications.map(notification => ({
      ...notification,
      read: true
    })),
    unreadCount: 0
  })),
  
  removeNotification: (id) => set((state) => {
    const notification = state.notifications.find(n => n.id === id)
    return {
      notifications: state.notifications.filter(n => n.id !== id),
      unreadCount: notification && !notification.read 
        ? Math.max(0, state.unreadCount - 1)
        : state.unreadCount
    }
  }),
  
  clearAllNotifications: () => set({
    notifications: [],
    unreadCount: 0
  }),
}))

export default useStore