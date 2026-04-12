import React, { Suspense, lazy } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';

// Layouts
import LoginLayout from '@/app/login/layout';
import RegisterLayout from '@/app/register/layout';
import ResetPasswordLayout from '@/app/reset-password/layout';
import HomeLayout from '@/app/home/layout';

// Pages
const LoginPage = lazy(() => import('@/app/login/page'));
const RegisterPage = lazy(() => import('@/app/register/page'));
const ResetPasswordPage = lazy(() => import('@/app/reset-password/page'));
const WizardPage = lazy(() => import('@/app/wizard/page'));
const SpaceCallbackPage = lazy(() => import('@/app/auth/space/callback/page'));
const HomePage = lazy(() => import('@/app/home/page'));
const MonitoringPage = lazy(() => import('@/app/home/monitoring/page'));
const ServiceDeskPage = lazy(() => import('@/app/home/service-desk/page'));
const BotsPage = lazy(() => import('@/app/home/bots/page'));
const PipelinesPage = lazy(() => import('@/app/home/pipelines/page'));
const PluginsPage = lazy(() => import('@/app/home/plugins/page'));
const MarketPage = lazy(() => import('@/app/home/market/page'));
const MCPPage = lazy(() => import('@/app/home/mcp/page'));
const KnowledgePage = lazy(() => import('@/app/home/knowledge/page'));

const Loading = () => <div>Loading...</div>;

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/login" replace />,
  },
  {
    path: '/login',
    element: (
      <Suspense fallback={<Loading />}>
        <LoginLayout>
          <LoginPage />
        </LoginLayout>
      </Suspense>
    ),
  },
  {
    path: '/register',
    element: (
      <Suspense fallback={<Loading />}>
        <RegisterLayout>
          <RegisterPage />
        </RegisterLayout>
      </Suspense>
    ),
  },
  {
    path: '/reset-password',
    element: (
      <Suspense fallback={<Loading />}>
        <ResetPasswordLayout>
          <ResetPasswordPage />
        </ResetPasswordLayout>
      </Suspense>
    ),
  },
  {
    path: '/wizard',
    element: (
      <Suspense fallback={<Loading />}>
        <WizardPage />
      </Suspense>
    ),
  },
  {
    path: '/auth/space/callback',
    element: (
      <Suspense fallback={<Loading />}>
        <SpaceCallbackPage />
      </Suspense>
    ),
  },
  {
    path: '/home',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <HomePage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/monitoring',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <MonitoringPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/service-desk',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <ServiceDeskPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/bots',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <BotsPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/pipelines',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <PipelinesPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/plugins',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <PluginsPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/market',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <MarketPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/mcp',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <MCPPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/knowledge',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <KnowledgePage />
        </HomeLayout>
      </Suspense>
    ),
  },
]);
