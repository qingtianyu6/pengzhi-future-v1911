/* eslint-disable react-refresh/only-export-components -- route modules export configuration and local route elements. */
import { lazy, Suspense, type ReactNode } from 'react'
import { Spin } from 'antd'
import { Navigate, createBrowserRouter, useLocation } from 'react-router-dom'
import RouteError from '../components/RouteError'
import { AppLayout } from '../layouts/AppLayout'
import { SiteLayout } from '../layouts/SiteLayout'
import { getStoredToken } from '../api/authApi'
import { enterGuestMode, isGuestMode } from '../api/guestMode'

const LandingPage = lazy(() => import('../pages/LandingPage'))
const TechHighlightsPage = lazy(() => import('../pages/TechHighlightsPage'))
const ApplicationScenariosPage = lazy(() => import('../pages/ApplicationScenariosPage'))
const CoreFunctionsPage = lazy(() => import('../pages/CoreFunctionsPage'))
const PlatformIntroductionPage = lazy(() => import('../pages/PlatformIntroductionPage'))
const DashboardPage = lazy(() => import('../pages/Dashboard/DashboardPage'))
const DataCenterPage = lazy(() => import('../pages/DataCenterPage'))
const Greenhouse3DPage = lazy(() => import('../features/greenhouse3d/Greenhouse3DPage'))
const EnvironmentAnalysisPage = lazy(() => import('../pages/EnvironmentAnalysisPage'))
const DiagnosisPage = lazy(() => import('../pages/Diagnosis/DiseaseDiagnosisPage'))
const DiseaseTimeMachinePage = lazy(() => import('../pages/DiseaseTimeMachinePage'))
const ProductionDecisionPage = lazy(() => import('../pages/ProductionDecisionPage'))
const NotFoundPage = lazy(() => import('../pages/NotFound'))
const AuthPage = lazy(() => import('../pages/Auth/AuthPage'))

function withSuspense(page: ReactNode) {
  return <Suspense fallback={<div className="route-loading"><Spin /></div>}>{page}</Suspense>
}

function LegacyRedirect({ to, tab }: { to: string; tab?: string }) {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  if (tab) params.set('tab', tab)
  const query = params.toString()
  return <Navigate replace to={`${to}${query ? `?${query}` : ''}`} />
}

function ProtectedPlatform() {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  if (params.get('mode') === 'guest') enterGuestMode()
  if (!getStoredToken() && !isGuestMode()) return <Navigate replace to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} />
  return <AppLayout />
}

export const router = createBrowserRouter([
  { path: '/', element: <Navigate replace to="/home" /> },
  { path: '/login', element: withSuspense(<AuthPage />) },
  { path: '/register', element: withSuspense(<AuthPage />) },
  { path: '/', errorElement: <RouteError />, element: <SiteLayout />, children: [
    { path: 'home', element: withSuspense(<LandingPage />) },
    { path: 'introduction', element: withSuspense(<PlatformIntroductionPage />) },
    { path: 'features', element: withSuspense(<CoreFunctionsPage />) },
    { path: 'highlights', element: withSuspense(<TechHighlightsPage />) },
    { path: 'scenarios', element: withSuspense(<ApplicationScenariosPage />) },
  ] },
  // 官网上线后仍兼容此前直接收藏的工作台链接。
  { path: '/data', element: <LegacyRedirect to="/platform/data" /> },
  { path: '/3d', element: <LegacyRedirect to="/platform/3d" /> },
  { path: '/environment', element: <LegacyRedirect to="/platform/environment" /> },
  { path: '/diagnosis', element: <LegacyRedirect to="/platform/diagnosis" /> },
  { path: '/disease-time-machine', element: <LegacyRedirect to="/platform/disease-time-machine" /> },
  { path: '/production', element: <LegacyRedirect to="/platform/production" /> },
  { path: '/greenhouses', element: <LegacyRedirect to="/platform/data" /> },
  { path: '/monitoring', element: <LegacyRedirect to="/platform/environment" tab="monitoring" /> },
  { path: '/prediction', element: <LegacyRedirect to="/platform/environment" tab="prediction" /> },
  { path: '/alerts', element: <LegacyRedirect to="/platform/environment" tab="alerts" /> },
  { path: '/decision', element: <LegacyRedirect to="/platform/production" tab="decision" /> },
  { path: '/tasks', element: <LegacyRedirect to="/platform/production" tab="tasks" /> },
  { path: '/ai', element: <LegacyRedirect to="/platform" /> },
  {
    path: '/platform',
    element: <ProtectedPlatform />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: withSuspense(<DashboardPage />) },
      { path: 'data', element: withSuspense(<DataCenterPage />) },
      { path: '3d', element: withSuspense(<Greenhouse3DPage />) },
      { path: 'environment', element: withSuspense(<EnvironmentAnalysisPage />) },
      { path: 'diagnosis', element: withSuspense(<DiagnosisPage />) },
      { path: 'disease-time-machine', element: withSuspense(<DiseaseTimeMachinePage />) },
      { path: 'production', element: withSuspense(<ProductionDecisionPage />) },

      // 旧链接继续可用，统一跳转到新的工作台结构。
      { path: 'greenhouses', element: <LegacyRedirect to="/platform/data" /> },
      { path: 'monitoring', element: <LegacyRedirect to="/platform/environment" tab="monitoring" /> },
      { path: 'prediction', element: <LegacyRedirect to="/platform/environment" tab="prediction" /> },
      { path: 'alerts', element: <LegacyRedirect to="/platform/environment" tab="alerts" /> },
      { path: 'decision', element: <LegacyRedirect to="/platform/production" tab="decision" /> },
      { path: 'tasks', element: <LegacyRedirect to="/platform/production" tab="tasks" /> },
      { path: 'ai', element: <LegacyRedirect to="/platform" /> },
      { path: '*', element: withSuspense(<NotFoundPage />) },
    ],
  },
  { path: '*', element: <Navigate replace to="/" /> },
])
