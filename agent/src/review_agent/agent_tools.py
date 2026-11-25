"""The investigator's own tools (beside the intel tools): argument models and descriptions,
as sent to the model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .findings import FindingInput


class ReportArgs(BaseModel):
    findings: list[FindingInput] = Field(min_length=1)


class UpdateArgs(BaseModel):
    id: str = Field(description="finding id, e.g. F2")
    withdraw: bool = False
    reason: str | None = None
    title: str | None = None
    description: str | None = None
    category: FindingInput.model_fields["category"].annotation | None = None
    severity: FindingInput.model_fields["severity"].annotation | None = None
    condition: str | None = None
    existing_code: str | None = None
    suggestion: str | None = None
    evidence: list[str] | None = None


class CandidateInput(BaseModel):
    concern: str = Field(description="one line: what might be wrong")
    unit: str | None = Field(default=None, description="unit handle, e.g. U3")
    priority: Literal["high", "medium", "low"] = "medium"


class CandidatesArgs(BaseModel):
    add: list[CandidateInput] = Field(default_factory=list)
    dismiss: list[str] = Field(
        default_factory=list,
        description="candidates checked and not worth reporting, as 'K2: reason'",
    )


class FinishArgs(BaseModel):
    summary: str = Field(description="one or two sentences on what was reviewed")
    unreviewed: list[str] = Field(
        default_factory=list, description="unit handles you could not review, if any"
    )
    dismissed: list[str] = Field(
        default_factory=list,
        description="candidates you decided not to report, as 'K2: reason'",
    )


AGENT_TOOLS = {
    "note_candidates": (
        CandidatesArgs,
        "Keep your list of candidate concerns: add new ones (they get ids K1, K2, ...) and "
        "dismiss checked ones. The open list is shown back to you in progress notes.",
    ),
    "report_finding": (
        ReportArgs,
        "Report one or more concerns. findings is an array of objects; each needs path, "
        "existing_code (lines copied from tool output), title, description, category, "
        'severity and evidence (an array of evidence ids, e.g. ["2f371f2e7f44"]). Fill '
        "condition for a conditional risk and candidate when it resolves a K#; set about_removal "
        "only when removing the code is itself the problem.",
    ),
    "update_finding": (UpdateArgs, "Correct a reported finding, or withdraw it."),
    "finish": (FinishArgs, "End the review of this assignment."),
}


def validation_message(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in item['loc']) or 'arguments'}: {item['msg']}"
        for item in exc.errors()[:5]
    )
