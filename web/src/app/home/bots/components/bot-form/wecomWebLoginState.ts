export type WecomWebLoginPanelState =
  | 'checking'
  | 'generating'
  | 'qrcode'
  | 'ready'
  | 'error';

export interface ResolveWecomWebLoginUiStateParams {
  hasLoadedState: boolean;
  loginRequired: boolean;
  loginQrImageBase64: string | null;
  loginQrLoadError: string | null;
}

export interface WecomWebLoginUiState {
  panelState: WecomWebLoginPanelState;
  qrImageBase64: string | null;
  shouldPoll: boolean;
}

export function resolveWecomWebLoginUiState({
  hasLoadedState,
  loginRequired,
  loginQrImageBase64,
  loginQrLoadError,
}: ResolveWecomWebLoginUiStateParams): WecomWebLoginUiState {
  if (loginQrLoadError) {
    return {
      panelState: 'error',
      qrImageBase64: null,
      shouldPoll: true,
    };
  }

  if (!hasLoadedState) {
    return {
      panelState: 'checking',
      qrImageBase64: null,
      shouldPoll: true,
    };
  }

  if (loginRequired) {
    if (loginQrImageBase64) {
      return {
        panelState: 'qrcode',
        qrImageBase64: loginQrImageBase64,
        shouldPoll: true,
      };
    }

    return {
      panelState: 'generating',
      qrImageBase64: null,
      shouldPoll: true,
    };
  }

  return {
    panelState: 'ready',
    qrImageBase64: null,
    shouldPoll: true,
  };
}
