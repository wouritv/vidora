const SECRET_KEY = import.meta.env.VITE_ENCRYPTION_KEY || 'OpenShorts-Static-Salt-Change-Me';
const ENCRYPTION_PREFIX = 'ENC:';

function xorBytes(bytes) {
  return bytes.map((b, i) => b ^ (SECRET_KEY.codePointAt(i % SECRET_KEY.length) & 0xff));
}

export function encrypt(text) {
  if (!text) return '';
  const bytes = Array.from(new TextEncoder().encode(text));
  const xored = xorBytes(bytes);
  return `${ENCRYPTION_PREFIX}${btoa(String.fromCharCode(...xored))}`;
}

export function decrypt(text) {
  if (!text) return '';
  if (!text.startsWith(ENCRYPTION_PREFIX)) return text;

  try {
    const decoded = atob(text.slice(ENCRYPTION_PREFIX.length));
    const bytes = Array.from(decoded, c => c.charCodeAt(0));
    const xored = xorBytes(bytes);
    return new TextDecoder().decode(new Uint8Array(xored));
  } catch {
    return '';
  }
}
