export type FontWeight = 'regular' | 'medium' | 'semibold' | 'bold' | 'extrabold'

export type SubtitleAnimation = 'none' | 'fade' | 'pop' | 'slide'

export interface Style {
  font: string
  fontSize: number
  fontWeight: FontWeight
  color: string
  outline: number
  outlineColor: string
  background: boolean
  animation: SubtitleAnimation
  /** How long the animation runs, in milliseconds. */
  animationSpeed: number
  /** Light up each word as it is said. */
  highlight: boolean
  highlightColor: string
}

export type Corner = 'topLeft' | 'topRight' | 'bottomLeft' | 'bottomRight'

/** A logo in a corner of the clip. Files live in templates/logos. */
export interface Watermark {
  file: string
  corner: Corner
  /** Share of the video width, 0.04 to 0.5. */
  width: number
  opacity: number
  margin: number
}

export interface Output {
  width: number
  height: number
  fps: number
}

/** One word and when it was said, for lighting it up as it is spoken. */
export interface Spoken {
  start: number
  end: number
  word: string
}

export interface Segment {
  start: number
  end: number
  text: string
  /** Whisper's own timings. They stop matching the text the moment somebody edits it, so
   *  read them through wordTimes() rather than trusting them. */
  words?: Spoken[]
}

export interface Transcript {
  language: string
  segments: Segment[]
}

export interface VideoInfo {
  width: number
  height: number
  duration: number
  fps: number
  videoCodec: string | null
  hasAudio: boolean
  audioCodec: string | null
  audioSampleRate: number | null
  audioChannels: number | null
}

export interface ClipOrigin {
  serviceId: string
  candidateId: string | null
  start: number
  end: number
}

export interface CropWindow {
  /** Centre of the 9:16 frame as a fraction of the scaled source (0.5 = centred). */
  x: number
  y: number
  /** 1 fills the frame, smaller letterboxes, larger crops in further. */
  zoom: number
}

/** The path the crop walks when it follows the speaker. Read with src/track.ts. */
export interface Track {
  /** Samples per second, evenly spaced from the start of the clip. */
  fps: number
  /** Centre of the frame, as a fraction of the scaled source. Same units as CropWindow.x. */
  x: number[]
  /** How much of the clip the speaker was actually found in, 0 to 1. */
  coverage: number
  /** "face" or "person": what it mostly had to go on. */
  subject: string
  /** How far to crop in when the speaker was small in the picture; null = as it was. */
  zoom: number | null
  /** Where to put the frame vertically once it is cropped in; null = as it was. */
  y: number | null
  /** Seconds where the camera changed. */
  cuts: number[]
  /** Samples the frame jumped to; nothing may interpolate across one. */
  jumps: number[]
  /** False: too little was found for this to be worth offering. */
  enough: boolean
}

export interface Project {
  id: string
  createdAt: string
  title: string | null
  origin: ClipOrigin | null
  sourceVideo: string | null
  sourceInfo: VideoInfo | null
  transcript: string | null
  style: Style
  output: Output
  outro: string
  music: MusicSettings
  watermark: Watermark
  cropStrategy: 'static' | 'tracked'
  crop: CropWindow
  track: Track | null
  transcriptData: Transcript | null
  /** Seconds into the source file where this clip begins; 0 when the clip owns its file. */
  sourceStart: number
  /** False when the recording this clip was cut from has been cleaned up. */
  hasFootage: boolean
}

export interface RenderStatus {
  status: 'idle' | 'running' | 'done' | 'error' | 'cancelled'
  progress: number
  message: string
  error: string | null
  canStop?: boolean
}

/** The shapes a clip can be made in. Upright is always made; the others on request. */
export type ShapeKey = '9x16' | '4x5' | '1x1'
export const MAIN_SHAPE: ShapeKey = '9x16'

/** One shape of one clip, and where the clip stands with it. */
export interface ShapeState {
  key: ShapeKey
  /** How a person writes it: "4:5". */
  ratio: string
  name: string
  /** Where it goes, in the words of somebody posting it. */
  use: string
  width: number
  height: number
  ready: boolean
  /** Made before the last change to the clip, so it shows the version from before. */
  stale: boolean
  madeAt: string | null
  mb: number | null
  /** Made every time "Video maken" is pressed. */
  always: boolean
}

/** How this church puts its clips out. Set once, used for every clip. */
export interface ShareSettings {
  /** Shapes made every time next to the upright one. */
  shapes: ShapeKey[]
  address: 'je' | 'u'
  hashtags: string[]
  /** Where the whole service can be watched; empty uses the page it came from. */
  link: string
}

