const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';
export const WS_BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000').replace('http', 'ws');

export interface CaseSummary {
  id: string;
  case_number: string;
  relation_type: string;
  hospital_name: string;
  organ_type: string;
  status: string;
  created_at: string;
}

export interface RuleResult {
  rule_code: string;
  rule_description: string;
  thoa_reference: string;
  evidence: string;
  next_step: string;
  needs_legal_verification: boolean;
}

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
  page: number;
}

export interface CaseDetail {
  id: string;
  case_number: string;
  relation_type: string;
  hospital_name: string;
  organ_type: string;
  status: string;
  created_at: string;
  donor: { full_name: string; age: number };
  recipient: { full_name: string; age: number };
  flags: string[];
  explanations: RuleResult[];
  bounding_boxes?: Record<string, BoundingBox | null>;
}

export interface AuditLog {
  id: string;
  action: string;
  detail: any;
  created_at: string;
  user_id: string;
}

export async function fetchCases(): Promise<CaseSummary[]> {
  const res = await fetch(`${API_BASE_URL}/cases`);
  if (!res.ok) throw new Error("Failed to fetch cases");
  return await res.json();
}

export async function fetchCaseDetails(id: string): Promise<CaseDetail> {
  const res = await fetch(`${API_BASE_URL}/cases/${id}/details`);
  if (!res.ok) throw new Error("Failed to fetch case details");
  return await res.json();
}

export async function fetchAuditLogs(id: string): Promise<AuditLog[]> {
  const res = await fetch(`${API_BASE_URL}/cases/${id}/audit`);
  if (!res.ok) throw new Error("Failed to fetch audit logs");
  return await res.json();
}

export interface CaseDocument {
  id: string;
  document_type: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  is_verified: boolean;
  created_at: string;
}

export async function fetchDocuments(caseId: string): Promise<CaseDocument[]> {
  const res = await fetch(`${API_BASE_URL}/cases/${caseId}/documents`);
  if (!res.ok) throw new Error("Failed to fetch documents");
  return await res.json();
}

export function getDocumentFileUrl(caseId: string, docId: string): string {
  return `${API_BASE_URL}/cases/${caseId}/documents/${docId}/file`;
}

export async function submitDecision(id: string, decision: string, comment: string, justification?: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/cases/${id}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, comment, justification })
  });
  if (!res.ok) throw new Error("Failed to submit decision");
}

export interface CaseCreatePayload {
  relation_type: string;
  hospital_name: string;
  organ_type: string;
  donor: {
    full_name: string;
    age: number;
    gender?: string;
    aadhaar_number: string;
    pan_number?: string;
    address?: string;
  };
  recipient: {
    full_name: string;
    age: number;
    gender?: string;
    aadhaar_number: string;
    pan_number?: string;
    address?: string;
  };
}

export async function createCase(data: CaseCreatePayload): Promise<CaseSummary> {
  const res = await fetch(`${API_BASE_URL}/cases`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create case");
  }
  return await res.json();
}

export async function uploadDocument(caseId: string, file: File, documentType: string): Promise<{ document_id: string; original_filename: string }> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_type', documentType);
  const res = await fetch(`${API_BASE_URL}/cases/${caseId}/documents`, {
    method: 'POST',
    body: formData
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to upload document");
  }
  return await res.json();
}

export async function triggerScreening(caseId: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE_URL}/cases/${caseId}/screen`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to trigger screening");
  }
  return await res.json();
}

export async function submitCorrection(
  caseId: string,
  fieldName: string,
  originalText: string,
  correctedText: string
): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/cases/${caseId}/corrections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      field_name: fieldName,
      original_text: originalText,
      corrected_text: correctedText
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to submit correction");
  }
}

export interface RenderedPageResponse {
  page_number: number;
  page_count: number;
  page_image: string | null;
  bounding_boxes: Array<{
    field: string;
    label: string;
    x: number;
    y: number;
    w: number;
    h: number;
    confidence: number;
  }>;
  error?: string;
}

export interface FraudAnalysisResponse {
  fraud_risk_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  verdict: string;
  ela_variance: number;
  signature_verification: {
    signature_zone_checked: boolean;
    ink_density: number;
    signatures_detected: boolean;
    status: string;
  };
  anomalies_detected: Array<{
    code: string;
    severity: string;
    title: string;
    description: string;
  }>;
  splice_boxes_count: number;
  heatmap_image?: string;
}

export async function fetchRenderedDocumentPage(
  caseId: string,
  docId: string,
  page: number = 0
): Promise<RenderedPageResponse> {
  const res = await fetch(`${API_BASE_URL}/cases/${caseId}/documents/${docId}/rendered?page=${page}`);
  if (!res.ok) throw new Error("Failed to fetch rendered document page");
  return await res.json();
}

export async function fetchFraudAnalysis(
  caseId: string,
  docId: string
): Promise<FraudAnalysisResponse> {
  const res = await fetch(`${API_BASE_URL}/cases/${caseId}/documents/${docId}/fraud-check`);
  if (!res.ok) throw new Error("Failed to fetch document fraud analysis");
  return await res.json();
}

