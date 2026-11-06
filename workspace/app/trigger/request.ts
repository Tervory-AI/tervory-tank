export const ACTION_TIMEOUT_MS = 30_000;

export class ActionTimeout extends Error {
  constructor() { super("The action outcome is unknown. Do not repeat it until checked."); }
}

export async function waitForAction<T>(work: Promise<T>, milliseconds = ACTION_TIMEOUT_MS): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([work, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new ActionTimeout()), milliseconds);
    })]);
  } finally { clearTimeout(timer); }
}

export function clientError(error: unknown): string {
  return error instanceof ActionTimeout ? error.message : "The action could not be completed. Please try again.";
}
