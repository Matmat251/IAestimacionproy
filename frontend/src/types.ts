export type Activity = {
  id: string;
  phase: string;
  name: string;
  profile: string;
  categoria?: string;
  requisitos_ids?: string[];
  api_documentada?: boolean;
  depends_on: string[];
  optimistic_hours: number;
  most_likely_hours: number;
  pessimistic_hours: number;
  expected_hours: number;
  rationale: string;
};

export type Risk = {
  description: string;
  impact: "bajo" | "medio" | "alto";
  mitigation: string;
};

export type RoleCost = {
  profile: string;
  hours: number;
  people: number;
  rate: number;
  cost: number;
};

export type Plan = {
  roles: RoleCost[];
  duration_weeks: number;
  total_cost: number;
};

export type Audit = {
  approved: boolean;
  findings: string[];
  warnings?: string[];
  iterations: number;
};

export type DiscardedAlternative = {
  nombre: string;
  motivo: string;
};

export type TechJustification = {
  nombre: string;
  categoria?: string;
  justificacion: string;
  requisitos_ids: string[];
  restricciones_ids?: string[];
  alternativas_descartadas: DiscardedAlternative[];
  compatible_con_infra?: boolean;
};

export type Requirement = {
  id?: string;
  title: string;
  detail: string;
  kind: string;
  origen?: "explicito" | "implicito" | "supuesto";
  cita_textual?: string | null;
  contiene_cifra?: boolean;
  requiere_confirmacion?: boolean;
  confirmado?: boolean;
  confidence: number;
};

export type DraftResponse = {
  project_name: string;
  status: "needs_clarification" | "ready_for_review";
  requirements: Requirement[];
  missing_fields: string[];
  questions: string[];
  activities: Activity[];
  total_expected_hours: number;
  notes: string[];
  complexity: "baja" | "media" | "alta";
  risks: Risk[];
  recommended_technologies?: string[];
  infra_profile?: "hosting_compartido" | "vps" | "cloud";
  tech_justifications?: TechJustification[];
  plan: Plan | null;
  audit: Audit | null;
};

export type SavedEstimation = {
  id: number;
  project_name: string;
  status: string;
  reviewer: string;
  comment: string;
  created_at: string;
};
