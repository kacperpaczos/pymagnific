"""Build exec jobs for ecommerce_raw pipeline instances."""

from __future__ import annotations

from typing import Any

from pymagnific.schemas.workspace import PipelineInstance, PipelineJob, WorkspaceManifest


def _pilot_color_ids(instance: PipelineInstance) -> list[str]:
    return [c.id for c in instance.pilot_colors()]


def build_ecommerce_raw_jobs(
    instance: PipelineInstance,
    *,
    include_material: bool = False,
) -> list[PipelineJob]:
    """Jobs: optional material -> color (pilot) -> photoshoot."""
    product_id = instance.product_id
    pilot_colors = _pilot_color_ids(instance)
    shot_count = len(instance.prompts.shot_ideas or instance.prompts.placement_hints)

    jobs: list[PipelineJob] = []

    if pilot_colors:
        first_color = pilot_colors[0]
        steps: list[dict[str, Any]] = []
        order = 1
        if include_material:
            steps.append(
                {
                    "order": order,
                    "stage": "stage_material",
                    "action": "spaces_run",
                    "expected_output": "1 obraz w Material variation generator output",
                }
            )
            order += 1
        steps.append(
            {
                "order": order,
                "stage": "stage_color",
                "action": "spaces_run",
                "inputs": {"colors_list": [first_color]},
                "expected_output": "1 obraz w Color variation list",
            }
        )
        order += 1
        steps.append(
            {
                "order": order,
                "stage": "stage_photoshoot",
                "action": "spaces_run",
                "inputs": {"shot_ideas_count": min(shot_count, 3) or 1},
                "expected_output": "Product shot list images",
            }
        )
        jobs.append(
            PipelineJob(
                job_id=f"pilot-{product_id}-{first_color.split('-')[-1]}-photoshoot",
                product_id=product_id,
                phase="pilot",
                enabled=True,
                steps=steps,
                qc_checklist=_qc_for_product(product_id),
            )
        )

    if len(pilot_colors) > 1:
        steps = []
        order = 1
        if include_material:
            steps.append(
                {
                    "order": order,
                    "stage": "stage_material",
                    "action": "spaces_run",
                    "expected_output": "Material variation",
                }
            )
            order += 1
        steps.append(
            {
                "order": order,
                "stage": "stage_color",
                "action": "spaces_run",
                "inputs": {"colors_list": pilot_colors},
                "expected_output": f"{len(pilot_colors)} obrazy w Color variation list",
            }
        )
        order += 1
        steps.append(
            {
                "order": order,
                "stage": "stage_photoshoot",
                "action": "spaces_run",
                "expected_output": "Product shots for all color variants",
            }
        )
        jobs.append(
            PipelineJob(
                job_id=f"pilot-{product_id}-full-colors-photoshoot",
                product_id=product_id,
                phase="pilot",
                enabled=True,
                steps=steps,
                qc_checklist=_qc_for_product(product_id),
            )
        )

    return jobs


def _qc_for_product(product_id: str) -> list[str]:
    if product_id == "77":
        return [
            "Spirala biala widoczna po lewej",
            "Tekst MOMENTS czytelny",
            "Proporcje portrait ~0.47",
            "Scena zgodna z shot idea",
        ]
    if product_id == "79":
        return [
            "Otwor na klamke widoczny",
            "Typografia Do Not Disturb czytelna",
            "Scena hotelowa naturalna",
        ]
    if product_id == "206":
        return [
            "Perforacja i gorna krawedz zszywu widoczne",
            "Linie i numeracja czytelne",
            "Kolory zgodne z lista",
            "Scena zgodna z shot idea",
        ]
    if product_id == "738":
        return [
            "Kieszenie i klapa teczki widoczne",
            "Nadruk/logo czytelny",
            "Proporcje A4 landscape",
            "Scena zgodna z shot idea",
        ]
    if product_id == "947":
        return [
            "Spot UV 3D widoczny i nietkniety",
            "Ksztalt die-cut zachowany",
            "Kolory zgodne z lista",
            "Scena zgodna z shot idea",
        ]
    if product_id == "828":
        return [
            "Otwor na metke i sznurek widoczne",
            "Nadruk czytelny",
            "Proporcje metki zachowane",
            "Scena zgodna z shot idea",
        ]
    if product_id == "130":
        return [
            "Linie die-cut i skrzydelka pudelka czytelne",
            "Nadruk/branding czytelny",
            "Proporcje pudelka zachowane",
            "Scena zgodna z shot idea",
        ]
    return ["Produkt czytelny", "Kolory zgodne z lista", "Scena zgodna z shot idea"]


def build_do3d_textures_jobs(instance: PipelineInstance) -> list[PipelineJob]:
    """Jobs: texture swatch -> print-flat photo (2 stages per reference)."""
    product_id = instance.product_id
    return [
        PipelineJob(
            job_id=f"pilot-{product_id}-texture-print-flat",
            product_id=product_id,
            phase="pilot",
            enabled=True,
            steps=[
                {
                    "order": 1,
                    "stage": "stage_texture",
                    "action": "spaces_run",
                    "expected_output": "1 obraz w Texture generator output",
                },
                {
                    "order": 2,
                    "stage": "stage_print_flat",
                    "action": "spaces_run",
                    "expected_output": "1 obraz w Print flat generator output",
                },
            ],
            qc_checklist=[
                "Texture: brak tekstu i logo, widoczny swatch materiału",
                "Print flat: tekst poziomy, czytelny, bez perspektywy i skosu",
            ],
        )
    ]


def jobs_for_instance(
    instance: PipelineInstance,
    workspace: WorkspaceManifest,
    *,
    spec_jobs: list[dict[str, Any]] | None = None,
) -> list[PipelineJob]:
    """Pick jobs: ecommerce_raw, do3d_textures_2d, or composite jobs from spec."""
    if workspace.uses_ecommerce_raw_template():
        return build_ecommerce_raw_jobs(instance, include_material=False)
    if workspace.uses_do3d_textures_template():
        return build_do3d_textures_jobs(instance)

    jobs: list[PipelineJob] = []
    if spec_jobs:
        for job_data in spec_jobs:
            if str(job_data.get("product_id")) == str(instance.product_id):
                jobs.append(PipelineJob.model_validate(job_data))
    return jobs
