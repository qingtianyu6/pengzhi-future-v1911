import { useCallback, useEffect, useRef, useState } from 'react'

interface RecognitionResult { isFinal: boolean; length: number; [index: number]: { transcript: string } }
interface RecognitionEvent { resultIndex: number; results: ArrayLike<RecognitionResult> }
interface Recognition {
  lang: string; continuous: boolean; interimResults: boolean
  onresult: ((event: RecognitionEvent) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start(): void; stop(): void; abort(): void
}
type RecognitionConstructor = new () => Recognition
const recognitionType = () => {
  const browser = window as Window & { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor }
  return browser.SpeechRecognition ?? browser.webkitSpeechRecognition
}
const errors: Record<string, string> = {
  'not-allowed': '麦克风权限未开启，请在浏览器地址栏允许访问后重试。',
  'service-not-allowed': '浏览器未允许语音识别服务，请使用文字输入。',
  'audio-capture': '没有可用的麦克风，请检查设备连接。',
  'no-speech': '没有识别到语音，可以重试或直接输入文字。',
  network: '语音识别网络不可用，请重试或使用文字输入。',
  'language-not-supported': '当前浏览器暂不支持中文识别，请使用文字输入。',
}

export function useAssistantVoice(onTranscript: (value: string) => void) {
  const [listening, setListening] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState('')
  const recognition = useRef<Recognition | null>(null)
  const timeout = useRef<number | undefined>(undefined)
  const transcriptRef = useRef(onTranscript)
  const speechEpoch = useRef(0)
  useEffect(() => { transcriptRef.current = onTranscript }, [onTranscript])
  const canListen = Boolean(recognitionType()) && window.isSecureContext
  const canSpeak = typeof window.speechSynthesis?.speak === 'function' && typeof window.SpeechSynthesisUtterance === 'function'

  const stopSpeaking = useCallback(() => {
    speechEpoch.current += 1
    window.speechSynthesis?.cancel?.()
    setSpeaking(false)
  }, [])
  const stopListening = useCallback((discard = false) => {
    if (discard) {
      const current = recognition.current
      if (current) { current.onresult = null; current.onend = null; current.onerror = null; current.abort() }
      recognition.current = null
      setListening(false); setInterim('')
    } else recognition.current?.stop()
    window.clearTimeout(timeout.current)
  }, [])
  const startListening = useCallback(() => {
    if (recognition.current) return
    const Constructor = recognitionType()
    if (!Constructor || !window.isSecureContext) {
      setError(window.isSecureContext ? '当前浏览器不支持语音输入，可以继续使用文字。' : '语音输入需要 HTTPS 或本机访问地址。')
      return
    }
    stopSpeaking(); setError(''); setInterim('')
    const current = new Constructor()
    current.lang = 'zh-CN'; current.continuous = false; current.interimResults = true
    recognition.current = current
    current.onresult = event => {
      if (recognition.current !== current) return
      let finalText = ''; let draft = ''
      for (let index = event.resultIndex; index < event.results.length; index++) {
        const result = event.results[index]
        if (result.isFinal) finalText += result[0].transcript
        else draft += result[0].transcript
      }
      if (finalText.trim()) transcriptRef.current(finalText.trim())
      setInterim(draft)
    }
    current.onerror = event => {
      if (recognition.current !== current) return
      if (event.error !== 'aborted') setError(errors[event.error] ?? '语音输入失败，可以继续使用文字。')
      window.clearTimeout(timeout.current); recognition.current = null; setListening(false); setInterim('')
    }
    current.onend = () => {
      if (recognition.current !== current) return
      window.clearTimeout(timeout.current); recognition.current = null; setListening(false); setInterim('')
    }
    try {
      current.start(); if (recognition.current !== current) return; setListening(true)
      timeout.current = window.setTimeout(() => current.stop(), 45000)
    } catch {
      recognition.current = null; setListening(false); setError('无法启动麦克风，请检查权限后重试。')
    }
  }, [stopSpeaking])
  const speak = useCallback((text: string) => {
    if (!window.speechSynthesis || typeof window.SpeechSynthesisUtterance !== 'function') {
      setError('当前浏览器不支持回答朗读。'); return
    }
    stopListening(true); stopSpeaking(); setError('')
    const clean = text.replace(/```[\s\S]*?```/g, '代码内容请查看文字。').replace(/!\[[^\]]*\]\([^)]*\)/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[#*_`>|]/g, '').trim()
    if (!clean) return
    const parts = clean.match(/[^。！？；\n]{1,180}[。！？；\n]?/g) ?? [clean]
    const epoch = speechEpoch.current
    const say = (index: number) => {
      if (epoch !== speechEpoch.current) return
      if (index >= parts.length) { setSpeaking(false); return }
      const utterance = new SpeechSynthesisUtterance(parts[index])
      const chinese = window.speechSynthesis.getVoices().find(voice => voice.lang.toLowerCase().startsWith('zh'))
      if (chinese) utterance.voice = chinese
      utterance.lang = 'zh-CN'; utterance.rate = 1; utterance.onend = () => say(index + 1)
      utterance.onerror = event => {
        if (epoch !== speechEpoch.current) return
        setSpeaking(false)
        if (!['canceled', 'interrupted'].includes(event.error)) setError('朗读暂不可用，请查看文字回答。')
      }
      setSpeaking(true); window.speechSynthesis.speak(utterance)
    }
    say(0)
  }, [stopListening, stopSpeaking])
  useEffect(() => {
    const pause = () => { if (document.hidden) { stopListening(true); stopSpeaking() } }
    document.addEventListener('visibilitychange', pause)
    return () => { document.removeEventListener('visibilitychange', pause); stopListening(true); stopSpeaking() }
  }, [stopListening, stopSpeaking])
  return { listening, speaking, interim, error, canListen, canSpeak, startListening, stopListening, speak, stopSpeaking, clearError: () => setError('') }
}
