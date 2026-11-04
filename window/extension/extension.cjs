exports.activate = async context => {
  const vscode = require('vscode');
  const { activate } = await import('./src/extension.mjs');
  return activate(vscode, context);
};
