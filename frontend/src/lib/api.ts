/**
 * API client for the Autopilot FastAPI backend.
 * All requests go through the Vite proxy (or direct in production).
 */

import type {
  BehavioralContext,
  DiagnosisResponse,
  DispatchResponse,
  RankedFailureMode,
  SubscriptionStatus,
  AudioInfo,
  SpectrogramData,
  Session,
  SessionMatch,
  Signature,
  SignatureStats,
  TroubleCode,
  VinDecodeResult,
  RecallsResult,
  VehicleYearsResult,
  VehicleMakesResult,
  VehicleModelsResult,
  SelectedVehicle,
  TSBSearchResult,
} from "@/types";
import { getApiBase } from "@/lib/env";

const BASE = `${getApiBase()}/api/v1`;

/** Error with status for paywall (429) handling */
export class ApiError extends Error {
  status: number;
  body: string;
  constructor(message: string, status: number, body: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(`API ${res.status}: ${body}`, res.status, body);
  }
  return res.json() as Promise<T>;
}

function headersWithAuth(contentType: string | undefined, accessToken: string | null): HeadersInit {
  const h: Record<string, string> = {};
  if (contentType) h["Content-Type"] = contentType;
  if (accessToken) h["Authorization"] = `Bearer ${accessToken}`;
  return h;
}

/* ─── Health ─── */
export async function healthCheck() {
  return request<{ status: string; version: string }>(`${getApiBase()}/health`);
}

/* ─── Diagnosis ─── */
export async function diagnoseText(
  payload: {
    symptoms: string;
    codes: string[];
    context: BehavioralContext;
    plain_english?: boolean;
    fuel_trims?: { stft?: number | null; ltft?: number | null };
  },
  accessToken?: string | null
): Promise<DiagnosisResponse> {
  return request<DiagnosisResponse>(`${BASE}/diagnosis/text`, {
    method: "POST",
    headers: headersWithAuth("application/json", accessToken ?? null),
    body: JSON.stringify(payload),
  });
}

export async function diagnoseAudio(
  file: File | Blob,
  symptoms = "",
  codes = "",
  plainEnglish = false,
  accessToken?: string | null
): Promise<DiagnosisResponse> {
  const form = new FormData();
  form.append("audio_file", file);
  form.append("symptoms", symptoms);
  form.append("codes", codes);
  form.append("plain_english", String(plainEnglish));
  return request<DiagnosisResponse>(`${BASE}/diagnosis/audio`, {
    method: "POST",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
    body: form,
  });
}

