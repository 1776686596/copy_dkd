import test from 'node:test';
import assert from 'node:assert/strict';

import { resolveWecomWebLoginUiState } from './wecomWebLoginState';

test('keeps polling while initial login state is still loading', () => {
  const state = resolveWecomWebLoginUiState({
    hasLoadedState: false,
    botEnabled: true,
    loginStateChecked: false,
    loginRequired: false,
    loginQrImageBase64: null,
    loginQrLoadError: null,
  });

  assert.deepEqual(state, {
    panelState: 'checking',
    qrImageBase64: null,
    qrImageSrc: null,
    shouldPoll: true,
  });
});

test('keeps polling while login is required but qr image is not ready yet', () => {
  const state = resolveWecomWebLoginUiState({
    hasLoadedState: true,
    botEnabled: true,
    loginStateChecked: true,
    loginRequired: true,
    loginQrImageBase64: null,
    loginQrLoadError: null,
  });

  assert.deepEqual(state, {
    panelState: 'generating',
    qrImageBase64: null,
    qrImageSrc: null,
    shouldPoll: true,
  });
});

test('shows qr image when login runtime already has one', () => {
  const state = resolveWecomWebLoginUiState({
    hasLoadedState: true,
    botEnabled: true,
    loginStateChecked: true,
    loginRequired: true,
    loginQrImageBase64: 'qr-base64',
    loginQrLoadError: null,
  });

  assert.deepEqual(state, {
    panelState: 'qrcode',
    qrImageBase64: 'qr-base64',
    qrImageSrc: 'data:image/png;base64,qr-base64',
    shouldPoll: true,
  });
});

test('shows ready state after login is restored', () => {
  const state = resolveWecomWebLoginUiState({
    hasLoadedState: true,
    botEnabled: true,
    loginStateChecked: true,
    loginRequired: false,
    loginQrImageBase64: null,
    loginQrLoadError: null,
  });

  assert.deepEqual(state, {
    panelState: 'ready',
    qrImageBase64: null,
    qrImageSrc: null,
    shouldPoll: true,
  });
});

test('surfaces load errors without stopping polling', () => {
  const state = resolveWecomWebLoginUiState({
    hasLoadedState: true,
    botEnabled: true,
    loginStateChecked: false,
    loginRequired: false,
    loginQrImageBase64: null,
    loginQrLoadError: 'failed',
  });

  assert.deepEqual(state, {
    panelState: 'error',
    qrImageBase64: null,
    qrImageSrc: null,
    shouldPoll: true,
  });
});

test('shows checking state until backend has actually checked login status', () => {
  const state = resolveWecomWebLoginUiState({
    hasLoadedState: true,
    botEnabled: true,
    loginStateChecked: false,
    loginRequired: false,
    loginQrImageBase64: null,
    loginQrLoadError: null,
  });

  assert.deepEqual(state, {
    panelState: 'checking',
    qrImageBase64: null,
    qrImageSrc: null,
    shouldPoll: true,
  });
});

test('shows disabled state for bots that are not enabled yet', () => {
  const state = resolveWecomWebLoginUiState({
    hasLoadedState: true,
    botEnabled: false,
    loginStateChecked: false,
    loginRequired: false,
    loginQrImageBase64: null,
    loginQrLoadError: null,
  });

  assert.deepEqual(state, {
    panelState: 'disabled',
    qrImageBase64: null,
    qrImageSrc: null,
    shouldPoll: false,
  });
});
