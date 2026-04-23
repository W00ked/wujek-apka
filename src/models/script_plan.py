from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SectionId = Literal["header", "meal_intro", "nutrition", "ingredients", "insights"]
SECTION_ORDER: tuple[SectionId, ...] = ("header", "meal_intro", "nutrition", "ingredients", "insights")


class ScriptSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section_id: SectionId
    script: str = Field(min_length=1)
    duration_sec: float = Field(gt=0)
    pause_after_sec: float = Field(ge=0)  # required in JSON schema (OpenAI strict: all props in "required")


class ScriptPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hook_line: str = Field(min_length=1)
    segments: list[ScriptSegment] = Field(min_length=1)

    @field_validator("segments")
    @classmethod
    def unique_sections(cls, value: list[ScriptSegment]) -> list[ScriptSegment]:
        seen: set[str] = set()
        for segment in value:
            if segment.section_id in seen:
                raise ValueError(f"duplicate section_id: {segment.section_id}")
            seen.add(segment.section_id)
        section_order = tuple(segment.section_id for segment in value)
        if section_order != SECTION_ORDER:
            raise ValueError(f"segments must use exact section order: {', '.join(SECTION_ORDER)}")
        return value

    @model_validator(mode="after")
    def validate_total_duration(self) -> "ScriptPlan":
        total = sum(segment.duration_sec for segment in self.segments)
        if total <= 0:
            raise ValueError("segment durations must sum to more than zero")
        return self

    @property
    def total_duration_sec(self) -> float:
        return sum(segment.duration_sec for segment in self.segments)

    def voiceover_text(self) -> str:
        return " ".join(segment.script.strip() for segment in self.segments if segment.script.strip())

    def tts_transcript_text(self) -> str:
        return "\n".join(segment.script.strip() for segment in self.segments if segment.script.strip())

    def scaled_segments(self, target_duration_sec: float) -> list[ScriptSegment]:
        if target_duration_sec <= 0:
            raise ValueError("target_duration_sec must be positive")

        current_total = self.total_duration_sec
        scale = target_duration_sec / current_total
        scaled: list[ScriptSegment] = []
        for segment in self.segments:
            duration = round(segment.duration_sec * scale, 3)
            if duration <= 0:
                raise ValueError("scaled duration must stay positive")
            scaled.append(
                ScriptSegment(
                    section_id=segment.section_id,
                    script=segment.script,
                    duration_sec=duration,
                    pause_after_sec=round(segment.pause_after_sec * scale, 3),
                )
            )
        return scaled
