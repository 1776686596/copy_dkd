import { AlertCircle, RefreshCw } from 'lucide-react';
import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { isRecoverableDynamicImportError } from '@/app/utils/lazyImportRecovery';

function getErrorMessage(error: unknown) {
  if (isRouteErrorResponse(error)) {
    return error.data?.message || error.statusText;
  }

  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === 'string') {
    return error;
  }

  return '出现了未预期的错误，请稍后重试。';
}

export default function RouteErrorBoundary() {
  const error = useRouteError();
  const isChunkLoadError = isRecoverableDynamicImportError(error);
  const title = isChunkLoadError ? '页面资源已更新' : '页面加载失败';
  const description = isChunkLoadError
    ? '当前页面仍在使用旧版本资源。刷新后会重新加载最新页面文件。'
    : '应用暂时无法完成本次页面渲染，你可以先刷新重试。';

  return (
    <div className="bg-muted/20 flex min-h-screen items-center justify-center px-4 py-10">
      <Card className="w-full max-w-xl shadow-sm">
        <CardHeader className="space-y-3">
          <CardTitle className="flex items-center gap-2 text-xl">
            <AlertCircle className="text-[#2288ee]" />
            {title}
          </CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <Alert variant={isChunkLoadError ? 'default' : 'destructive'}>
            <AlertCircle />
            <AlertTitle>错误详情</AlertTitle>
            <AlertDescription>{getErrorMessage(error)}</AlertDescription>
          </Alert>
        </CardContent>
        <CardFooter className="flex flex-wrap gap-3">
          <Button onClick={() => window.location.reload()}>
            <RefreshCw />
            立即刷新
          </Button>
          <Button variant="outline" asChild>
            <Link to="/">返回首页</Link>
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