export async function confirmTest(payload: {
  ranked_failure_modes: RankedFailureMode[];
  test_id: string;
  result: "pass" | "fail";
}): Promise<{ ranked_failure_modes: RankedFailureMode[] }> {
  return request<{ ranked_failure_modes: RankedFailureMode[] }>(
    `${BASE}/diagnosis/confirm`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
}

export async function exportDiagnosisPdf(payload: {
  top_class: string;
  top_class_display: string;
  confidence: string;
  is_ambiguous: boolean;
  report_text: string;
  llm_narrative?: string | null;
  class_scores: { class_name?: string; display_name?: string; score?: number }[];
  ranked_failure_modes?: { display_name?: string; description?: string }[];
  symptoms?: string;
  vehicle?: string;
}): Promise<Blob> {
  const res = await fetch(`${BASE}/diagnosis/export-pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(`PDF export failed: ${body}`, res.status, body);
  }
  return res.blob();
}

/* ─── Audio ─── */
export async function getAudioInfo(file: File | Blob): Promise<AudioInfo> {
  const form = new FormData();
  form.append("audio_file", file);
  return request<AudioInfo>(`${BASE}/audio/info`, {
    method: "POST",
    body: form,
  });
}

export async function getSpectrogram(
  file: File | Blob,
  mode = "power"
): Promise<SpectrogramData> {
  const form = new FormData();
  form.append("audio_file", file);
  form.append("mode", mode);
  return request<SpectrogramData>(`${BASE}/audio/spectrogram`, {
    method: "POST",
    body: form,
  });
}

/* ─── Sessions ─── */
export async function listSessions(limit = 50): Promise<Session[]> {
  return request<Session[]>(`${BASE}/sessions/?limit=${limit}`);
}

/* ─── Repairs (Enterprise) ─── */
export interface RepairLog {
  id: number;
  session_id: number | null;
  vin: string | null;
  repair_description: string;
  parts_used: string;
  outcome: string;
  created_at: string;
}

export async function createRepair(payload: {
  session_id?: number | null;
  vin?: string | null;
  repair_description: string;
  parts_used?: string;
  outcome?: string;
}): Promise<{ id: number }> {
  return request<{ id: number }>(`${BASE}/repairs/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listRepairs(params?: {
  vin?: string;
  session_id?: number;
  limit?: number;
}): Promise<RepairLog[]> {
  const search = new URLSearchParams();
  if (params?.vin) search.set("vin", params.vin);
  if (params?.session_id != null) search.set("session_id", String(params.session_id));
  if (params?.limit != null) search.set("limit", String(params.limit));
  const qs = search.toString();
  return request<RepairLog[]>(`${BASE}/repairs/${qs ? `?${qs}` : ""}`);
}

/* ─── Analytics (Enterprise) ─── */
export async function getAnalytics(): Promise<{
  total_diagnoses: number;
  total_repair_logs: number;
}> {
  return request(`${BASE}/analytics/`);
}

export async function getSessionMatches(
  sessionId: number
): Promise<SessionMatch[]> {
  return request<SessionMatch[]>(`${BASE}/sessions/${sessionId}/matches`);
}

export async function deleteSession(
  sessionId: number
): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`${BASE}/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

/* ─── Signatures ─── */
export async function listSignatures(): Promise<Signature[]> {
  return request<Signature[]>(`${BASE}/signatures/`);
}

export async function getSignatureStats(): Promise<SignatureStats> {
  return request<SignatureStats>(`${BASE}/signatures/stats`);
}

export async function createSignature(payload: {
  name: string;
  description: string;
  category: string;
  associated_codes?: string;
}): Promise<{ signature_id: number }> {
  return request<{ signature_id: number }>(`${BASE}/signatures/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteSignature(
  id: number
): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`${BASE}/signatures/${id}`, {
    method: "DELETE",
  });
}

/* ─── Trouble Codes ─── */
export async function lookupCode(code: string): Promise<TroubleCode> {
  return request<TroubleCode>(`${BASE}/codes/lookup/${code}`);
}

export async function lookupCodes(codes: string[]): Promise<TroubleCode[]> {
  return request<TroubleCode[]>(
    `${BASE}/codes/lookup?codes=${codes.join(",")}`
  );
}

export async function searchCodes(
  query: string
): Promise<{ query: string; results: TroubleCode[]; count: number }> {
  return request<{ query: string; results: TroubleCode[]; count: number }>(
    `${BASE}/codes/search?q=${encodeURIComponent(query)}`
  );
}

export async function suggestBySymptoms(
  keywords: string[]
): Promise<TroubleCode[]> {
  return request<TroubleCode[]>(
    `${BASE}/codes/symptoms?keywords=${keywords.join(",")}`
  );
}

/* ─── Vehicle (NHTSA vPIC + Recalls) ─── */
export async function decodeVin(
  vin: string,
  modelYear?: number
): Promise<VinDecodeResult> {
  const params = new URLSearchParams();
  if (modelYear != null) params.set("model_year", String(modelYear));
  const q = params.toString();
  return request<VinDecodeResult>(
    `${BASE}/vehicle/vin/${encodeURIComponent(vin)}${q ? `?${q}` : ""}`
  );
}

export async function getRecalls(
  make: string,
  model: string,
  modelYear: number
): Promise<RecallsResult> {
  return request<RecallsResult>(
    `${BASE}/vehicle/recalls?make=${encodeURIComponent(make)}&model=${encodeURIComponent(model)}&model_year=${modelYear}`
  );
}

export async function getVehicleYears(): Promise<VehicleYearsResult> {
  return request<VehicleYearsResult>(`${BASE}/vehicle/years`);
}

export async function getVehicleMakes(
  vehicleType = "car"
): Promise<VehicleMakesResult> {
  return request<VehicleMakesResult>(
    `${BASE}/vehicle/makes?vehicle_type=${encodeURIComponent(vehicleType)}`
  );
}

export async function getVehicleModels(
  makeId: number,
  modelYear: number
): Promise<VehicleModelsResult> {
  return request<VehicleModelsResult>(
    `${BASE}/vehicle/models?make_id=${makeId}&model_year=${modelYear}`
  );
}

export async function getSelectedVehicle(): Promise<SelectedVehicle> {
  return request<SelectedVehicle>(`${BASE}/vehicle/selected`);
}

export async function saveSelectedVehicle(payload: {
  model_year: number | null;
  make: string;
  model: string;
  submodel: string;
}): Promise<SelectedVehicle> {
  return request<SelectedVehicle>(`${BASE}/vehicle/selected`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** charm.li (Operation CHARM) service manual URL for the current or given vehicle (1982–2013). */
export async function getManualUrl(params?: {
  make?: string;
  model_year?: number;
}): Promise<{ url: string | null; make: string; model_year: number | null; message: string }> {
  const search = new URLSearchParams();
  if (params?.make) search.set("make", params.make);
  if (params?.model_year != null) search.set("model_year", String(params.model_year));
  const q = search.toString();
  return request<{ url: string | null; make: string; model_year: number | null; message: string }>(
    `${BASE}/vehicle/manual-url${q ? `?${q}` : ""}`
  );
}

/* ─── TSBs ─── */
export async function searchTsbs(params: {
  model_year?: number;
  make?: string;
  model?: string;
  component?: string;
  limit?: number;
}): Promise<TSBSearchResult> {
  const search = new URLSearchParams();
  if (params.model_year != null) search.set("model_year", String(params.model_year));
  if (params.make) search.set("make", params.make);
  if (params.model) search.set("model", params.model);
  if (params.component) search.set("component", params.component);
  if (params.limit != null) search.set("limit", String(params.limit));
  return request<TSBSearchResult>(`${BASE}/tsbs/search?${search.toString()}`);
}

export async function getTsbCount(): Promise<{ count: number }> {
  return request<{ count: number }>(`${BASE}/tsbs/count`);
}

/* ─── Payments (subscription, requires auth) ─── */
export async function getSubscriptionStatus(
  accessToken: string
): Promise<SubscriptionStatus> {
  return request<SubscriptionStatus>(`${BASE}/payments/subscription`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function createCheckout(
  payload: { tier: "pro" | "premium"; success_url: string; cancel_url: string },
  accessToken: string
): Promise<{ checkout_url: string }> {
  return request<{ checkout_url: string }>(`${BASE}/payments/checkout`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(payload),
  });
}

export async function cancelSubscription(accessToken: string): Promise<{ message: string }> {
  return request<{ message: string }>(`${BASE}/payments/cancel`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

/* ─── Repair guides (CarDiagn + charm.li, no separate API) ─── */
export interface RepairGuideItem {
  id: number;
  source: string;
  source_url: string;
  title: string;
  summary?: string;
  vehicle_make?: string;
  vehicle_model?: string;
  year_min?: number;
  year_max?: number;
}

export async function getRepairGuidesForDiagnosis(params: {
  q?: string;
  make?: string;
  model?: string;
  year?: number;
  limit?: number;
}): Promise<RepairGuideItem[]> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.make) search.set("make", params.make);
  if (params.model) search.set("model", params.model);
  if (params.year != null) search.set("year", String(params.year));
  if (params.limit != null) search.set("limit", String(params.limit));
  const qs = search.toString();
  return request<RepairGuideItem[]>(
    `${BASE}/repair-guides/for-diagnosis${qs ? `?${qs}` : ""}`
  );
}

/* ─── Chat (Ollama — local, no credits) ─── */
export interface ChatMessagePayload {
  role: string;
  content: string;
}

export interface ChatContextPayload {
  symptoms?: string;
  vehicle?: string;
  trouble_codes?: string[];
  diagnosis_summary?: string;
  photo_urls?: string[];
}

export async function uploadDiagnosisPhoto(file: File): Promise<{ photo_id: string; url: string }> {
  const form = new FormData();
  form.append("file", file);
  return request<{ photo_id: string; url: string }>(`${BASE}/diagnosis/upload-photo`, {
    method: "POST",
    body: form,
  });
}

export interface ChatResponsePayload {
  content: string;
  error?: string;
  sources?: string[];
}

export async function postChat(
  messages: ChatMessagePayload[],
  context?: ChatContextPayload
): Promise<ChatResponsePayload> {
  return request<ChatResponsePayload>(`${BASE}/chat/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, context }),
  });
}

/** Stream chat response via SSE. Calls onToken for each token, onDone with final sources. Returns false if stream unavailable (use postChat fallback). */
export async function postChatStream(
  messages: ChatMessagePayload[],
  context: ChatContextPayload | undefined,
  callbacks: {
    onToken: (token: string) => void;
    onDone: (sources: string[]) => void;
    onError: (err: string) => void;
  }
): Promise<boolean> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, context }),
  });
  if (!res.ok) {
    if (res.status === 503) return false;
    const text = await res.text();
    callbacks.onError(text || `HTTP ${res.status}`);
    return false;
  }
  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError("No response body");
    return false;
  }
  const decoder = new TextDecoder();
  let buffer = "";
  let sources: string[] = [];
  let doneCalled = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const raw = line.slice(6);
          if (raw === "[DONE]") continue;
          try {
            const data = JSON.parse(raw);
            if (data.token) callbacks.onToken(data.token);
            if (data.sources) sources = data.sources;
            if (data.error) callbacks.onError(data.error);
            if (data.done && !doneCalled) {
              doneCalled = true;
              callbacks.onDone(sources);
            }
          } catch {
            /* ignore parse errors */
          }
        }
      }
    }
    if (!doneCalled && (sources.length > 0 || buffer)) {
      callbacks.onDone(sources);
    }
  } catch (e) {
    callbacks.onError(e instanceof Error ? e.message : "Stream failed");
    return false;
  }
  return true;
}

/* ─── Dispatch parts order (Stripe payment) ─── */
export async function createPartsOrder(payload: {
  thread_id: string;
  part: { name: string };
  retailer_id: string;
  retailer_name: string;
  retailer_store_id?: string;
  user_id?: string;
}): Promise<{
  client_secret: string | null;
  payment_intent_id: string;
  amount_cents: number;
  order_id?: number;
  stub: boolean;
}> {
  return request(`${BASE}/dispatch/parts-order/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getPaymentsConfig(): Promise<{ stripe_publishable_key: string }> {
  return request(`${BASE}/payments/config`);
}

/* ─── Geocoding (address -> lat/lng for dispatch) ─── */
export async function geocodeAddress(address: string): Promise<{ latitude: number; longitude: number }> {
  const params = new URLSearchParams({ address });
  return request<{ latitude: number; longitude: number }>(`${BASE}/geocode?${params}`);
}

/* ─── Dispatch (diagnostics -> parts -> mechanic) ─── */
export async function dispatchRun(payload: {
  symptoms: string;
  codes: string[];
  behavioral_context?: Record<string, unknown>;
  user_id?: string;
}): Promise<DispatchResponse> {
  return request<DispatchResponse>(`${BASE}/dispatch/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** Direct to mechanic — skip diagnosis for users who already know what's wrong. */
export async function dispatchRunDirect(payload: {
  part_info: string;
  user_latitude?: number;
  user_longitude?: number;
  user_address?: string;
  user_id?: string;
}): Promise<DispatchResponse> {
  return request<DispatchResponse>(`${BASE}/dispatch/run-direct`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function createReview(payload: {
  job_id: number;
  reviewer_role: "customer" | "mechanic";
  rating: number;
  comment?: string;
}, userId?: string | null): Promise<{ ok: boolean }> {
  return request(`${BASE}/reviews/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(userId ? { "X-User-Id": userId } : {}) },
    body: JSON.stringify(payload),
  });
}

export async function getMechanicReviews(mechanicId: number): Promise<{ rating: number; comment: string | null; created_at: string }[]> {
  return request(`${BASE}/reviews/mechanic/${mechanicId}`);
}

/* ─── Maintenance ─── */
export async function getMaintenanceRecords(userId?: string | null): Promise<MaintenanceRecord[]> {
  return request(`${BASE}/maintenance/records`, {
    headers: userId ? { "X-User-Id": userId } : {},
  });
}

export async function getMaintenanceDue(userId?: string | null, currentMileage?: number): Promise<MaintenanceRecord[]> {
  const qs = currentMileage != null ? `?current_mileage=${currentMileage}` : "";
  return request(`${BASE}/maintenance/due${qs}`, {
    headers: userId ? { "X-User-Id": userId } : {},
  });
}

export async function getMaintenanceSchedules(): Promise<{ id: number; service_type: string; interval_miles: number; interval_months: number; description: string }[]> {
  return request(`${BASE}/maintenance/schedules`);
}

export async function createMaintenanceRecord(
  payload: {
    vehicle_vin?: string;
    vehicle_year?: number;
    vehicle_make?: string;
    vehicle_model?: string;
    service_type: string;
    mileage?: number;
    performed_at?: string;
    next_due_mileage?: number;
    next_due_date?: string;
    notes?: string;
  },
  userId?: string | null
): Promise<{ id: number; ok: boolean }> {
  return request(`${BASE}/maintenance/records`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(userId ? { "X-User-Id": userId } : {}) },
    body: JSON.stringify(payload),
  });
}

export interface MaintenanceRecord {
  id: number;
  vehicle_vin?: string;
  vehicle_year?: number;
  vehicle_make?: string;
  vehicle_model?: string;
  service_type: string;
  mileage?: number;
  performed_at?: string;
  next_due_mileage?: number;
  next_due_date?: string;
  notes?: string;
  created_at: string;
}

export async function getJob(jobId: number): Promise<{
  id: number;
  part_info: string;
  user_latitude: number | null;
  user_longitude: number | null;
  user_address: string | null;
  status: string;
  assigned_mechanic_id: number | null;
  mechanic_name: string | null;
  mechanic_lat: number | null;
  mechanic_lng: number | null;
  estimated_arrival_at: string | null;
  route_distance_mi: number | null;
  route_duration_min: number | null;
  created_at: string;
}> {
  return request(`${BASE}/dispatch/job/${jobId}`);
}

export async function dispatchContinue(payload: {
  thread_id: string;
  action: "get_parts" | "part_selected" | "stock_confirmed" | "mechanic_selected" | "mechanic_responded";
  selected_part?: Record<string, unknown>;
  selected_mechanic_id?: number;
  mechanic_accepted?: boolean;
  payment_intent_id?: string;
  user_latitude?: number;
  user_longitude?: number;
  user_address?: string;
}): Promise<DispatchResponse> {
  return request<DispatchResponse>(`${BASE}/dispatch/continue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/* ─── Mechanic Profile ─── */
export interface MechanicProfile {
  id: number;
  user_id: string;
  name: string;
  email?: string;
  phone?: string;
  latitude?: number;
  longitude?: number;
  availability?: string;
  service_radius_mi?: number;
  hourly_rate_cents?: number;
  bio?: string;
  profile_photo_url?: string;
  rating?: number;
  total_jobs?: number;
  is_verified?: number;
  skills?: string;
}

function mechanicHeaders(userId?: string | null): HeadersInit {
  const h: Record<string, string> = {};
  if (userId) h["X-Mechanic-User-Id"] = userId;
  return h;
}

export async function registerMechanic(
  payload: {
    name: string;
    email?: string;
    phone?: string;
    latitude?: number;
    longitude?: number;
    service_radius_mi?: number;
    hourly_rate_cents?: number;
    bio?: string;
    skills?: string;
  },
  userId?: string | null
): Promise<{ mechanic_id: number; message: string }> {
  return request(`${BASE}/mechanic/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...mechanicHeaders(userId) },
    body: JSON.stringify(payload),
  });
}

export async function getMechanicProfile(userId?: string | null): Promise<MechanicProfile | null> {
  try {
    return await request<MechanicProfile>(`${BASE}/mechanic/me`, {
      headers: mechanicHeaders(userId),
    });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function updateMechanicProfile(
  payload: Partial<MechanicProfile>,
  userId?: string | null
): Promise<MechanicProfile> {
  return request<MechanicProfile>(`${BASE}/mechanic/me`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...mechanicHeaders(userId) },
    body: JSON.stringify(payload),
  });
}

export async function uploadMechanicPhoto(file: File, userId?: string | null): Promise<{ profile_photo_url: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${getApiBase()}/api/v1/mechanic/me/photo`, {
    method: "POST",
    headers: userId ? { "X-Mechanic-User-Id": userId } : {},
    body: form,
  });
  const body = await res.text();
  if (!res.ok) throw new ApiError(body || `HTTP ${res.status}`, res.status, body);
  const data = JSON.parse(body) as { profile_photo_url: string };
  return { profile_photo_url: data.profile_photo_url };
}
