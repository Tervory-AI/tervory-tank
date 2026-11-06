process.once('message', async ({ service, account, method, value }) => {
  try {
    if (!['getPassword', 'setPassword', 'deletePassword'].includes(method)) throw new Error();
    const { Entry } = await import('@napi-rs/keyring');
    const entry = new Entry(service, account, { linux: { store: 'secret-service' } });
    const result = method === 'setPassword' ? entry.setPassword(value) : entry[method]();
    process.send?.({ ok: true, value: result });
  } catch { process.send?.({ ok: false }); }
});
