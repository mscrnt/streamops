import { 
  Check, 
  AlertCircle,
  HardDrive,
  Video,
  Wand2,
  Layers,
  Rocket,
  Settings
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

export default function WizardReview({ allData, onApply, applyMutation }) {
  const { drives, obs, rules, overlays } = allData
  
  const hasRecordingDrive = drives?.some(d => d.role === 'recording' && d.enabled)
  const hasEditingDrive = drives?.some(d => d.role === 'editing' && d.enabled)
  const enabledRules = rules?.filter(r => r.enabled) || []
  
  const isReady = hasRecordingDrive && hasEditingDrive
  
  return (
    <div className="space-y-6">
      {/* Summary Card */}
      <Card className={isReady ? 'border-green-500/50' : 'border-yellow-500/50'}>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Configuration Summary
            {isReady ? (
              <Badge variant="success">
                <Check className="h-4 w-4 mr-1" />
                Ready to Start
              </Badge>
            ) : (
              <Badge variant="warning">
                <AlertCircle className="h-4 w-4 mr-1" />
                Missing Requirements
              </Badge>
            )}
          </CardTitle>
          <CardDescription>
            Review your configuration before starting StreamOps
          </CardDescription>
        </CardHeader>
      </Card>
      
      {/* Configuration Details */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Drives */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center space-x-2">
              <HardDrive className="h-5 w-5 text-primary" />
              <span>Drives & Folders</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {drives?.filter(d => d.enabled).map(drive => (
                <div key={drive.id} className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-sm">{drive.label}</p>
                    <p className="text-xs text-muted-foreground">{drive.path}</p>
                  </div>
                  <Badge variant="outline">
                    {drive.role}
                  </Badge>
                </div>
              ))}
              {(!drives || drives.length === 0) && (
                <p className="text-sm text-muted-foreground">No drives configured</p>
              )}
            </div>
          </CardContent>
        </Card>
        
        {/* OBS */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center space-x-2">
              <Video className="h-5 w-5 text-primary" />
              <span>OBS Integration</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {obs?.enabled ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Status</span>
                  <Badge variant="success">Enabled</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">URL</span>
                  <span className="text-sm font-mono text-muted-foreground">
                    {obs.url}
                  </span>
                </div>
              </div>
            ) : (
              <div className="flex items-center space-x-2 text-muted-foreground">
                <Settings className="h-4 w-4" />
                <span className="text-sm">Not configured (optional)</span>
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Rules */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center space-x-2">
              <Wand2 className="h-5 w-5 text-primary" />
              <span>Automation Rules</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {enabledRules.length > 0 ? (
              <div className="space-y-2">
                {enabledRules.map(rule => (
                  <div key={rule.id} className="flex items-center space-x-2">
                    <Check className="h-4 w-4 text-green-500" />
                    <span className="text-sm">{rule.label}</span>
                  </div>
                ))}
                <div className="pt-2 border-t">
                  <p className="text-xs text-muted-foreground">
                    {enabledRules.length} rule{enabledRules.length !== 1 ? 's' : ''} will be active
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No rules enabled</p>
            )}
          </CardContent>
        </Card>
        
        {/* Overlays */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center space-x-2">
              <Layers className="h-5 w-5 text-primary" />
              <span>Stream Overlays</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {overlays?.enabled ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Preset</span>
                  <Badge variant="outline">{overlays.preset}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Position</span>
                  <span className="text-sm text-muted-foreground">
                    {overlays.position}
                  </span>
                </div>
              </div>
            ) : (
              <div className="flex items-center space-x-2 text-muted-foreground">
                <Settings className="h-4 w-4" />
                <span className="text-sm">Not configured (optional)</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      
      {/* What Happens Next */}
      <Card>
        <CardHeader>
          <CardTitle>What Happens Next</CardTitle>
          <CardDescription>
            Once you apply this configuration:
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-start space-x-3">
              <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-xs font-medium">1</span>
              </div>
              <div>
                <p className="font-medium text-sm">Drive watchers start</p>
                <p className="text-xs text-muted-foreground">
                  StreamOps will begin monitoring your recording folders for new files
                </p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-xs font-medium">2</span>
              </div>
              <div>
                <p className="font-medium text-sm">Existing files indexed</p>
                <p className="text-xs text-muted-foreground">
                  Any recordings already in your folders will be discovered and indexed
                </p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-xs font-medium">3</span>
              </div>
              <div>
                <p className="font-medium text-sm">Rules activate</p>
                <p className="text-xs text-muted-foreground">
                  Your automation rules will begin processing files based on your settings
                </p>
              </div>
            </div>
            
            {obs?.enabled && (
              <div className="flex items-start space-x-3">
                <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs font-medium">4</span>
                </div>
                <div>
                  <p className="font-medium text-sm">OBS connects</p>
                  <p className="text-xs text-muted-foreground">
                    StreamOps will connect to OBS and start tracking your recording sessions
                  </p>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
      
      {/* Action Button */}
      <Card className="border-primary">
        <CardContent className="py-6">
          <div className="text-center space-y-4">
            <Rocket className="h-12 w-12 text-primary mx-auto" />
            <div>
              <h3 className="text-lg font-medium mb-2">Ready to Launch StreamOps?</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Your configuration will be saved and StreamOps will start processing
              </p>
            </div>
            <Button 
              size="lg"
              onClick={onApply}
              disabled={!isReady || applyMutation?.isPending}
              className="min-w-48"
            >
              {applyMutation?.isPending ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current mr-2" />
                  Applying Configuration...
                </>
              ) : (
                <>
                  <Rocket className="h-5 w-5 mr-2" />
                  Start StreamOps
                </>
              )}
            </Button>
            
            {!isReady && (
              <p className="text-sm text-yellow-600 dark:text-yellow-400">
                <AlertCircle className="h-4 w-4 inline mr-1" />
                Please configure at least a recording source and editing target folder
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}