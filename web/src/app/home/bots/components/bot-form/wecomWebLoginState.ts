export type WecomWebLoginPanelState =
  | 'disabled'
  | 'checking'
  | 'generating'
  | 'qrcode'
  | 'ready'
  | 'error';

export interface ResolveWecomWebLoginUiStateParams {
  hasLoadedState: boolean;
  botEnabled: boolean;
  loginStateChecked: boolean;
  loginRequired: boolean;
  loginQrImageBase64: string | null;
  loginQrLoadError: string | null;
}

export interface WecomWebLoginUiState {
  panelState: WecomWebLoginPanelState;
  qrImageBase64: string | null;
  qrImageSrc: string | null;
  shouldPoll: boolean;
}

function buildWecomWebLoginImageSrc(imageBase64: string | null): string | null {
  return imageBase64 ? `data:image/png;base64,${imageBase64}` : null;
}

export function resolveWecomWebLoginUiState({
  hasLoadedState,
  botEnabled,
  loginStateChecked,
  loginRequired,
  loginQrImageBase64,
  loginQrLoadError,
}: ResolveWecomWebLoginUiStateParams): WecomWebLoginUiState {
  if (!botEnabled) {
    return {
      panelState: 'disabled',
      qrImageBase64: null,
      qrImageSrc: null,
      shouldPoll: false,
    };
  }

  if (loginQrLoadError) {
    return {
      panelState: 'error',
      qrImageBase64: null,
      qrImageSrc: null,
      shouldPoll: true,
    };
  }

  if (!hasLoadedState || !loginStateChecked) {
    return {
      panelState: 'checking',
      qrImageBase64: null,
      qrImageSrc: null,
      shouldPoll: true,
    };
  }

  if (loginRequired) {
    if (loginQrImageBase64) {
      return {
        panelState: 'qrcode',
        qrImageBase64: loginQrImageBase64,
        qrImageSrc: buildWecomWebLoginImageSrc(loginQrImageBase64),
        shouldPoll: true,
      };
    }

    return {
      panelState: 'generating',
      qrImageBase64: null,
      qrImageSrc: null,
      shouldPoll: true,
    };
  }

  return {
    panelState: 'ready',
    qrImageBase64: null,
    qrImageSrc: null,
    shouldPoll: true,
  };
}
