import { useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Assets from './pages/Assets'
import Jobs from './pages/Jobs'
import Rules from './pages/Rules'
import Drives from './pages/Drives'
import Settings from './pages/Settings'
import Wizard from './pages/Wizard'
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
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App