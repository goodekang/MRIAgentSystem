# MRIAgentSystem

This repository contains the core implementation of MRIAgentSystem, a protocol-aware multi-agent framework for quantitative MRI analysis.

The released code focuses on the architectural components described in the manuscript:

- protocol analysis
- typed inter-agent messaging
- preprocessing route construction
- quantitative report schema construction
- verification auditing
- audit-trail recording
- system-level orchestration

This repository is a research-code release focused on the method implementation. Dataset access, trained models, and experiment-specific configurations are handled separately according to data-use agreements and manuscript review requirements.

Additional materials may be made available by the authors upon reasonable academic request, subject to data usage restrictions, model-release constraints, and ongoing research extensions.

## Structure

```text
mri_agent_system/
  agents/
    preprocessing.py
    protocol.py
    quantitative.py
    verification.py
  core/
    exceptions.py
    schemas.py
    serialization.py
  runtime/
    audit.py
    message_bus.py
    orchestrator.py
```

## Availability

The public package exposes the framework-level control logic, message schemas, routing abstractions, report construction logic, and verification rules needed to inspect the method. Additional study materials may be provided by the authors upon reasonable academic request where permitted by dataset licenses and institutional policies.

## Citation

Please cite the associated manuscript if this implementation is used in academic work.