export interface Delivery {
  shapes: ShapeState[]
  /** False when the recording is gone and nothing new can be made from it. */
  canMake: boolean
  share: ShareSettings
}

export type Platform = 'instagram' | 'facebook' | 'whatsapp'

/** The texts to put under the clip, one per place, ready to paste. */
export interface PostView {
  texts: Record<Platform, string>
  /** Platforms whose text was changed by hand. */
  own: Platform[]
  /** The passage the clip names, checked against what was said. */
  bible: string
  by: 'model' | 'template'
  /** Why the plain version is showing, when it is. */
  note: string
  written: string
  link: string
  /** Where the link came from: typed in, this service's own page, or the church's page. */
  linkFrom: '' | 'merk' | 'dienst' | 'station'
}

export interface PostState {
  job: RenderStatus
  post: PostView | null
}

/** One recording or clip that could be cleaned up, and what that would give back. */
export interface StorageItem {
  kind: 'service' | 'project'
  id: string
  title: string
  createdAt: string
  days: number
  mb: number
  /** What survives the cleanup, in the user's words. */
  keeps: string
  /** Empty when it can go; otherwise why it cannot yet. */
  blocked: string
}

export interface StorageReport {
  keepWeeks: number
  freeGb: number
  lowDisk: boolean
  usedMb: number
  oldMb: number
  items: StorageItem[]
}

export interface HealthCheck {
  name: string
  ok: boolean
  detail: string
}

export interface Health {
  ok: boolean
  /** Which version is running, so a support call can start with an answer. */
  version: string
  checks: HealthCheck[]
}

/** One step of the proof: whether it ran, what it found, and how long it took. */
export interface SelfTestStep {
  step: string
  name: string
  ok: boolean
  detail: string
  seconds: number
  skipped: boolean
}

export interface SelfTestResult {
  ok: boolean
  /** What the speech model read back out of the spoken sentence. */
  heard: string
  steps: SelfTestStep[]
  at: string
}

export interface SelfTest {
  last: SelfTestResult | null
  hasClip: boolean
  job: RenderStatus | null
}

/** What the welcome still has to ask a church, and what it can already fill in. */
export interface SetupState {
  done: boolean
  version: string
  provider: string
  hasKey: boolean
  churchName: string
  station: string
  skippedStation: boolean
  missing: ('key' | 'church' | 'station')[]
}

/** What one analysis run would send to the model, and what it costs. */
export interface AnalysisEstimate {
  provider: string
  model: string
  /** Windows actually sent; the rest of the service is not preaching. */
  windows: number
  skippedMinutes: number
  tokens: number
  costEur: number
}

export interface OutroLine {
  text: string
  y: number
  align: 'left' | 'center' | 'right'
  size: number
  weight: FontWeight
  color: string
  font: string
  spacing: number
  uppercase: boolean
  delay: number
}

export type OutroMotion = 'none' | 'in' | 'out' | 'up'

export interface OutroConfig {
  generate: boolean
  duration: number
  motion: OutroMotion
  font: string
  fade: number
  background: { type: 'solid' | 'gradient' | 'image'; color: string; colors: string[]; angle: number; image: string; darken: number }
  logo: { file: string; width: number; y: number }
  lines: OutroLine[]
}

export interface FontFamily {
  name: string
  /** File-name prefix in /templates/fonts; empty for the system font. */
  stem: string
  weights: FontWeight[]
}

export interface MusicSettings {
  file: string
  volume: number
  duck: boolean
  fadeOut: number
}

export interface LogoFile {
  file: string
}

/** A track that can go under a clip: one of the library that ships with the app, or the church's own. */
export interface MusicFile {
  file: string
  title: string
  /** Who made it, as its licence asks for it to be named. */
  credit: string
  /** Ships with the app; cannot be thrown away. */
  library: boolean
  sizeMb: number
  /** Where the browser plays it from. */
  url: string
}

/** The words a church uses that a speech model would not guess. */
export interface Vocabulary {
  preachers: string[]
  series: string[]
  songbooks: string[]
  places: string[]
  extra: string[]
  corrections: Record<string, string>
}

export interface Brand {
  id: string
  name: string
  church: ChurchInfo
  outro: OutroConfig
  subtitleStyle: Style
  music: MusicSettings
  watermark: Watermark
  vocabulary: Vocabulary
  share: ShareSettings
}

export interface BrandSummary {
  id: string
  name: string
  active: boolean
}

