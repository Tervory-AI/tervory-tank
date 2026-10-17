// Lets node --experimental-strip-types load the Base page's extensionless TypeScript imports.
export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("./") || specifier.startsWith("../")) {
    const hasExtension = /\.(tsx?|jsx?|json|css|mjs|cjs)$/.test(specifier);
    if (!hasExtension) {
      for (const extension of [".ts", ".tsx"]) {
        try {
          return await nextResolve(specifier + extension, context);
        } catch {
          // Try the next extension.
        }
      }
    }
  }
  return nextResolve(specifier, context);
}
