const SECRET_KEY = import.meta.env.VITE_ENCRYPTION_KEY || 'OpenShorts-Static-Salt-Change-Me';
const ENCRYPTION_PREFIX = 'ENC:';

function xorString(text) {
  return text
    .split('')
    .map((c, i) => String.fromCodePoint(c.codePointAt(0) ^ SECRET_KEY.codePointAt(i % SECRET_KEY.length)))
    .join('');
}

export function encrypt(text) {
  if (!text) return '';
  return `${ENCRYPTION_PREFIX}${btoa(xorString(text))}`;
}

export function decrypt(text) {
  if (!text) return '';
  if (!text.startsWith(ENCRYPTION_PREFIX)) return text;

  try {
    return xorString(atob(text.slice(ENCRYPTION_PREFIX.length)));
  } catch {
    return '';
  }
}

