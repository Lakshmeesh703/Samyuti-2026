import { useEffect, useMemo, useState } from 'react'
import { AudioVisualizer } from './components/AudioVisualizer'
import { Card } from './components/ui/Card'
import { GradientButton } from './components/ui/GradientButton'
import { Toast } from './components/ui/Toast'
import { analyzeVerse, generateChant, generateTTS } from './lib/api'
import type { AnalyzeResponse, EasyMeter } from './types'

const DEFAULT_VERSE = `योगस्थः कुरु कर्माणि सङ्गं त्यक्त्वा धनञ्जय ।
सिद्ध्यसिद्ध्योः समो भूत्वा समत्वं योग उच्यते ॥`

const DEFAULT_BACKEND_URL = (import.meta as any).env?.VITE_BACKEND_URL || 'http://localhost:8000'

const RAGA_OPTIONS = [
  { value: 'shanti', label: 'Shanti - Hamsadhwani style' },
  { value: 'meditative', label: 'Meditative · Yaman style' },
  { value: 'devotional', label: 'Devotional · Bhairavi style' },
] as const

const EDGE_VOICE_PRESETS = {
  male: 'hi-IN-MadhurNeural',
  female: 'hi-IN-SwaraNeural',
} as const

const EASY_METERS: EasyMeter[] = ['Anushtubh', 'Indravajra', 'Mandakranta', 'Shardulavikridita']

