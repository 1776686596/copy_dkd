export type LoginPageAccountType = 'local' | 'space' | null;

export interface LoginPageModeInput {
  accountType: LoginPageAccountType;
  hasPassword: boolean;
  demoLoginKeyEnabled: boolean;
}

export interface LoginPageMode {
  showSpaceLogin: boolean;
  showPasswordLogin: boolean;
  showDemoKeyLogin: boolean;
}

export function resolveLoginPageMode({
  accountType,
  hasPassword,
  demoLoginKeyEnabled,
}: LoginPageModeInput): LoginPageMode {
  const showDemoKeyLogin = demoLoginKeyEnabled;
  const showSpaceLogin = accountType === 'space';
  const showPasswordLogin =
    accountType === 'local' || (accountType === 'space' && hasPassword);

  return {
    showSpaceLogin,
    showPasswordLogin,
    showDemoKeyLogin,
  };
}
