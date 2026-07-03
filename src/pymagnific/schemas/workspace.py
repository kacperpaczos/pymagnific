"""Workspace models: one Magnific Space, multiplied pipeline instances."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

WORKSPACE_SCHEMA_VERSION = "workspace/1"
INSTANCE_SCHEMA_VERSION = "instance/1"
DeployStatus = Literal["pending", "uploaded", "prepared", "ready"]


class WorkspaceMeta(BaseModel):
    workspace_id: str
    space_ref: str
    space_id: str | None = None
    schema_version: str = WORKSPACE_SCHEMA_VERSION
    description: str | None = None


class SharedPrompts(BaseModel):
    color_generator_base: str = ""
    composite_instructions_base: str = ""
    material_prompt_generator_base: str = ""
    shots_prompt_generator_base: str = ""
    negative_fragments: list[str] = Field(default_factory=list)


class WorkspaceTemplate(BaseModel):
    template_id: str = "ecommerce_raw"
    board_file: str = "../templates/ecommerce_raw/board.json"
    space_id: str | None = None


class WorkspaceManifest(BaseModel):
    meta: WorkspaceMeta
    template: WorkspaceTemplate | None = None
    shared_prompts: SharedPrompts = Field(default_factory=SharedPrompts)
    pipeline_ids: list[str] = Field(default_factory=list)

    def uses_ecommerce_raw_template(self) -> bool:
        return self.template is not None and self.template.template_id == "ecommerce_raw"

    def uses_do3d_textures_template(self) -> bool:
        return self.template is not None and self.template.template_id == "do3d_textures_2d"


class BackgroundAsset(BaseModel):
    id: str
    file: str
    tags: list[str] = Field(default_factory=list)


class PipelineAssets(BaseModel):
    product: str = "assets/product.jpg"
    material: str = "assets/material.jpg"
    backgrounds: list[BackgroundAsset] = Field(default_factory=list)


class ColorEntry(BaseModel):
    id: str
    text: str
    pilot: bool = True


class ColorGeneratorPrompt(BaseModel):
    model: str = "imagen-nano-banana-2"
    aspect_ratio: str = "1:1"
    resolution: str = "1k"
    product_addon: str = ""
    full: str = ""


class ImageGeneratorPrompt(BaseModel):
    """Flat image-generator prompt (do3d texture / print_flat)."""

    model: str = "imagen-nano-banana-2-flash"
    aspect_ratio: str = "1:1"
    resolution: str = "1k"
    full: str = ""


class CompositePromptGenerator(BaseModel):
    model: str = "GEMINI31_PRO"
    product_addon: str = ""
    instructions: str = ""


class MaterialPromptGenerator(BaseModel):
    model: str = "CLAUDE_OPUS_4_5"
    product_addon: str = ""
    instructions: str = ""


class ShotsPromptGenerator(BaseModel):
    model: str = "GEMINI31_PRO"
    product_addon: str = ""
    instructions: str = ""


class PipelinePrompts(BaseModel):
    color_generator: ColorGeneratorPrompt = Field(default_factory=ColorGeneratorPrompt)
    colors: list[ColorEntry] = Field(default_factory=list)
    placement_hints: list[str] = Field(default_factory=list)
    shot_ideas: list[str] = Field(default_factory=list)
    material_prompt_generator: MaterialPromptGenerator = Field(
        default_factory=MaterialPromptGenerator
    )
    shots_prompt_generator: ShotsPromptGenerator = Field(default_factory=ShotsPromptGenerator)
    composite_prompt_generator: CompositePromptGenerator = Field(
        default_factory=CompositePromptGenerator
    )
    texture_generator: ImageGeneratorPrompt = Field(default_factory=ImageGeneratorPrompt)
    print_flat_generator: ImageGeneratorPrompt = Field(default_factory=ImageGeneratorPrompt)


class MagnificInstanceBinding(BaseModel):
    panel_name: str = ""
    space_id: str | None = None
    nodes: dict[str, str] = Field(default_factory=dict)
    provisioned_at: str | None = None
    note: str | None = None
    asset_bindings: dict[str, dict[str, str]] = Field(default_factory=dict)


class PipelineJob(BaseModel):
    job_id: str
    product_id: str | None = None
    phase: str = "pilot"
    enabled: bool = True
    steps: list[dict[str, Any]] = Field(default_factory=list)
    qc_checklist: list[str] = Field(default_factory=list)
    note: str | None = None


class PipelineInstance(BaseModel):
    schema_version: str = INSTANCE_SCHEMA_VERSION
    pipeline_id: str
    product_id: str
    name: str | None = None
    enabled: bool = True
    deploy_status: DeployStatus = "pending"
    assets: PipelineAssets = Field(default_factory=PipelineAssets)
    prompts: PipelinePrompts = Field(default_factory=PipelinePrompts)
    jobs: list[PipelineJob] = Field(default_factory=list)
    magnific: MagnificInstanceBinding = Field(default_factory=MagnificInstanceBinding)

    def pilot_colors(self) -> list[ColorEntry]:
        return [c for c in self.prompts.colors if c.pilot]

    def color_texts(self, *, pilot_only: bool = False) -> list[str]:
        entries = self.pilot_colors() if pilot_only else self.prompts.colors
        return [e.text for e in entries]

    def instance_dir_name(self) -> str:
        return self.product_id
