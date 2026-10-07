const SESSION_KEY = 'morpheus-pilot-synthesis-retry-v1'

interface RetryState {
  requestIdentity: string
  idempotencyKey: string
}

let memoryState: RetryState | null = null

export async function pilotSynthesisRequestIdentity(payload: object): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(payload))
  const digest = await window.crypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(digest), (item) => item.toString(16).padStart(2, '0')).join('')
}

function freshKey(): string {
  if (typeof window.crypto.randomUUID === 'function') {
    return `web-${window.crypto.randomUUID()}`
  }
  const bytes = new Uint8Array(16)
  window.crypto.getRandomValues(bytes)
  return `web-${Array.from(bytes, (item) => item.toString(16).padStart(2, '0')).join('')}`
}

function readState(): RetryState | null {
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<RetryState>
      if (
        typeof parsed.requestIdentity === 'string'
        && /^[0-9a-f]{64}$/.test(parsed.requestIdentity)
        && typeof parsed.idempotencyKey === 'string'
        && parsed.idempotencyKey.length >= 8
        && parsed.idempotencyKey.length <= 128
      ) {
        memoryState = {
          requestIdentity: parsed.requestIdentity,
          idempotencyKey: parsed.idempotencyKey
        }
        return memoryState
      }
    }
  } catch {
    // sessionStorage can be unavailable under strict browser policy. The
    // module-level fallback still preserves retry identity for this page load.
  }
  return memoryState
}

function writeState(value: RetryState | null): void {
  memoryState = value
  try {
    if (value) window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(value))
    else window.sessionStorage.removeItem(SESSION_KEY)
  } catch {
    // Browser storage is optional; retain the in-memory fallback.
  }
}

export function pilotSynthesisIdempotencyKey(requestIdentity: string): string {
  const prior = readState()
  if (prior?.requestIdentity === requestIdentity) return prior.idempotencyKey
  const idempotencyKey = freshKey()
  writeState({ requestIdentity, idempotencyKey })
  return idempotencyKey
}

export function clearPilotSynthesisRetry(idempotencyKey: string): void {
  const current = readState()
  if (current?.idempotencyKey === idempotencyKey) writeState(null)
}