export default function App() {
  const [verse, setVerse] = useState(DEFAULT_VERSE)
  const [raga, setRaga] = useState<(typeof RAGA_OPTIONS)[number]['value']>('shanti')
  const [preferredMeter, setPreferredMeter] = useState<'auto' | EasyMeter>('auto')
  const [voiceStyle, setVoiceStyle] = useState<'male' | 'female' | 'custom'>('male')
  const [ttsVoice, setTtsVoice] = useState('hi-IN-MadhurNeural')

  const [jsonText, setJsonText] = useState<string>('')
  const [jsonCopyText, setJsonCopyText] = useState<string>('')
  const [detectedMeter, setDetectedMeter] = useState<string>('')
  const [audioUrl, setAudioUrl] = useState<string>('')
  const [audioFileName, setAudioFileName] = useState('audio.wav')
  const [isPlaying, setIsPlaying] = useState(false)

  const [busyAction, setBusyAction] = useState<'analyze' | 'chant' | 'tts' | null>(null)
  const [toast, setToast] = useState<{ type: 'error' | 'success' | 'info'; message: string } | null>(null)

  const canRun = useMemo(() => verse.trim().length > 0, [verse])
  const busy = busyAction !== null

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl)
    }
  }, [audioUrl])

  useEffect(() => {
    if (voiceStyle === 'custom') return
    setTtsVoice(EDGE_VOICE_PRESETS[voiceStyle])
  }, [voiceStyle])

  function clearAudio() {
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioUrl('')
    setAudioFileName('audio.wav')
    setIsPlaying(false)
  }

  function notify(type: 'error' | 'success' | 'info', message: string) {
    setToast({ type, message })
  }

  async function copyJson() {
    if (!jsonCopyText) return
    await navigator.clipboard.writeText(jsonCopyText)
    notify('success', 'JSON copied to clipboard')
  }

  async function onAnalyze() {
    setBusyAction('analyze')
    setToast(null)
    clearAudio()
    try {
      const data: AnalyzeResponse = await analyzeVerse(DEFAULT_BACKEND_URL, {
        verse,
        meterOptions: EASY_METERS,
        preferredMeter: preferredMeter === 'auto' ? undefined : preferredMeter,
      })
      const prettyJson = JSON.stringify(data, null, 2)
      // Keep copy JSON valid, but show verse line breaks naturally in the UI.
      setJsonCopyText(prettyJson)
      setJsonText(prettyJson.replace(/\\n/g, '\n'))
      const meter = data.detected_meter || data.chandas
      setDetectedMeter(meter)
      notify('success', `Analyzed successfully · ${meter}`)
    } catch (e: any) {
      notify('error', e?.message ?? String(e))
    } finally {
      setBusyAction(null)
    }
  }

  async function onChant() {
    setBusyAction('chant')
    setToast(null)
    try {
      const blob = await generateChant(DEFAULT_BACKEND_URL, {
        verse,
        raga,
        preferredMeter: preferredMeter === 'auto' ? undefined : preferredMeter,
      })
      const url = URL.createObjectURL(blob)
      clearAudio()
      setAudioUrl(url)
      setAudioFileName(`chant-${raga}.wav`)
      notify('success', `Raga chanting audio generated${preferredMeter === 'auto' ? '' : ` · ${preferredMeter} rhythm`}`)
    } catch (e: any) {
      notify('error', e?.message ?? String(e))
    } finally {
      setBusyAction(null)
    }
  }

  async function onTTS() {
    setBusyAction('tts')
    setToast(null)
    try {
      const blob = await generateTTS(DEFAULT_BACKEND_URL, {
        verse,
        provider: 'edge',
        voice: ttsVoice,
        pitch: '+0Hz',
        raga,
        model: 'gpt-4o-mini-tts',
        format: 'mp3',
      })
      const url = URL.createObjectURL(blob)
      clearAudio()
      setAudioUrl(url)
      setAudioFileName('tts.mp3')
      notify('success', 'Speech TTS generated')
    } catch (e: any) {
      notify('error', e?.message ?? String(e))
    } finally {
      setBusyAction(null)
    }
  }

  return (
    <div className="relative min-h-screen bg-aurora px-4 pb-24 pt-8 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute inset-0 mesh-overlay" />
      <div className="pointer-events-none absolute -left-24 top-10 h-56 w-56 rounded-full bg-saffron/20 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 top-16 h-64 w-64 rounded-full bg-violetDeep/25 blur-3xl" />

      <div className="relative mx-auto max-w-7xl">
        <header className="mb-6 text-center animate-fadeUp">
          <h1 className="gradient-text text-4xl font-black tracking-tight sm:text-5xl">BharathAI Chant Engine</h1>
          <p className="mx-auto mt-2 max-w-3xl text-sm text-slate-300 sm:text-base">
            Musically guided, phonetically tuned Sanskrit recitation with AI-assisted chanting.
          </p>
        </header>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card
            title="Input & Chanting Controls"
            subtitle="Enter Sanskrit verse, choose raga, and generate premium chant audio."
            className="space-y-4"
          >
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-widest text-slate-300">Sanskrit Verse</label>
              <textarea
                value={verse}
                onChange={(e) => setVerse(e.target.value)}
                rows={8}
                className="font-sanskrit w-full rounded-xl border border-white/20 bg-black/20 px-3 py-2 text-base text-slate-100 outline-none transition focus:border-gold/70"
              />
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">Raga</label>
                <select
                  value={raga}
                  onChange={(e) => setRaga(e.target.value as any)}
                  className="select-themed mt-1 w-full rounded-xl border border-white/20 bg-white/5 px-3 py-2 text-sm text-slate-100 outline-none focus:border-saffron/70"
                >
                  {RAGA_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">Meter</label>
                <select
                  value={preferredMeter}
                  onChange={(e) => setPreferredMeter(e.target.value as 'auto' | EasyMeter)}
                  className="select-themed mt-1 w-full rounded-xl border border-white/20 bg-white/5 px-3 py-2 text-sm text-slate-100 outline-none focus:border-saffron/70"
                >
                  <option value="auto">Auto Detect</option>
                  {EASY_METERS.map((meter) => (
                    <option key={meter} value={meter}>
                      {meter}
                    </option>
                  ))}
                </select>
              </div>

            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">Voice Style</label>
                <select
                  value={voiceStyle}
                  onChange={(e) => setVoiceStyle(e.target.value as 'male' | 'female' | 'custom')}
                  className="select-themed mt-1 w-full rounded-xl border border-white/20 bg-white/5 px-3 py-2 text-sm text-slate-100 outline-none focus:border-saffron/70"
                >
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="custom">Custom</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">Voice ID</label>
                <input
                  value={ttsVoice}
                  onChange={(e) => {
                    setVoiceStyle('custom')
                    setTtsVoice(e.target.value)
                  }}
                  className="mt-1 w-full rounded-xl border border-white/20 bg-white/5 px-3 py-2 text-sm text-slate-100 outline-none focus:border-saffron/70"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <GradientButton onClick={onAnalyze} disabled={!canRun} busy={busyAction === 'analyze'}>
                Analyze → JSON
              </GradientButton>
              <GradientButton onClick={onChant} disabled={!canRun} busy={busyAction === 'chant'}>
                Generate Chant Audio
              </GradientButton>
              <GradientButton onClick={onTTS} disabled={!canRun} busy={busyAction === 'tts'}>
                Generate Speech TTS
              </GradientButton>
            </div>

            {busy ? (
              <div className="flex items-center gap-2 rounded-xl border border-gold/30 bg-gold/10 px-3 py-2 text-sm text-gold animate-pulseGlow">
                <span className="h-2.5 w-2.5 rounded-full bg-gold" /> Chanting in progress…
              </div>
            ) : null}
          </Card>

          <div className="space-y-5">
            <Card title="Audio Output" subtitle="Waveform-like bars animate during playback." className="space-y-4">
              <div className="rounded-xl border border-white/10 bg-black/25 p-3">
                <AudioVisualizer active={isPlaying} />
                <audio
                  className="mt-3 w-full rounded-lg"
                  controls
                  src={audioUrl || undefined}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  onEnded={() => setIsPlaying(false)}
                />
              </div>

              <a
                href={audioUrl || '#'}
                download={audioFileName}
                className={`inline-flex rounded-xl border px-4 py-2 text-sm font-medium transition ${
                  audioUrl
                    ? 'border-saffron/50 bg-saffron/10 text-saffron hover:bg-saffron/20'
                    : 'pointer-events-none border-white/10 bg-white/5 text-slate-500'
                }`}
              >
                Download {audioFileName}
              </a>
            </Card>

            <Card title="Detected Meter" subtitle="Best matching meter.">
              <div className="rounded-xl border border-saffron/35 bg-saffron/10 px-4 py-3 text-saffron">
                <div className="text-xs uppercase tracking-wider text-saffron/80">Shloka Meter</div>
                <div className="mt-1 text-xl font-semibold">
                  {detectedMeter || 'Run Analyze to detect meter'}
                </div>
              </div>
            </Card>

            <Card title="Analysis JSON" subtitle="Copy structured output for model/debug usage.">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs uppercase tracking-wider text-slate-400">Output</span>
                <button
                  onClick={copyJson}
                  disabled={!jsonCopyText}
                  className="rounded-lg border border-white/15 bg-white/10 px-3 py-1.5 text-xs text-slate-200 transition hover:bg-white/20 disabled:opacity-40"
                >
                  Copy JSON
                </button>
              </div>
              <textarea
                value={jsonText}
                readOnly
                rows={18}
                className="scroll-thin w-full rounded-xl border border-white/10 bg-black/30 p-3 font-mono text-xs text-slate-100 outline-none transition focus:border-saffron/40"
              />
            </Card>
          </div>
        </div>
      </div>

      <footer className="fixed bottom-2 left-1/2 z-40 -translate-x-1/2 rounded-full border border-gold/25 bg-indigoDeep/55 px-4 py-1.5 text-xs text-gold shadow-glow backdrop-blur">
        Powered by BharathAI
      </footer>

      {toast ? <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} /> : null}
    </div>
  )
}
