from __future__ import annotations


class MRIAgentError(Exception):
    pass


class SchemaValidationError(MRIAgentError):
    pass


class RoutingError(MRIAgentError):
    pass


class AuditIntegrityError(MRIAgentError):
    pass