/** Small payload used while polling a running job; the transcript is left out on purpose. */
export interface ServiceProgress {
  status: Service['status']
  error: string | null
  warning: string | null
  job: RenderStatus | null
  candidates: number
  clips: number
}

export interface ChurchInfo {
  churchName: string
  serviceTimes: string[]
  instagram: string
  /** The number in the address of this church's page on kerkdienstgemist.nl. */
  kerkdienstgemistStation: string
}

/** A service that has been worked on before, to go back to. */
export interface ServiceSummary {
  id: string
  title: string
  status: ServiceStatus
  createdAt: string
  duration: number | null
  hasFootage: boolean
  clips: number
  moments: number
  /** Who preached, as the church wrote it. Empty when nobody filled it in. */
  preacher: string
  /** Where to get the still that came with the recording, or null when there is none. */
  poster: string | null
}

/** One service standing on a church's page there. */
export interface StationService {
  id: string
  title: string
  when: string
  url: string
  duration: number | null
  /** Who preached, as the church wrote it. Empty when nobody filled it in. */
  preacher: string
  /** A still, straight off the platform. The link is signed, so it does not keep. */
  poster: string | null
}

export interface StationServices {
  id: string
  name: string
  url: string
  services: StationService[]
}

/** An error from the API. `offline` means the app itself could not be reached. */
export class ApiError extends Error {
  offline: boolean
  constructor(message: string, offline = false) {
    super(message)
    this.offline = offline
  }
}

export const OFFLINE_MESSAGE = 'Geen verbinding met de app. Staat het zwarte venster nog open?'
export const OUTDATED_MESSAGE =
  'Dit kent de app nog niet: het zwarte venster draait een oudere versie. Sluit het en start de app opnieuw.'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new ApiError(OFFLINE_MESSAGE, true)
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* not JSON */
    }
    if (res.status >= 500 && !detail) detail = 'De app kon dit niet verwerken. Kijk in het zwarte venster voor details.'
    // Every route of ours answers a 404 in Dutch. The bare English one means the route is not
    // there at all: the interface is newer than the server that is running.
    if (res.status === 404 && detail === 'Not Found') detail = OUTDATED_MESSAGE
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json() as Promise<T>
}

