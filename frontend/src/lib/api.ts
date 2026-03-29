import type { AnalyzeResponse, EasyMeter, TTSFormat, TTSProvider } from '../types'

const endpointMap = {
  analyze: ['/analyze', '/api/analyze'],
  chant: ['/chant', '/api/synthesize'],
  tts: ['/tts', '/api/tts'],
} as const

function normalizeBaseUrl(input: string): string {
  return input.trim().replace(/\/$/, '')
}

async function callWithFallback(
  baseUrl: string,
  paths: readonly string[],
  payload: unknown,
): Promise<Response> {
  const root = normalizeBaseUrl(baseUrl)
  let lastErrorText = 'Endpoint not reachable'

  for (const path of paths) {
    const res = await fetch(`${root}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (res.ok) return res

    const text = await res.text()
    lastErrorText = `${path} failed (${res.status}): ${text}`

    if (res.status !== 404) {
      throw new Error(lastErrorText)
    }
  }

  throw new Error(lastErrorText)
}

export async function analyzeVerse(
  baseUrl: string,
  payload: {
    verse: string
    meterOptions: EasyMeter[]
    preferredMeter?: EasyMeter
  },
): Promise<AnalyzeResponse> {
  const res = await callWithFallback(baseUrl, endpointMap.analyze, {
    verse: payload.verse,
    meter_options: payload.meterOptions,
    preferred_meter: payload.preferredMeter,
  })
  return (await res.json()) as AnalyzeResponse
}

export async function generateChant(baseUrl: string, payload: {
  verse: string
  raga: 'shanti' | 'meditative' | 'devotional'
  preferredMeter?: EasyMeter
}): Promise<Blob> {
  const res = await callWithFallback(baseUrl, endpointMap.chant, {
    verse: payload.verse,
    options: {
      unit_seconds: 0.24,
      base_freq_hz: 174,
      glide_ms: 58,
      brightness: 0.62,
      raga: payload.raga,
      preferred_meter: payload.preferredMeter,
      include_drone: true,
      temple_reverb: 0.24,
      bell_at_edges: true,
    },
  })
  return await res.blob()
}

export async function generateTTS(baseUrl: string, payload: {
  verse: string
  provider: TTSProvider
  voice: string
  pitch: string
  raga: 'shanti' | 'meditative' | 'devotional'
  model: string
  format: TTSFormat
}): Promise<Blob> {
  const res = await callWithFallback(baseUrl, endpointMap.tts, {
    verse: payload.verse,
    options: {
      provider: payload.provider,
      voice: payload.voice,
      rate: '-18%',
      pitch: payload.pitch,
      raga: payload.raga,
      model: payload.model,
      audio_format: payload.format,
      prefer_devanagari: true,
      chant_mode: true,
    },
  })

  return await res.blob()
}
