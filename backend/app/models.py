from typing import Any, Literal
from pydantic import BaseModel, Field, computed_field, field_validator


class ProjectInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=20, max_length=20000)
    scope: str = ""
    technology: str = ""
    integrations: str = ""
    constraints: str = ""
    project_status: Literal["new", "existing"] = "new"
    completed_work: str = ""


class Requirement(BaseModel):
    id: str = "R1"
    title: str = "Requerimiento"
    detail: str = ""
    kind: Literal["functional", "non_functional", "assumption"] = "functional"
    origen: Literal["explicito", "implicito", "supuesto"] = "explicito"
    cita_textual: str | None = None
    contiene_cifra: bool = False
    requiere_confirmacion: bool = False
    confirmado: bool = True
    confidence: float = Field(default=0.85, ge=0, le=1)

    @field_validator("kind", mode="before")
    @classmethod
    def _norm_kind(cls, v: Any) -> str:
        s = str(v or "").lower().strip()
        if "non" in s or "no_" in s or "no " in s:
            return "non_functional"
        if "assum" in s or "supuest" in s:
            return "assumption"
        return "functional"

    @field_validator("origen", mode="before")
    @classmethod
    def _norm_origen(cls, v: Any) -> str:
        s = str(v or "").lower().strip().replace("í", "i")
        if "supuest" in s or "assum" in s:
            return "supuesto"
        if "implic" in s:
            return "implicito"
        return "explicito"


class DiscardedAlternative(BaseModel):
    nombre: str = "Alternativa"
    motivo: str = "Menor ajuste al perfil del proyecto"


class TechJustification(BaseModel):
    nombre: str
    categoria: str = "general"
    justificacion: str = ""
    requisitos_ids: list[str] = Field(default_factory=list)
    restricciones_ids: list[str] = Field(default_factory=list)
    alternativas_descartadas: list[DiscardedAlternative] = Field(default_factory=list)
    compatible_con_infra: bool = True


class Activity(BaseModel):
    id: str = "A1"
    phase: str
    name: str
    profile: str
    categoria: str = "desarrollo"
    requisitos_ids: list[str] = Field(default_factory=list)
    api_documentada: bool = True
    depends_on: list[str] = Field(default_factory=list)
    optimistic_hours: float = Field(ge=0)
    most_likely_hours: float = Field(ge=0)
    pessimistic_hours: float = Field(ge=0)
    rationale: str

    @computed_field
    @property
    def expected_hours(self) -> float:
        return round((self.optimistic_hours + 4 * self.most_likely_hours + self.pessimistic_hours) / 6, 1)


class Risk(BaseModel):
    description: str = ""
    impact: Literal["bajo", "medio", "alto"] = "medio"
    mitigation: str = ""

    @field_validator("impact", mode="before")
    @classmethod
    def _norm_impact(cls, v: Any) -> str:
        s = str(v or "").lower().strip()
        if "alt" in s or "high" in s or "crit" in s:
            return "alto"
        if "baj" in s or "low" in s:
            return "bajo"
        return "medio"


class RoleCost(BaseModel):
    profile: str
    hours: float
    people: int
    rate: float
    cost: float


class Plan(BaseModel):
    roles: list[RoleCost]
    duration_weeks: float
    total_cost: float
    p50_hours: float = 0.0
    p80_hours: float = 0.0
    p50_cost: float = 0.0
    p80_cost: float = 0.0


class Audit(BaseModel):
    approved: bool
    findings: list[str]
    warnings: list[str] = Field(default_factory=list)
    iterations: int


class RagEvidence(BaseModel):
    nombre: str
    tecnologias: str = ""
    complejidad: str = "media"
    fase: str = "General"
    horas_reales: float = 0.0
    similarity: float = 0.0
    source: Literal["historico_csv", "estimacion_aprobada"] = "historico_csv"


class DraftRequest(BaseModel):
    project: ProjectInput
    clarification_answers: dict[str, str] = Field(default_factory=dict)


class DraftResponse(BaseModel):
    project_name: str
    status: Literal["needs_clarification", "ready_for_review"]
    requirements: list[Requirement]
    missing_fields: list[str]
    questions: list[str]
    activities: list[Activity]
    total_expected_hours: float
    notes: list[str] = Field(default_factory=list)
    complexity: Literal["baja", "media", "alta"] = "media"
    risks: list[Risk] = Field(default_factory=list)
    recommended_technologies: list[str] = Field(default_factory=list)
    infra_profile: Literal["hosting_compartido", "vps", "cloud"] = "vps"
    tech_justifications: list[TechJustification] = Field(default_factory=list)
    plan: Plan | None = None
    audit: Audit | None = None
    rag_evidence: list[RagEvidence] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    approved: bool
    reviewer: str = Field(min_length=2)
    comment: str = ""
    draft: DraftResponse
