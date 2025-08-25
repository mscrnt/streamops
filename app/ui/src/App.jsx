import { useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import Layout from './components/layout/Layout'
import SettingsLayout from './layouts/SettingsLayout'
import Dashboard from './pages/Dashboard'
import Assets from './pages/Assets'
import Jobs from './pages/Jobs'
import Rules from './pages/Rules'
import Drives from './pages/Drives'
import Settings from './pages/Settings'
import Wizard from './pages/Wizard'

// Settings pages
import SystemSettings from './pages/settings/SystemSettings'
import ProcessingSettings from './pages/settings/ProcessingSettings'
import StorageSettings from './pages/settings/StorageSettings'
import OBSSettings from './pages/settings/OBSSettings'
import GuardrailsSettings from './pages/settings/GuardrailsSettings'
import NotificationsSettings from './pages/settings/NotificationsSettings'
import SecuritySettings from './pages/settings/SecuritySettings'
import InterfaceSettings from './pages/settings/InterfaceSettings'
import { useApi } from './hooks/useApi'

function App() {
  const navigate = useNavigate()
  const { api } = useApi()
  
  // Check if wizard has been completed
  const { data: wizardState } = useQuery({
    queryKey: ['wizard', 'state'],
    queryFn: async () => {
      const response = await api.get('/wizard/state')
      return response.data
    }
  })
  
  // Redirect to wizard if not completed
  useEffect(() => {
    if (wizardState && !wizardState.completed) {
      navigate('/wizard')
    }
  }, [wizardState, navigate])
  
  return (
    <Routes>
      <Route path="/wizard" element={<Wizard />} />
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="assets" element={<Assets />} />
        <Route path="jobs" element={<Jobs />} />
        <Route path="rules" element={<Rules />} />
        <Route path="drives" element={<Drives />} />
        <Route path="settings" element={<SettingsLayout />}>
          <Route index element={<Navigate to="/settings/system" replace />} />
          <Route path="system" element={<SystemSettings />} />
          <Route path="processing" element={<ProcessingSettings />} />
          <Route path="storage" element={<StorageSettings />} />
          <Route path="obs" element={<OBSSettings />} />
          <Route path="guardrails" element={<GuardrailsSettings />} />
          <Route path="notifications" element={<NotificationsSettings />} />
          <Route path="security" element={<SecuritySettings />} />
          <Route path="interface" element={<InterfaceSettings />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App