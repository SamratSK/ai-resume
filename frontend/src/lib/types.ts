// Mirrors backend pydantic models (resume_pipeline.schema / scoring.*).
// Kept intentionally close to the JSON shape so no mapping layer is needed.

export type Confidence = "high" | "medium" | "low";
export type ParseQuality = "Clean" | "Partial" | "Failed";
export type ParseMethod = "docling" | "docling+ocr" | "text" | "xml" | "unsupported";

export interface FieldValue {
  raw_value: string | null;
  normalized_value: unknown;
  scale: string | null;
  confidence: Confidence | null;
  evidence: string | null;
  assumption: string | null;
}

export interface ProjectEntry {
  title: string | null;
  one_liner: string | null;
  evidence: string | null;
  confidence: Confidence | null;
}

export interface ExperienceEntry {
  company: string | null;
  role: string | null;
  duration: string | null;
  evidence: string | null;
  confidence: Confidence | null;
}

export interface AdditionalField {
  field_name: string;
  raw_value: string | null;
  normalized_value: unknown;
  data_type: string | null;
  confidence: Confidence | null;
  evidence: string | null;
}

export interface ResumeRecord {
  file: string;
  method: ParseMethod;
  parse_quality: ParseQuality;
  full_name: FieldValue | null;
  email: FieldValue | null;
  phone: FieldValue | null;
  college: FieldValue | null;
  degree: FieldValue | null;
  branch: FieldValue | null;
  graduation_year: FieldValue | null;
  cgpa: FieldValue | null;
  skills: FieldValue[];
  projects: ProjectEntry[];
  experience: ExperienceEntry[];
  certifications: FieldValue[];
  additional_fields: AdditionalField[];
  anomalies: string[];
}

export interface ResumeSummary {
  doc_id: string;
  file: string;
  method: ParseMethod;
  parse_quality: ParseQuality;
  anomaly_count: number;
}

export interface JobDescription {
  id: string;
  role: string;
  required_skills: string[];
  preferred_skills: string[];
  cgpa_min: number;
  slots: number;
}

export interface ComponentResult {
  points: number;
  max_points: number;
  source: "python" | "llm";
  detail: string;
  meta: Record<string, unknown> | null;
}

export type SkillTier = "exact" | "synonym" | "partial" | "implicit" | "missing";

export interface SkillMatch {
  jd_skill: string;
  tier: SkillTier;
  matched_against: string | null;
  evidence: string | null;
  credit: number;
  flagged: boolean;
  note: string | null;
}

export interface ScoredCandidate {
  rank: number | null;
  doc_id: string;
  file: string;
  parse_quality: ParseQuality;
  score: number | null;
  confidence: "High" | "Medium" | "Low" | null;
  human_review_required: boolean;
  breakdown: Record<string, ComponentResult> | null;
  required_skill_matches: SkillMatch[];
  preferred_skill_matches: SkillMatch[];
  reasoning_bullets: string[];
  anomalies: string[];
  error: string | null;
}

export interface ShortlistPayload {
  jd_id: string;
  role: string;
  slots: number;
  cutoff: number;
  candidates_evaluated: number;
  slots_filled_note: string | null;
  shortlist: ScoredCandidate[];
  reserve: ScoredCandidate[];
  excluded: ScoredCandidate[];
}

export interface JobStatus<TResult = unknown> {
  id: string;
  status: "pending" | "running" | "done" | "error";
  progress: string;
  result: TResult | null;
  error: string | null;
}

export interface ProvenancePage {
  page: number;
  width: number;
  height: number;
  image_url: string;
}

export interface ProvenanceLegendEntry {
  field: string;
  label: string;
  group: string;
  color: string;
  located: boolean;
  page: number | null;
  bbox: [number, number, number, number] | null;
  rendered_bbox: [number, number, number, number] | null;
  score: number | null;
}

export interface ProvenancePayload {
  available: boolean;
  reason: string | null;
  pages: ProvenancePage[];
  legend: ProvenanceLegendEntry[];
}

export interface ChatSource {
  resume_id: string;
  name: string;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  route_taken: "structured" | "semantic" | "hybrid";
}

export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
}
