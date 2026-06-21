from __future__ import annotations

from typing import Any

from ..core.schemas import Biomarker, Domain, PreprocessingPlan, QuantitativeReport


class QuantitativeAnalyzer:
    def build_report(
        self,
        plan: PreprocessingPlan,
        task_id: str,
        measurements: dict[str, Any],
        provenance: list[dict[str, Any]] | None = None,
    ) -> QuantitativeReport:
        domain = plan.protocol_card.domain
        if domain == Domain.CARDIAC:
            biomarkers = self._cardiac(measurements)
        elif domain == Domain.NEURODEGENERATION:
            biomarkers = self._neurodegeneration(measurements)
        else:
            biomarkers = self._brain_tumour(measurements)
        return QuantitativeReport(
            task_id=task_id,
            domain=domain,
            protocol_class=plan.protocol_card.protocol_class,
            biomarkers=biomarkers,
            provenance=provenance or [],
            metadata={"route_id": plan.route_id},
        )

    def _brain_tumour(self, values: dict[str, Any]) -> dict[str, Biomarker]:
        voxel_volume = self._float(values.get("voxel_volume_mm3"), 1.0)
        whole = self._volume(values.get("whole_tumour_voxels"), voxel_volume)
        core = self._volume(values.get("tumour_core_voxels"), voxel_volume)
        enhancing = self._volume(values.get("enhancing_tumour_voxels"), voxel_volume)
        return {
            "whole_tumour_volume": Biomarker("whole_tumour_volume", whole, "cm3", "segmentation"),
            "tumour_core_volume": Biomarker("tumour_core_volume", core, "cm3", "segmentation"),
            "enhancing_tumour_volume": Biomarker("enhancing_tumour_volume", enhancing, "cm3", "segmentation"),
            "radiomics_feature_count": Biomarker(
                "radiomics_feature_count",
                int(values.get("radiomics_feature_count", 107)),
                "count",
                "radiomics",
            ),
        }

    def _cardiac(self, values: dict[str, Any]) -> dict[str, Biomarker]:
        lv_ed = self._float(values.get("lv_ed_volume_ml"))
        lv_es = self._float(values.get("lv_es_volume_ml"))
        rv_ed = self._float(values.get("rv_ed_volume_ml"))
        rv_es = self._float(values.get("rv_es_volume_ml"))
        myocardium = self._float(values.get("myocardial_volume_cm3"))
        lvef = ((lv_ed - lv_es) / lv_ed * 100.0) if lv_ed else 0.0
        rvef = ((rv_ed - rv_es) / rv_ed * 100.0) if rv_ed else 0.0
        mass = myocardium * 1.05
        return {
            "lv_ed_volume": Biomarker("lv_ed_volume", lv_ed, "ml", "segmentation"),
            "lv_es_volume": Biomarker("lv_es_volume", lv_es, "ml", "segmentation"),
            "rv_ed_volume": Biomarker("rv_ed_volume", rv_ed, "ml", "segmentation"),
            "rv_es_volume": Biomarker("rv_es_volume", rv_es, "ml", "segmentation"),
            "lvef": Biomarker("lvef", lvef, "%", "derived"),
            "rvef": Biomarker("rvef", rvef, "%", "derived"),
            "myocardial_mass": Biomarker("myocardial_mass", mass, "g", "derived"),
            "wall_thickness": Biomarker("wall_thickness", self._float(values.get("wall_thickness_mm")), "mm", "derived"),
        }

    def _neurodegeneration(self, values: dict[str, Any]) -> dict[str, Biomarker]:
        left = self._float(values.get("left_hippocampus_cm3"))
        right = self._float(values.get("right_hippocampus_cm3"))
        return {
            "hippocampal_volume": Biomarker("hippocampal_volume", left + right, "cm3", "parcellation"),
            "left_hippocampus": Biomarker("left_hippocampus", left, "cm3", "parcellation"),
            "right_hippocampus": Biomarker("right_hippocampus", right, "cm3", "parcellation"),
            "mean_cortical_thickness": Biomarker(
                "mean_cortical_thickness",
                self._float(values.get("mean_cortical_thickness_mm")),
                "mm",
                "parcellation",
            ),
            "total_intracranial_volume": Biomarker(
                "total_intracranial_volume",
                self._float(values.get("total_intracranial_volume_cm3")),
                "cm3",
                "affine",
            ),
            "brain_age": Biomarker("brain_age", self._float(values.get("brain_age_years")), "years", "regression"),
        }

    def _volume(self, voxels: Any, voxel_volume_mm3: float) -> float:
        return self._float(voxels) * voxel_volume_mm3 / 1000.0

    def _float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
