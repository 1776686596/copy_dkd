import React, { ComponentType, Suspense, lazy } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import RouteErrorBoundary from '@/app/RouteErrorBoundary';
import { createRecoverableLazyImport } from '@/app/utils/lazyImportRecovery';

// Layouts
import LoginLayout from '@/app/login/layout';
import RegisterLayout from '@/app/register/layout';
import ResetPasswordLayout from '@/app/reset-password/layout';
import HomeLayout from '@/app/home/layout';

// Pages
const lazyPage = <TComponent extends ComponentType<any>>(
  routeKey: string,
  importer: () => Promise<{ default: TComponent }>,
) => lazy(createRecoverableLazyImport(importer, routeKey));

const LoginPage = lazyPage('login-page', () => import('@/app/login/page'));
const RegisterPage = lazyPage(
  'register-page',
  () => import('@/app/register/page'),
);
const ResetPasswordPage = lazyPage(
  'reset-password-page',
  () => import('@/app/reset-password/page'),
);
const WizardPage = lazyPage('wizard-page', () => import('@/app/wizard/page'));
const SpaceCallbackPage = lazyPage(
  'space-callback-page',
  () => import('@/app/auth/space/callback/page'),
);
const HomePage = lazyPage('home-page', () => import('@/app/home/page'));
const MonitoringPage = lazyPage(
  'monitoring-page',
  () => import('@/app/home/monitoring/page'),
);
const ServiceDeskPage = lazyPage(
  'service-desk-page',
  () => import('@/app/home/service-desk/page'),
);
const BotsPage = lazyPage('bots-page', () => import('@/app/home/bots/page'));
const PipelinesPage = lazyPage(
  'pipelines-page',
  () => import('@/app/home/pipelines/page'),
);
const PluginsPage = lazyPage(
  'plugins-page',
  () => import('@/app/home/plugins/page'),
);
const MarketPage = lazyPage(
  'market-page',
  () => import('@/app/home/market/page'),
);
const MCPPage = lazyPage('mcp-page', () => import('@/app/home/mcp/page'));
const KnowledgePage = lazyPage(
  'knowledge-page',
  () => import('@/app/home/knowledge/page'),
);

const Loading = () => <div>Loading...</div>;
const errorElement = <RouteErrorBoundary />;

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/login" replace />,
    errorElement,
  },
  {
    path: '/login',
    errorElement,
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
    errorElement,
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
    errorElement,
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
    errorElement,
    element: (
      <Suspense fallback={<Loading />}>
        <WizardPage />
      </Suspense>
    ),
  },
  {
    path: '/auth/space/callback',
    errorElement,
    element: (
      <Suspense fallback={<Loading />}>
        <SpaceCallbackPage />
      </Suspense>
    ),
  },
  {
    path: '/home',
    errorElement,
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
    errorElement,
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
    errorElement,
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
    errorElement,
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
    errorElement,
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
    errorElement,
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
    errorElement,
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
    errorElement,
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
    errorElement,
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <KnowledgePage />
        </HomeLayout>
      </Suspense>
    ),
  },
]);
