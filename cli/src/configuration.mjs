// Only setting names and fixed recovery instructions enter these errors.
export class ConfigurationError extends Error {
  constructor(message, settings) {
    super(message);
    this.settings = settings;
    this.name = 'ConfigurationError';
  }
}

export function missingSetting(name, action) {
  return new ConfigurationError(`Missing setting ${name}. ${action}`, [name]);
}

export const LOGIN_SETTING = '@tervory/cli/personal-token';
export const keyringUnavailable = (operation = 'read') => new ConfigurationError(
  `Login unavailable. OS keyring entry ${LOGIN_SETTING} could not be ${operation}. Enable the OS keyring, then run tervory login.`, [LOGIN_SETTING]);
