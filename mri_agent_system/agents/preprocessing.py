from __future__ import annotations

from hashlib import sha1

from ..core.schemas import Domain, PreprocessingPlan, PreprocessingStep, ProtocolCard, ProtocolClass, ToolDescriptor


class ToolRegistry:
    def __init__(self, tools: list[ToolDescriptor] | None = None) -> None:
        self._tools = {tool.name: tool for tool in (tools or self._default_tools())}

    def compatible(self, card: ProtocolCard) -> list[ToolDescriptor]:
        selected: list[ToolDescriptor] = []
        for tool in self._tools.values():
            protocol_match = not tool.compatible_protocols or card.protocol_class in tool.compatible_protocols
            domain_match = not tool.compatible_domains or card.domain in tool.compatible_domains
            if protocol_match and domain_match:
                selected.append(tool)
        return selected

    def get(self, name: str) -> ToolDescriptor:
        return self._tools[name]

    def _default_tools(self) -> list[ToolDescriptor]:
        static_brain = (
            ProtocolClass.T1_MPRAGE,
            ProtocolClass.T1_SE,
            ProtocolClass.T1_GD,
            ProtocolClass.T2_SE,
            ProtocolClass.T2_FLAIR,
            ProtocolClass.T2_STAR,
            ProtocolClass.DWI,
            ProtocolClass.SWI,
        )
        cine = (ProtocolClass.CINE_SSFP, ProtocolClass.CINE_GRE)
        return [
            ToolDescriptor("convert", ("dicom",), ("nifti",), (), (), expected_runtime_s=12.0),
            ToolDescriptor("reorient", ("nifti",), ("nifti",), (), (), ("convert",), expected_runtime_s=5.0),
            ToolDescriptor("bias_field", ("nifti",), ("nifti",), static_brain, (), ("reorient",), expected_runtime_s=45.0),
            ToolDescriptor("skull_strip", ("nifti",), ("mask",), static_brain, (Domain.BRAIN_TUMOUR, Domain.NEURODEGENERATION), ("bias_field",), expected_runtime_s=30.0),
            ToolDescriptor("normalise", ("nifti",), ("nifti",), (), (), ("reorient",), expected_runtime_s=8.0),
            ToolDescriptor("resample", ("nifti",), ("nifti",), (), (), ("normalise",), expected_runtime_s=10.0),
            ToolDescriptor("register", ("nifti",), ("nifti",), static_brain, (Domain.BRAIN_TUMOUR, Domain.NEURODEGENERATION), ("resample",), expected_runtime_s=60.0),
            ToolDescriptor("motion_correct", ("nifti",), ("nifti",), cine, (Domain.CARDIAC,), ("convert",), expected_runtime_s=25.0),
            ToolDescriptor("temporal_align", ("nifti",), ("nifti",), cine, (Domain.CARDIAC,), ("motion_correct",), expected_runtime_s=18.0),
            ToolDescriptor("denoise", ("nifti",), ("nifti",), (), (), ("normalise",), expected_runtime_s=20.0),
            ToolDescriptor("artefact_detect", ("nifti",), ("qc",), (), (), ("resample",), expected_runtime_s=6.0),
        ]


class PreprocessingCoordinator:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry()

    def plan(self, card: ProtocolCard) -> PreprocessingPlan:
        tools = self.registry.compatible(card)
        ordered = self._topological_order(tools)
        steps = [self._step(tool, card, index) for index, tool in enumerate(ordered)]
        route_id = self._route_id(card, steps)
        qc = {
            "hash_inputs": True,
            "hash_outputs": True,
            "record_runtime": True,
            "retain_failed_attempts": True,
        }
        return PreprocessingPlan(protocol_card=card, steps=steps, route_id=route_id, qc_requirements=qc)

    def _step(self, tool: ToolDescriptor, card: ProtocolCard, index: int) -> PreprocessingStep:
        parameters = dict(tool.parameters)
        constraints = card.preprocessing_constraints
        if tool.name == "bias_field":
            parameters["strength"] = constraints.get("bias_correction_strength", "standard")
        if tool.name == "normalise":
            parameters["method"] = constraints.get("normalisation", "zscore")
        if tool.name == "resample":
            parameters["target_spacing"] = self._target_spacing(card)
        return PreprocessingStep(
            tool_name=tool.name,
            parameters=parameters,
            dependencies=tool.dependencies,
            parallel_group=self._parallel_group(tool, index),
        )

    def _topological_order(self, tools: list[ToolDescriptor]) -> list[ToolDescriptor]:
        available = {tool.name: tool for tool in tools}
        emitted: list[ToolDescriptor] = []
        remaining = dict(available)
        while remaining:
            progressed = False
            for name, tool in list(remaining.items()):
                if all(dep not in available or any(done.name == dep for done in emitted) for dep in tool.dependencies):
                    emitted.append(tool)
                    del remaining[name]
                    progressed = True
            if not progressed:
                emitted.extend(remaining.values())
                break
        return emitted

    def _target_spacing(self, card: ProtocolCard) -> tuple[float, float, float]:
        if card.domain == Domain.CARDIAC:
            return (1.25, 1.25, 8.0)
        if card.domain == Domain.NEURODEGENERATION:
            return (1.0, 1.0, 1.0)
        return (1.0, 1.0, 1.0)

    def _parallel_group(self, tool: ToolDescriptor, index: int) -> int:
        if tool.name in {"bias_field", "denoise", "artefact_detect"}:
            return 2
        if tool.name in {"motion_correct", "temporal_align"}:
            return 3
        return index

    def _route_id(self, card: ProtocolCard, steps: list[PreprocessingStep]) -> str:
        text = "|".join([card.protocol_class.value, card.domain.value, *[step.tool_name for step in steps]])
        return sha1(text.encode("utf-8")).hexdigest()[:12]
