from __future__ import annotations

from collections.abc import Mapping
from statistics import median
from typing import Any

from ..core.schemas import Domain, ImageStatistics, ProtocolCard, ProtocolClass


class ProtocolAnalyst:
    def analyse(
        self,
        metadata: Mapping[str, Any],
        intensities: list[float] | None = None,
        task_hint: str | None = None,
    ) -> ProtocolCard:
        stats = self._statistics(intensities or [])
        protocol, confidence, evidence = self._classify(metadata, task_hint)
        domain = self._domain(protocol, task_hint)
        constraints = self._constraints(protocol, domain, metadata)
        return ProtocolCard(
            protocol_class=protocol,
            domain=domain,
            confidence=confidence,
            metadata=dict(metadata),
            image_statistics=stats,
            evidence=evidence,
            preprocessing_constraints=constraints,
        )

    def _statistics(self, values: list[float]) -> ImageStatistics:
        if not values:
            return ImageStatistics()
        n = len(values)
        mean_value = sum(values) / n
        variance = sum((value - mean_value) ** 2 for value in values) / max(n - 1, 1)
        std_value = variance**0.5
        low_values = sorted(values)[: max(1, n // 20)]
        noise = sum(abs(value) for value in low_values) / len(low_values)
        snr = mean_value / noise if noise else None
        bins = self._histogram(values, 256)
        return ImageStatistics(
            mean=mean_value,
            median=median(values),
            std=std_value,
            coefficient_of_variation=std_value / mean_value if mean_value else None,
            snr=snr,
            histogram=bins,
        )

    def _histogram(self, values: list[float], bins: int) -> list[float]:
        lo = min(values)
        hi = max(values)
        if lo == hi:
            output = [0.0] * bins
            output[0] = float(len(values))
            return output
        width = (hi - lo) / bins
        output = [0.0] * bins
        for value in values:
            index = min(int((value - lo) / width), bins - 1)
            output[index] += 1.0
        return output

    def _classify(
        self,
        metadata: Mapping[str, Any],
        task_hint: str | None,
    ) -> tuple[ProtocolClass, float, list[str]]:
        sequence = str(metadata.get("sequence_name", metadata.get("SequenceName", ""))).lower()
        protocol = str(metadata.get("protocol_name", metadata.get("ProtocolName", ""))).lower()
        vendor = str(metadata.get("vendor", metadata.get("Manufacturer", ""))).lower()
        tr = self._float(metadata.get("repetition_time", metadata.get("RepetitionTime")))
        te = self._float(metadata.get("echo_time", metadata.get("EchoTime")))
        flip = self._float(metadata.get("flip_angle", metadata.get("FlipAngle")))
        text = " ".join([sequence, protocol, task_hint or ""]).lower()
        evidence: list[str] = []

        if "flair" in text:
            evidence.append("flair sequence token")
            return ProtocolClass.T2_FLAIR, 0.94, evidence
        if "mprage" in text or "spgr" in text or "bravo" in text:
            evidence.append("3d t1 structural token")
            return ProtocolClass.T1_MPRAGE, 0.95, evidence
        if "t1" in text and ("gd" in text or "ce" in text or "contrast" in text):
            evidence.append("contrast-enhanced t1 token")
            return ProtocolClass.T1_GD, 0.93, evidence
        if "ssfp" in text or "fiesta" in text or "truefisp" in text or "balanced" in text:
            evidence.append("balanced cine token")
            return ProtocolClass.CINE_SSFP, 0.93, evidence
        if "cine" in text and ("gre" in text or "flash" in text):
            evidence.append("gradient echo cine token")
            return ProtocolClass.CINE_GRE, 0.89, evidence
        if "dwi" in text or "diff" in text or "adc" in text:
            evidence.append("diffusion token")
            return ProtocolClass.DWI, 0.92, evidence
        if "swi" in text or "suscept" in text:
            evidence.append("susceptibility token")
            return ProtocolClass.SWI, 0.91, evidence
        if "mra" in text or "angio" in text or "tof" in text:
            evidence.append("angiography token")
            return ProtocolClass.MRA, 0.9, evidence
        if "pd" in text or "proton" in text:
            evidence.append("proton density token")
            return ProtocolClass.PD, 0.88, evidence
        if tr is not None and te is not None and tr < 900 and te < 30:
            evidence.append("short tr and short te")
            return ProtocolClass.T1_SE, 0.82, evidence
        if tr is not None and te is not None and tr > 1800 and te > 60:
            evidence.append("long tr and long te")
            return ProtocolClass.T2_SE, 0.82, evidence
        if "philips" in vendor and "tfe" in text and flip and flip > 8:
            evidence.append("vendor-specific t1 alias")
            return ProtocolClass.T1_MPRAGE, 0.78, evidence
        evidence.append("insufficient discriminative metadata")
        return ProtocolClass.UNKNOWN, 0.35, evidence

    def _domain(self, protocol: ProtocolClass, task_hint: str | None) -> Domain:
        hint = (task_hint or "").lower()
        if any(token in hint for token in ("tumour", "tumor", "brats", "glioma", "radiomics")):
            return Domain.BRAIN_TUMOUR
        if any(token in hint for token in ("cardiac", "heart", "ventricle", "acdc", "cine", "ejection")):
            return Domain.CARDIAC
        if any(token in hint for token in ("aibl", "adni", "hippocamp", "cortical", "atrophy", "brain age")):
            return Domain.NEURODEGENERATION
        if protocol in {ProtocolClass.CINE_SSFP, ProtocolClass.CINE_GRE}:
            return Domain.CARDIAC
        if protocol in {ProtocolClass.T1_MPRAGE, ProtocolClass.T1_SE, ProtocolClass.T1_GD, ProtocolClass.T2_FLAIR}:
            return Domain.BRAIN_TUMOUR
        return Domain.UNKNOWN

    def _constraints(
        self,
        protocol: ProtocolClass,
        domain: Domain,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        field_strength = self._float(metadata.get("field_strength", metadata.get("MagneticFieldStrength")))
        constraints: dict[str, Any] = {
            "normalisation": "zscore",
            "requires_temporal_alignment": domain == Domain.CARDIAC,
            "requires_skull_stripping": domain in {Domain.BRAIN_TUMOUR, Domain.NEURODEGENERATION},
        }
        if protocol == ProtocolClass.T2_FLAIR:
            constraints["normalisation"] = "percentile"
        if field_strength and field_strength <= 1.5:
            constraints["bias_correction_strength"] = "high"
        else:
            constraints["bias_correction_strength"] = "standard"
        return constraints

    def _float(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