/** Upload with a progress callback; fetch cannot report how much has been sent. */
function upload<T>(url: string, file: File, onProgress?: (fraction: number) => void): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const form = new FormData()
    form.append('file', file)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.onload = () => {
      let data: { detail?: string } = {}
      try {
        data = JSON.parse(xhr.responseText)
      } catch {
        reject(new ApiError(`Onverwacht antwoord van de app (${xhr.status}).`))
        return
      }
      if (xhr.status >= 400) reject(new ApiError(data.detail ?? `Uploaden mislukt (${xhr.status}).`))
      else resolve(data as T)
    }
    xhr.onerror = () => reject(new ApiError(OFFLINE_MESSAGE, true))
    xhr.ontimeout = () => reject(new ApiError('Het uploaden duurde te lang.', true))
    xhr.send(form)
  })
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  createProject: () => request<Project>('/projects', { method: 'POST' }),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  upload: (id: string, file: File, onProgress?: (fraction: number) => void) =>
    upload<Project>(`/projects/${id}/upload`, file, onProgress),
  transcribe: (id: string) => request<RenderStatus>(`/projects/${id}/transcribe`, { method: 'POST' }),
  transcribeStatus: (id: string) => request<RenderStatus>(`/projects/${id}/transcribe-status`),
  stopTranscribe: (id: string) => request<RenderStatus>(`/projects/${id}/transcribe/stop`, { method: 'POST' }),
  saveTranscript: (id: string, transcript: Transcript) =>
    request<Transcript>(`/projects/${id}/transcript`, json('PUT', transcript)),
  saveStyle: (id: string, style: Style) => request<Project>(`/projects/${id}/style`, json('PUT', style)),
  saveCrop: (id: string, crop: CropWindow) => request<Project>(`/projects/${id}/crop`, json('PUT', crop)),
  /** Follow the speaker, or go back to the window set by hand. */
  setFraming: (id: string, follow: boolean) => request<Project>(`/projects/${id}/framing`, json('PUT', { follow })),
  /** Look through this clip for the speaker. Runs as a job; watch it with trackStatus. */
  track: (id: string) => request<RenderStatus>(`/projects/${id}/track`, { method: 'POST' }),
  trackStatus: (id: string) =>
    request<{ job: RenderStatus | null; cropStrategy: 'static' | 'tracked'; track: Track | null }>(`/projects/${id}/track`),
  saveMusic: (id: string, music: MusicSettings) => request<Project>(`/projects/${id}/music`, json('PUT', music)),
  saveMeta: (id: string, title: string) => request<Project>(`/projects/${id}/meta`, json('PUT', { title })),
  saveWatermark: (id: string, watermark: Watermark) =>
    request<Project>(`/projects/${id}/watermark`, json('PUT', watermark)),
  wordSuggestions: (id: string) =>
    request<{ suggestions: Record<string, string> }>(`/projects/${id}/word-suggestions`),
  learnWords: (id: string, corrections: Record<string, string>) =>
    request<{ learned: number; total: number }>(`/projects/${id}/word-suggestions`, json('POST', { corrections })),
  logos: () => request<LogoFile[]>('/logos'),
  uploadLogo: (file: File, onProgress?: (f: number) => void) => upload<LogoFile>('/logos', file, onProgress),
  deleteLogo: (name: string) => request<LogoFile>(`/logos/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  logoUrl: (name: string) => `/templates/logos/${encodeURIComponent(name)}`,
  music: () => request<MusicFile[]>('/music'),
  uploadMusic: (file: File, onProgress?: (f: number) => void) => upload<{ file: string }>('/music', file, onProgress),
  deleteMusic: (name: string) => request<{ file: string }>(`/music/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  brands: () => request<BrandSummary[]>('/brands'),
  brand: (id: string) => request<Brand>(`/brands/${id}`),
  saveBrand: (brand: Brand) => request<Brand>(`/brands/${brand.id}`, json('PUT', brand)),
  createBrand: (name: string, copyFrom?: string) => request<Brand>('/brands', json('POST', { name, copyFrom })),
  activateBrand: (id: string) => request<Brand>(`/brands/${id}/activate`, { method: 'POST' }),
  deleteBrand: (id: string) => request<BrandSummary[]>(`/brands/${id}`, { method: 'DELETE' }),
  /** Make the clip. Without shapes: upright, plus whatever the church always wants. */
  render: (id: string, shapes?: ShapeKey[]) =>
    request<RenderStatus>(`/projects/${id}/render`, shapes ? json('POST', { shapes }) : { method: 'POST' }),
  delivery: (id: string) => request<Delivery>(`/projects/${id}/delivery`),
  post: (id: string) => request<PostState>(`/projects/${id}/post`),
  /** Write the texts again; what was changed by hand in them goes. */
  rewritePost: (id: string) => request<PostState>(`/projects/${id}/post`, { method: 'POST' }),
  editPost: (id: string, platform: Platform, text: string) =>
    request<PostState>(`/projects/${id}/post`, json('PUT', { platform, text })),
  share: () => request<ShareSettings>('/share'),
  saveShare: (share: ShareSettings) => request<ShareSettings>('/share', json('PUT', share)),
  stopRender: (id: string) => request<RenderStatus>(`/projects/${id}/render/stop`, { method: 'POST' }),
  health: () => request<Health>('/health'),
  /** Ten seconds through the whole chain, so nobody finds out on a Sunday. */
  selfTest: () => request<SelfTest>('/selftest'),
  runSelfTest: () => request<RenderStatus>('/selftest', { method: 'POST' }),
  storage: () => request<StorageReport>('/storage'),
  cleanOne: (kind: StorageItem['kind'], id: string) =>
    request<StorageReport>('/storage/clean', json('POST', { kind, id })),
  cleanOld: () => request<StorageReport>('/storage/clean-old', { method: 'POST' }),
  renderStatus: (id: string) => request<RenderStatus>(`/projects/${id}/render-status`),
  church: () => request<ChurchInfo>('/church'),
  /** The mishearings this church knows about, for flagging one still in a line. */
  words: () => request<{ corrections: Record<string, string> }>('/words'),
  fonts: () => request<FontFamily[]>('/fonts'),
  outroConfig: () => request<OutroConfig>('/outro'),
  saveOutro: (config: OutroConfig) => request<OutroConfig>('/outro', json('PUT', config)),
  uploadOutroBackground: (file: File) => upload<{ image: string }>('/outro/background', file),
  rebuildOutro: () => request<OutroConfig>('/outro/rebuild', { method: 'POST' }),
  sourceUrl: (id: string) => `/projects/${id}/source`,
  outputUrl: (id: string, shape: ShapeKey = MAIN_SHAPE) =>
    shape === MAIN_SHAPE ? `/projects/${id}/output` : `/projects/${id}/output?shape=${shape}`,
  outroUrl: (version = 0) => `/templates/outro.mp4?v=${version}`,
}

