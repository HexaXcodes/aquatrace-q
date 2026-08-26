"""
Domain-level exceptions and their HTTP mapping.

Services raise these exceptions; the API layer never has to know the
resulting status code, and we never silently swallow a domain error into
a generic 500.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AquaTraceError(Exception):
    """Base class for all domain errors raised by AquaTrace-Q services."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, **context: object) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class SurveyNotFoundError(AquaTraceError):
    status_code = status.HTTP_404_NOT_FOUND


class TargetNotFoundError(AquaTraceError):
    status_code = status.HTTP_404_NOT_FOUND


class MissionNotFoundError(AquaTraceError):
    status_code = status.HTTP_404_NOT_FOUND


class JobNotFoundError(AquaTraceError):
    status_code = status.HTTP_404_NOT_FOUND


class ExperimentNotFoundError(AquaTraceError):
    status_code = status.HTTP_404_NOT_FOUND


class FeatureVectorNotFoundError(AquaTraceError):
    status_code = status.HTTP_404_NOT_FOUND


class UnsupportedSonarFormatError(AquaTraceError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


class FileTooLargeError(AquaTraceError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


class InvalidSonarFileError(AquaTraceError):
    status_code = status.HTTP_400_BAD_REQUEST


class SurveyAlreadyProcessedError(AquaTraceError):
    status_code = status.HTTP_409_CONFLICT


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AquaTraceError)
    async def handle_aquatrace_error(request: Request, exc: AquaTraceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "context": exc.context,
            },
        )
