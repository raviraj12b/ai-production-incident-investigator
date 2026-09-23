import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '../components/AppShell'
import { IncidentDetailPage } from '../pages/IncidentDetailPage'
import { IncidentsPage } from '../pages/IncidentsPage'
import { InvestigationDetailPage } from '../pages/InvestigationDetailPage'
import { NewIncidentPage } from '../pages/NewIncidentPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { RouteErrorPage } from '../pages/RouteErrorPage'

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />} errorElement={<RouteErrorPage />}>
        <Route index element={<Navigate replace to="/incidents" />} />
        <Route path="incidents" element={<IncidentsPage />} />
        <Route path="incidents/new" element={<NewIncidentPage />} />
        <Route path="incidents/:incidentId" element={<IncidentDetailPage />} />
        <Route path="investigations/:investigationId" element={<InvestigationDetailPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
