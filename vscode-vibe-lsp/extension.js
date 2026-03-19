const path = require('path');
const { workspace } = require('vscode');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

let client;

function activate(context) {
  const cmd = workspace.getConfiguration('vibe').get('lspCommand') || 'vibec';
  const args = workspace.getConfiguration('vibe').get('lspArgs') || ['lsp'];

  const serverOptions = {
    command: cmd,
    args,
    transport: TransportKind.stdio,
  };

  const clientOptions = {
    documentSelector: [{ scheme: 'file', language: 'vibe' }],
  };

  client = new LanguageClient('vibe-lsp', 'Vibe LSP', serverOptions, clientOptions);
  context.subscriptions.push(client.start());
}

function deactivate() {
  if (!client) return undefined;
  return client.stop();
}

module.exports = { activate, deactivate };
