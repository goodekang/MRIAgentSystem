from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..core.schemas import Domain, QuantitativeReport, Severity, VerificationIssue, VerificationResult


class VerificationAuditor:
    def __init__(self) -> None:
        self._bounds: dict[str, tuple[float, float]] = {
            "lvef": (15.0, 85.0),
            "rvef": (10.0, 85.0),
            "hippocampal_volume": (1.5, 6.0),
            "total_intracranial_volume": (900.0, 1900.0),
            "mean_cortical_thickness": (1.5, 4.0),
            "whole_tumour_volume": (0.0, 250.0),
            "tumour_core_volume": (0.0, 200.0),
            "enhancing_tumour_volume": (0.0, 150.0),
            "brain_age": (18.0, 110.0),
        }
        self._derived_checks: dict[Domain, tuple[Callable[[QuantitativeReport], list[VerificationIssue]], ...]] = {
            Domain.CARDIAC: (self._cardiac_consistency,),
            Domain.NEURODEGENERATION: (self._neuro_consistency,),
            Domain.BRAIN_TUMOUR: (self._tumour_consistency,),
        }

    def audit(self, report: QuantitativeReport, retry_count: int = 0) -> VerificationResult:
        issues: list[VerificationIssue] = []
        issues.extend(self._integrity(report))
        issues.extend(self._plausibility(report))
        for check in self._derived_checks.get(report.domain, ()):
            issues.extend(check(report))
        status = self._status(issues)
        confidence = self._confidence(status, issues, retry_count)
        retry_target = self._retry_target(issues, retry_count)
        return VerificationResult(status=status, confidence=confidence, issues=issues, retry_target=retry_target)

    def _integrity(self, report: QuantitativeReport) -> list[VerificationIssue]:
        issues: list[VerificationIssue] = []
        if not report.task_id:
            issues.append(self._issue("missing_task_id", "task_id is required", Severity.ERROR, "task_id", "rebuild_report"))
        if not report.biomarkers:
            issues.append(self._issue("missing_biomarkers", "biomarkers are required", Severity.ERROR, "biomarkers", "rerun_analysis"))
        for name, biomarker in report.biomarkers.items():
            if biomarker.value is None:
                issues.append(self._issue("null_value", f"{name} is null", Severity.ERROR, name, "rerun_analysis"))
            if not biomarker.unit:
                issues.append(self._issue("missing_unit", f"{name} has no unit", Severity.ERROR, name, "normalise_units"))
            if not biomarker.source:
                issues.append(self._issue("missing_source", f"{name} has no source", Severity.WARNING, name, "append_provenance"))
        return issues

    def _plausibility(self, report: QuantitativeReport) -> list[VerificationIssue]:
        issues: list[VerificationIssue] = []
        for name, bounds in self._bounds.items():
            biomarker = report.biomarkers.get(name)
            if biomarker is None:
                continue
            value = self._number(biomarker.value)
            if value is None:
                issues.append(self._issue("non_numeric_value", f"{name} is not numeric", Severity.ERROR, name, "normalise_value"))
                continue
            lo, hi = bounds
            if value < lo or value > hi:
                issues.append(
                    self._issue(
                        "physiological_bound",
                        f"{name}={value:.4g} outside [{lo}, {hi}]",
                        Severity.ERROR,
                        name,
                        "rerun_or_flag_case",
                    )
                )
        return issues

    def _cardiac_consistency(self, report: QuantitativeReport) -> list[VerificationIssue]:
        issues: list[VerificationIssue] = []
        lv_ed = self._metric(report, "lv_ed_volume")
        lv_es = self._metric(report, "lv_es_volume")
        rv_ed = self._metric(report, "rv_ed_volume")
        rv_es = self._metric(report, "rv_es_volume")
        if lv_ed is not None and lv_es is not None and lv_ed <= lv_es:
            issues.append(self._issue("lv_phase_order", "lv_ed_volume must exceed lv_es_volume", Severity.ERROR, "lv_ed_volume", "reselect_cardiac_phases"))
        if rv_ed is not None and rv_es is not None and rv_ed <= rv_es:
            issues.append(self._issue("rv_phase_order", "rv_ed_volume must exceed rv_es_volume", Severity.ERROR, "rv_ed_volume", "reselect_cardiac_phases"))
        return issues

    def _neuro_consistency(self, report: QuantitativeReport) -> list[VerificationIssue]:
        issues: list[VerificationIssue] = []
        left = self._metric(report, "left_hippocampus")
        right = self._metric(report, "right_hippocampus")
        total = self._metric(report, "hippocampal_volume")
        if left is not None and right is not None and total is not None and abs(total - left - right) > 0.05:
            issues.append(self._issue("hippocampal_sum", "hippocampal_volume must equal left plus right", Severity.ERROR, "hippocampal_volume", "recompute_derived_metrics"))
        if left and right and abs(left - right) / max(left, right) > 0.3:
            issues.append(self._issue("hippocampal_asymmetry", "hippocampal asymmetry exceeds expected range", Severity.WARNING, "left_hippocampus", "manual_review"))
        return issues

    def _tumour_consistency(self, report: QuantitativeReport) -> list[VerificationIssue]:
        issues: list[VerificationIssue] = []
        whole = self._metric(report, "whole_tumour_volume")
        core = self._metric(report, "tumour_core_volume")
        enhancing = self._metric(report, "enhancing_tumour_volume")
        if whole is not None and core is not None and core > whole:
            issues.append(self._issue("core_exceeds_whole", "tumour_core_volume must not exceed whole_tumour_volume", Severity.ERROR, "tumour_core_volume", "refuse_mask_fusion"))
        if whole is not None and enhancing is not None and enhancing > whole:
            issues.append(self._issue("enhancing_exceeds_whole", "enhancing_tumour_volume must not exceed whole_tumour_volume", Severity.ERROR, "enhancing_tumour_volume", "refuse_mask_fusion"))
        return issues

    def _metric(self, report: QuantitativeReport, name: str) -> float | None:
        biomarker = report.biomarkers.get(name)
        return self._number(biomarker.value) if biomarker else None

    def _number(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _status(self, issues: list[VerificationIssue]) -> str:
        if any(issue.severity == Severity.ERROR for issue in issues):
            return "failed"
        if issues:
            return "warning"
        return "passed"

    def _confidence(self, status: str, issues: list[VerificationIssue], retry_count: int) -> float:
        base = {"passed": 0.96, "warning": 0.78, "failed": 0.45}[status]
        penalty = min(0.2, retry_count * 0.05 + len(issues) * 0.015)
        return max(0.0, round(base - penalty, 4))

    def _retry_target(self, issues: list[VerificationIssue], retry_count: int) -> str | None:
        if retry_count >= 2 or not any(issue.severity == Severity.ERROR for issue in issues):
            return None
        action_counts: dict[str, int] = {}
        for issue in issues:
            if issue.suggested_action:
                action_counts[issue.suggested_action] = action_counts.get(issue.suggested_action, 0) + 1
        if not action_counts:
            return "quantitative_analyzer"
        action = max(action_counts, key=action_counts.get)
        if action in {"reselect_cardiac_phases", "recompute_derived_metrics", "normalise_value"}:
            return "quantitative_analyzer"
        if action in {"normalise_units", "append_provenance", "rebuild_report"}:
            return "report_serializer"
        return "preprocessing_coordinator"

    def _issue(
        self,
        code: str,
        message: str,
        severity: Severity,
        field: str | None,
        suggested_action: str | None,
    ) -> VerificationIssue:
        return VerificationIssue(code, message, severity, field, suggested_action)