// --- full-service clip discovery ---------------------------------------------

export type ServiceStatus =
  | 'created' | 'fetching' | 'uploaded' | 'transcribing' | 'transcribed' | 'analyzing' | 'ready' | 'processing' | 'complete' | 'error'

export interface TimeRange {
  start: number
  end: number
}

export type CandidateSource = 'found' | 'self'

export interface ClipCandidate {
  id: string
  start: number
  end: number
  title: string
  summary: string
  reason: string
  confidence: number
  selected: boolean
  score: number
  alternateBoundaries: TimeRange[]
  /** False when the second pass judged another moment better. Still available. */
  shortlisted: boolean
  /** One line: why it was picked, or why it was passed over. */
  verdict: string
  /** Which part of the service it comes from. */
  part: string
  /** "self": cut out of the transcript by hand, which the search may never touch. */
  source: CandidateSource
}

/** One stretch of the service: welcome, songs, reading, prayer, sermon, notices, blessing. */
export interface ServiceBlock {
  part: string
  label: string
  start: number
  end: number
  confidence: number
}

export interface ProcessedClip {
  candidateId: string
  projectId: string
  title: string
  start: number
  end: number
  createdAt: string
}

export interface Service {
  id: string
  createdAt: string
  title: string
  sourceVideo: string | null
  sourceInfo: VideoInfo | null
  transcript: string | null
  status: ServiceStatus
  error: string | null
  warning: string | null
  /** Use the slower model that hears more. Applies to the next run. */
  accurate: boolean
  /** What the preaching is about, when the church knows beforehand. */
  sermonTitle: string
  series: string
  /** Who preached, as the church wrote it on its own page. */
  preacher: string
  /** Where to get the still that came with this recording, or null when there is none. */
  posterUrl: string | null
  shape: ServiceBlock[]
  candidates: ClipCandidate[]
  clips: ProcessedClip[]
  transcriptData: Transcript | null
  analysis: AnalysisEstimate | null
  job: RenderStatus | null
}

export const setupApi = {
  read: () => request<SetupState>('/setup'),
  /** Tried against the API before it is written down, so a typo says so here. */
  saveKey: (key: string) => request<SetupState & { model: string }>('/setup/key', json('PUT', { key })),
  dropKey: () => request<SetupState>('/setup/key', { method: 'DELETE' }),
  saveChurch: (patch: {
    churchName?: string
    station?: string
    serviceTimes?: string[]
    instagram?: string
  }) => request<SetupState>('/setup/church', json('PUT', patch)),
  done: (skippedStation: boolean) => request<SetupState>('/setup/done', json('POST', { skippedStation })),
  reopen: () => request<SetupState>('/setup/reopen', { method: 'POST' }),
}

export const serviceApi = {
  create: () => request<Service>('/services', { method: 'POST' }),
  /** The services worked on before, newest first, so closing one is not losing it. */
  recent: () => request<ServiceSummary[]>('/services'),
  get: (id: string) => request<Service>(`/services/${id}`),
  status: (id: string) => request<ServiceProgress>(`/services/${id}/status`),
  upload: (id: string, file: File, onProgress?: (fraction: number) => void) =>
    upload<Service>(`/services/${id}/upload`, file, onProgress),
  /** Fetch the recording from where the church already publishes it. */
  link: (id: string, url: string) => request<Service>(`/services/${id}/link`, json('POST', { url })),
  /** The services standing on this church's own page at kerkdienstgemist. */
  station: (station: string) => request<StationServices>(`/kerkdienstgemist/stations/${encodeURIComponent(station)}`),
  transcribe: (id: string) => request<Service>(`/services/${id}/transcribe`, { method: 'POST' }),
  setAccuracy: (id: string, accurate: boolean) =>
    request<Service>(`/services/${id}/accuracy`, json('PUT', { accurate })),
  setAbout: (id: string, sermonTitle: string, series: string) =>
    request<Service>(`/services/${id}/about`, json('PUT', { sermonTitle, series })),
  analyze: (id: string) => request<Service>(`/services/${id}/analyze`, { method: 'POST' }),
  saveCandidates: (id: string, candidates: ClipCandidate[]) =>
    request<ClipCandidate[]>(`/services/${id}/candidates`, json('PUT', candidates)),
  processSelected: (id: string) => request<Service>(`/services/${id}/process-selected`, { method: 'POST' }),
  stop: (id: string) => request<Service>(`/services/${id}/stop`, { method: 'POST' }),
  sourceUrl: (id: string) => `/services/${id}/source`,
}
