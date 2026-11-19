export async function call(method, ...args) {
  const bridge = window.pywebview?.api;
  if (!bridge?.[method]) throw new Error('Peak Clip todavía no está conectado.');
  return bridge[method](...args);
}
