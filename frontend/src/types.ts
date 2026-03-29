export type AnalyzeResponse = {
  verse: string
  syllables: { text: string; type: 'laghu' | 'guru'; duration: 1 | 2; pitch: number }[]
  chandas: string
  detected_meter?: string
  pattern: string
  chant_sequence: { phoneme: string; duration: number; pitch: number }[]
}

export type EasyMeter = 'Anushtubh' | 'Indravajra' | 'Mandakranta' | 'Shardulavikridita'

export type TTSProvider = 'edge' | 'openai'
export type TTSFormat = 'mp3' | 'wav' | 'opus' | 'flac' | 'pcm'
