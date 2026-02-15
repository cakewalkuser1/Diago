/**
 * API client for the Diago FastAPI backend.
 * All requests go through the Vite proxy (or direct in production).
 */

import type {
  BehavioralContext,
  DiagnosisResponse,
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
}

export interface ChatResponsePayload {
  content: string;
  error?: string;
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
