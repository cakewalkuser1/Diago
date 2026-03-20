/* ─── Behavioral Context ─── */
export interface BehavioralContext {
  rpm_dependency: boolean;
  speed_dependency: boolean;
  load_dependency: boolean;
  cold_only: boolean;
  occurs_at_idle: boolean;
  mechanical_localization: boolean;
  noise_character: string;
  perceived_frequency: string;
  intermittent: boolean;
  issue_duration: string;
  vehicle_type: string;
  mileage_range: string;
  recent_maintenance: string;
}

/** Optional fuel trim data (STFT/LTFT %) for DIYer/Pro users. */
export interface FuelTrimInput {
  stft: number | null;
  ltft: number | null;
}

export const DEFAULT_CONTEXT: BehavioralContext = {
  rpm_dependency: false,
  speed_dependency: false,
  load_dependency: false,
  cold_only: false,
  occurs_at_idle: false,
  mechanical_localization: false,
  noise_character: "unknown",
  perceived_frequency: "unknown",
  intermittent: false,
  issue_duration: "unknown",
  vehicle_type: "unknown",
  mileage_range: "unknown",
  recent_maintenance: "unknown",
};

/* ─── Diagnosis ─── */
export interface ClassScore {
  class_name: string;
  display_name: string;
  score: number;
  penalty: number;
}

export interface ConfirmTest {
  test: string;
  tool: string;
  expected: string;
}

export interface RankedFailureMode {
  failure_id: string;
  display_name: string;
  description: string;
  score: number;
  confirm_tests: ConfirmTest[];
  matched_conditions: string[];
  ruled_out_disqualifiers: string[];
}

export interface DiagnosisResponse {
  top_class: string;
  top_class_display: string;
  confidence: string;
  is_ambiguous: boolean;
  class_scores: ClassScore[];
  fingerprint_count: number;
  llm_narrative: string | null;
  report_text: string;
  ranked_failure_modes?: RankedFailureMode[];
}

export interface SubscriptionStatus {
  tier: string;
  limit: number;
  used: number;
  remaining: number;
}

/* ─── Audio ─── */
export interface AudioInfo {
  duration_seconds: number;
  sample_rate: number;
  num_samples: number;
  peak_amplitude: number;
  rms_energy: number;
}

export interface SpectrogramData {
  image_base64: string;
  duration_seconds: number;
  sample_rate: number;
}

/* ─── Sessions ─── */
export interface Session {
  id: number;
  timestamp: string;
  audio_path: string;
  user_codes: string;
  notes: string;
  duration_seconds: number;
}

export interface SessionMatch {
  fault_name: string;
  confidence_pct: number;
  trouble_codes: string;
  description: string;
  category: string;
  signature_id: number;
}

/* ─── Signatures ─── */
export interface Signature {
  id: number;
  name: string;
  description: string;
  category: string;
  associated_codes: string;
  created_at: string;
}

export interface SignatureStats {
  total_signatures: number;
  total_hashes: number;
}

/* ─── Trouble Codes ─── */
export interface TroubleCode {
  code: string;
  description: string;
  system: string;
  subsystem: string;
  mechanical_classes: string[];
  symptoms: string[];
  severity: string;
}

/* ─── Chat ─── */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
}

/* ─── Vehicle (NHTSA) ─── */
export interface VinDecodeResult {
  make: string;
  model: string;
  model_year: string;
  trim: string;
  engine_model: string;
  vehicle_type: string;
  raw: Record<string, unknown>;
  error?: string;
}

export interface RecallItem {
  campaign_number: string;
  summary: string;
  consequence: string;
  remedy: string;
  component: string;
  nhtsa_id: string;
}

export interface RecallsResult {
  make: string;
  model: string;
  model_year: number;
  count: number;
  recalls: RecallItem[];
}

/** Vehicle dropdown data (year / make / model / trim) for start diagnosis. */
export interface VehicleSelection {
  year: number | null;
  makeId: number | null;
  makeName: string;
  modelId: number | null;
  modelName: string;
  trim: string;
}

export interface VehicleYearsResult {
  years: number[];
}

export interface MakeItem {
  make_id: number;
  make_name: string;
}

export interface ModelItem {
  model_id: number;
  model_name: string;
  make_id: number;
  make_name: string;
}

export interface VehicleMakesResult {
  makes: MakeItem[];
}

export interface VehicleModelsResult {
  models: ModelItem[];
}

/** Stored selected vehicle (from API/DB) for tailored diagnosis. */
export interface SelectedVehicle {
  model_year: number | null;
  make: string;
  model: string;
  submodel: string;
}

/* ─── TSBs ─── */
export interface TSBItem {
  id: number;
  model_year: number;
  make: string;
  model: string;
  component: string;
  summary: string;
  nhtsa_id: string;
  document_id: string;
  created_at: string;
}

export interface TSBSearchResult {
  count: number;
  results: TSBItem[];
}

/* ─── View Modes ─── */
export type ViewMode = "spectrogram" | "mel" | "waveform";
export type RecordDuration = "manual" | "3" | "5" | "10" | "15" | "30" | "60";

/* ─── Dispatch (diagnostics -> parts -> mechanic) ─── */
export interface DispatchPartRetailer {
  id: string;
  name: string;
  distance_mi: number;
  store_id: string;
}

export interface DispatchMechanic {
  id: number;
  name: string;
  distance_mi: number;
  availability: string;
  rating?: number | null;
}

export interface DispatchResponse {
  thread_id: string;
  diagnosis_result?: { top_class: string; confidence: string; class_scores?: Record<string, number> };
  diagnosis_summary?: string;
  suggested_parts?: { name: string }[];
  part_retailers?: DispatchPartRetailer[];
  mechanic_list?: DispatchMechanic[];
  job_id?: number;
  job_status?: string;
  current_step: string;
  prompt_for_user: string;
  error?: string;
}
