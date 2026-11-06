"use client";

export default function ErrorState({reset}: {reset: () => void}) {
  return <section role="alert"><h1>This item is unavailable.</h1><p>The request could not be completed. Please try again.</p><button onClick={reset}>Try again</button></section>;
}
