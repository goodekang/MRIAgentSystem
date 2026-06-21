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

## Citation

Please cite the associated manuscript if this implementation is used in academic work.
