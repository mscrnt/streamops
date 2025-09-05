import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  ChevronRight, 
  ChevronLeft, 
  Check, 
  AlertCircle,
  HardDrive,
  Video,
  Eye
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { useApi } from '@/hooks/useApi'
import WizardDrives from '@/components/wizard/WizardDrives'
import WizardOBSMulti from '@/components/wizard/WizardOBSMulti'
import WizardReview from '@/components/wizard/WizardReview'

const WIZARD_STEPS = [
  {
    id: 'drives',
    title: 'Drives & Folders',
    description: 'Pick where your recordings land and where edited files should go',
    icon: HardDrive,
    component: WizardDrives
  },
  {
    id: 'obs',
    title: 'OBS Connections',
    description: 'Connect to OBS instances for smarter timing and session tags (optional)',
    icon: Video,
    component: WizardOBSMulti
  },
  {
    id: 'review',
    title: 'Review & Apply',
    description: 'Review your configuration and start StreamOps',
    icon: Eye,
    component: WizardReview
  }
]

export default function Wizard() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { api } = useApi()
  const [currentStep, setCurrentStep] = useState(0)
  const [wizardData, setWizardData] = useState({
    drives: [],
    obs: []  // Now an array of connections
  })
  const [stepErrors, setStepErrors] = useState({})
  const [isApplying, setIsApplying] = useState(false)
  
  // Check if wizard has been completed
  const { data: wizardState, refetch: refetchWizardState } = useQuery({
    queryKey: ['wizard', 'state'],
    queryFn: async () => {
      const response = await api.get('/wizard/state')
      return response.data
    }
  })
  
  // Get wizard defaults
  const { data: defaults, isLoading: loadingDefaults } = useQuery({
    queryKey: ['wizard', 'defaults'],
    queryFn: async () => {
      const response = await api.get('/wizard/defaults')
      return response.data
    }
  })
  
  // Apply wizard configuration
  const applyMutation = useMutation({
    mutationFn: async (data) => {
      console.log('[Wizard] Applying configuration:', data)
      console.log('[Wizard] Data to send:', JSON.stringify(data))
      
      try {
        const response = await api.post('/wizard/apply', data)
        console.log('[Wizard] Apply response:', response.data)
        return response.data
      } catch (error) {
        console.error('[Wizard] API Error:', error)
        console.error('[Wizard] Request data was:', data)
        throw error
      }
    },
    onSuccess: async (data) => {
      console.log('[Wizard] onSuccess called with data:', data)
      // Clear the draft since we successfully applied
      localStorage.removeItem('wizard_draft')
      // Set applying flag to prevent re-render
      setIsApplying(true)
      
      // Poll the wizard state until it's marked as complete
      let retries = 0
      const maxRetries = 10
      
      while (retries < maxRetries) {
        // Invalidate and refetch the wizard state
        await queryClient.invalidateQueries(['wizard', 'state'])
        
        // Fetch using the proper queryFn
        const result = await queryClient.fetchQuery({
          queryKey: ['wizard', 'state'],
          queryFn: async () => {
            const response = await api.get('/wizard/state')
            return response.data
          }
        })
        
        console.log(`[Wizard] Checking wizard state (attempt ${retries + 1}):`, result)
        
        if (result?.completed) {
          console.log('[Wizard] Wizard state confirmed as complete, navigating to dashboard')
          // Give React a moment to process
          await new Promise(resolve => setTimeout(resolve, 100))
          window.location.href = '/dashboard'
          return
        }
        
        // Wait before next retry
        await new Promise(resolve => setTimeout(resolve, 500))
        retries++
      }
      
      // If we couldn't confirm completion after max retries, still navigate
      console.warn('[Wizard] Could not confirm wizard completion after max retries, navigating anyway')
      window.location.href = '/dashboard'
    },
    onError: (error) => {
      console.error('[Wizard] Failed to apply configuration:', error)
      console.error('[Wizard] Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      })
      setIsApplying(false)
    }
  })
  
  // Load saved draft from localStorage
  useEffect(() => {
    const savedDraft = localStorage.getItem('wizard_draft')
    if (savedDraft) {
      try {
        const draft = JSON.parse(savedDraft)
        setWizardData(draft)
      } catch (e) {
        console.error('Failed to load wizard draft:', e)
      }
    }
  }, [])
  
  // Save draft to localStorage on changes
  useEffect(() => {
    localStorage.setItem('wizard_draft', JSON.stringify(wizardData))
  }, [wizardData])
  
  // If wizard is already completed, show option to re-run (but not while applying)
  if (wizardState?.completed && !isApplying) {
    return (
      <div className="flex items-center justify-center min-h-screen p-6">
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle>Setup Already Complete</CardTitle>
            <CardDescription>
              StreamOps has already been configured. Would you like to re-run the setup wizard?
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button 
              onClick={() => setCurrentStep(0)}
              className="w-full"
            >
              Re-run Setup Wizard
            </Button>
            <Button 
              variant="outline" 
              onClick={() => navigate('/dashboard')}
              className="w-full"
            >
              Go to Dashboard
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }
  
  const CurrentStepComponent = WIZARD_STEPS[currentStep].component
  const currentStepData = WIZARD_STEPS[currentStep]
  const Icon = currentStepData.icon
  
  const handleNext = () => {
    if (currentStep < WIZARD_STEPS.length - 1) {
      setCurrentStep(currentStep + 1)
    }
  }
  
  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }
  
  const handleStepData = useCallback((stepId, data) => {
    setWizardData(prev => ({
      ...prev,
      [stepId]: data
    }))
  }, [])
  
  const handleSkip = () => {
    handleNext()
  }
  
  const handleApply = async () => {
    console.log('[Wizard] handleApply called')
    console.log('[Wizard] Starting apply with data:', wizardData)
    
    if (!wizardData.drives || wizardData.drives.length === 0) {
      console.error('[Wizard] No drives configured!')
      return
    }
    
    // Clean the data to remove any circular references or undefined values
    const cleanData = {
      drives: wizardData.drives || [],
      obs: (wizardData.obs || []).map(conn => ({
        id: conn.id || '',
        name: conn.name || '',
        ws_url: conn.ws_url || '',
        connected: conn.connected || false,
        auto_connect: conn.auto_connect !== false,
        roles: conn.roles || []
      })),
      rules: [],  // Empty rules array for compatibility
      overlays: { enabled: false }  // Default overlays for compatibility
    }
    
    // Log the exact data being sent
    console.log('[Wizard] Clean data structure:', JSON.stringify(cleanData, null, 2))
    
    setIsApplying(true)
    try {
      console.log('[Wizard] Calling mutateAsync with clean data...')
      const result = await applyMutation.mutateAsync(cleanData)
      console.log('[Wizard] mutateAsync completed:', result)
    } catch (error) {
      console.error('[Wizard] Apply failed:', error)
      setIsApplying(false)
      // Error is handled in the mutation's onError
    }
  }
  
  const isStepValid = (stepId) => {
    if (stepId === 'drives') {
      const drives = wizardData.drives || []
      return drives.some(d => d.role === 'recording') && 
             drives.some(d => d.role === 'editing')
    }
    return true // Other steps are optional
  }
  
  if (loadingDefaults) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading setup wizard...</p>
        </div>
      </div>
    )
  }
  
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">StreamOps Setup Wizard</h1>
              <p className="text-muted-foreground">
                Let's get your media pipeline up and running in just a few minutes
              </p>
            </div>
            <Button 
              variant="ghost" 
              onClick={() => navigate('/dashboard')}
              className="text-muted-foreground"
            >
              Exit Setup
            </Button>
          </div>
        </div>
      </div>
      
      {/* Progress Steps */}
      <div className="border-b bg-muted/30">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {WIZARD_STEPS.map((step, index) => {
              const StepIcon = step.icon
              const isActive = index === currentStep
              const isComplete = index < currentStep
              const isValid = isStepValid(step.id)
              
              return (
                <div key={step.id} className="flex items-center">
                  <button
                    onClick={() => isComplete && setCurrentStep(index)}
                    disabled={!isComplete}
                    className={`
                      flex items-center space-x-2 px-4 py-2 rounded-lg transition-all
                      ${isActive ? 'bg-primary text-primary-foreground' : ''}
                      ${isComplete ? 'cursor-pointer hover:bg-muted' : 'cursor-default'}
                      ${!isActive && !isComplete ? 'text-muted-foreground' : ''}
                    `}
                  >
                    <div className={`
                      w-8 h-8 rounded-full flex items-center justify-center
                      ${isActive ? 'bg-primary-foreground/20' : ''}
                      ${isComplete ? 'bg-green-500/20' : 'bg-muted'}
                    `}>
                      {isComplete ? (
                        <Check className="h-4 w-4 text-green-500" />
                      ) : (
                        <StepIcon className="h-4 w-4" />
                      )}
                    </div>
                    <span className="font-medium hidden md:inline">
                      {step.title}
                    </span>
                  </button>
                  
                  {index < WIZARD_STEPS.length - 1 && (
                    <ChevronRight className="h-4 w-4 mx-2 text-muted-foreground" />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
      
      {/* Main Content */}
      <div className="container mx-auto px-6 py-8">
        <div className="max-w-4xl mx-auto">
          {/* Step Header */}
          <div className="mb-8">
            <div className="flex items-center space-x-3 mb-2">
              <Icon className="h-6 w-6 text-primary" />
              <h2 className="text-2xl font-bold">{currentStepData.title}</h2>
            </div>
            <p className="text-muted-foreground">
              {currentStepData.description}
            </p>
          </div>
          
          {/* Step Component */}
          <CurrentStepComponent
            data={wizardData[currentStepData.id]}
            onChange={(data) => handleStepData(currentStepData.id, data)}
            defaults={defaults}
            allData={wizardData}
            onApply={handleApply}
            applyMutation={applyMutation}
          />
          
          {/* Navigation */}
          <div className="flex items-center justify-between mt-8 pt-8 border-t">
            <Button
              variant="outline"
              onClick={handlePrevious}
              disabled={currentStep === 0}
            >
              <ChevronLeft className="h-4 w-4 mr-2" />
              Previous
            </Button>
            
            <div className="flex items-center space-x-3">
              {currentStep < WIZARD_STEPS.length - 1 && (
                <>
                  {currentStepData.id !== 'drives' && (
                    <Button
                      variant="ghost"
                      onClick={handleSkip}
                      className="text-muted-foreground"
                    >
                      Skip
                    </Button>
                  )}
                  <Button
                    onClick={handleNext}
                    disabled={currentStepData.id === 'drives' && !isStepValid('drives')}
                  >
                    Next
                    <ChevronRight className="h-4 w-4 ml-2" />
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}