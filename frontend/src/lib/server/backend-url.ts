function normalizeBaseUrl(value: string) {
  return value.trim().replace(/\/$/, "");
}

function pickFirstNonEmpty(values: Array<string | undefined>) {
  for (const value of values) {
    if (value && value.trim()) {
      return normalizeBaseUrl(value);
    }
  }
  return "";
}

export function getBackendInternalBaseUrl(context: string) {
  const resolved = pickFirstNonEmpty([
    process.env.BACKEND_INTERNAL_BASE_URL,
    process.env.API_BASE_URL,
    process.env.NEXT_PUBLIC_API_BASE_URL,
  ]);

  if (!resolved) {
    throw new Error(
      `Missing backend internal URL for ${context}. Set BACKEND_INTERNAL_BASE_URL (preferred) or API_BASE_URL.`,
    );
  }

  return resolved;
}

export function getBackendPublicBaseUrl(context: string) {
  const resolved = pickFirstNonEmpty([
    process.env.BACKEND_PUBLIC_BASE_URL,
    process.env.API_BASE_URL,
    process.env.NEXT_PUBLIC_API_BASE_URL,
  ]);

  if (!resolved) {
    throw new Error(
      `Missing backend public URL for ${context}. Set BACKEND_PUBLIC_BASE_URL (preferred) or API_BASE_URL.`,
    );
  }

  return resolved;
}

export function toWebSocketBaseUrl(httpBaseUrl: string) {
  const normalized = normalizeBaseUrl(httpBaseUrl);
  if (normalized.startsWith("https://")) {
    return `wss://${normalized.slice("https://".length)}`;
  }
  if (normalized.startsWith("http://")) {
    return `ws://${normalized.slice("http://".length)}`;
  }
  return normalized;
}
