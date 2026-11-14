"""Repository Connection and Ingestion API Endpoints."""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.integrations.github import (
    GitHubAuthError,
    GitHubForbiddenError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    parse_and_validate_github_url,
)
from app.services.ingestion import IngestionService

logger = logging.getLogger("relaypoint.api.repositories")

router = APIRouter(prefix="/repositories", tags=["Repositories"])


# Request & Response Schemas
class ConnectRepositoryRequest(BaseModel):
    """Payload to connect a new GitHub repository."""
    repository_url: str = Field(
        ...,
        description="Public or authorized GitHub repository URL (e.g. https://github.com/owner/repo)",
        examples=["https://github.com/fastapi/fastapi"],
    )
    name: Optional[str] = Field(
        None,
        description="Optional display name override for the repository",
        max_length=100,
    )


class RepositoryResponse(BaseModel):
    """Repository metadata representation."""
    id: str
    provider: str
    external_repository_id: Optional[str] = None
    name: str
    full_name: str
    description: Optional[str] = ""
    default_branch: str
    repository_url: str
    created_at: str
    updated_at: str


class IngestionResponse(BaseModel):
    """Result of an ingestion analysis execution."""
    run_id: str
    repository_id: str
    status: str
    chunks_created: int
    duplicates_skipped: int
    started_at: str
    completed_at: str


class SourceChunkItem(BaseModel):
    """Individual sanitized source chunk summary."""
    id: str
    repository_id: str
    source_type: str
    source_external_id: Optional[str] = None
    commit_hash: Optional[str] = None
    content: str
    content_hash: str
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class SourceChunksResponse(BaseModel):
    """Paginated source chunks response."""
    repository_id: str
    total: int
    limit: int
    offset: int
    sources: List[SourceChunkItem]


class ActivityItem(BaseModel):
    """Normalized activity timeline entry."""
    source_id: str
    source_type: str
    identifier: Optional[str] = None
    title: str
    author: str
    timestamp: Optional[str] = None
    source_url: Optional[str] = None


def _get_ingestion_service() -> IngestionService:
    """Dependency provider for IngestionService."""
    return IngestionService()


@router.post(
    "/connect",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a GitHub repository",
    description="Validates a GitHub URL, verifies accessibility, and registers it for analysis.",
)
def connect_repository(payload: ConnectRepositoryRequest) -> RepositoryResponse:
    """Register and connect a new GitHub repository."""
    try:
        parse_and_validate_github_url(payload.repository_url)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )

    service = _get_ingestion_service()
    try:
        repo_data = service.connect_repository(
            repository_url=payload.repository_url,
            custom_name=payload.name,
        )
        return RepositoryResponse(**repo_data)
    except GitHubAuthError as auth_err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(auth_err))
    except GitHubRateLimitError as rate_err:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(rate_err))
    except GitHubNotFoundError as not_found_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(not_found_err))
    except GitHubForbiddenError as forbid_err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(forbid_err))
    except Exception as exc:
        logger.error("Failed to connect repository '%s': %s", payload.repository_url, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to connect to the specified GitHub repository. Please verify the URL and access permissions.",
        )


@router.get(
    "",
    response_model=List[RepositoryResponse],
    summary="List connected repositories",
    description="Retrieve all registered repositories in the platform.",
)
def list_repositories() -> List[RepositoryResponse]:
    """Retrieve connected repositories list."""
    service = _get_ingestion_service()
    repos = service.list_repositories()
    return [RepositoryResponse(**r) for r in repos]


@router.get(
    "/{repository_id}",
    response_model=RepositoryResponse,
    summary="Get repository metadata",
    description="Retrieve metadata for a specific connected repository.",
)
def get_repository(repository_id: str) -> RepositoryResponse:
    """Retrieve repository by primary key."""
    service = _get_ingestion_service()
    repo = service.get_repository_by_id(repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    return RepositoryResponse(**repo)


@router.post(
    "/{repository_id}/ingest",
    response_model=IngestionResponse,
    summary="Trigger repository history ingestion",
    description="Synchronously pulls commits, issues, and PRs, sanitizes secrets, and saves source chunks.",
)
def ingest_repository(repository_id: str) -> IngestionResponse:
    """Ingest history for a connected repository."""
    service = _get_ingestion_service()
    repo = service.get_repository_by_id(repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    try:
        result = service.ingest_repository(repository_id)
        return IngestionResponse(**result)
    except GitHubAuthError as auth_err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(auth_err))
    except GitHubRateLimitError as rate_err:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(rate_err))
    except GitHubNotFoundError as not_found_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(not_found_err))
    except Exception as exc:
        logger.error("Ingestion failed for repository '%s': %s", repository_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ingestion failed. Please check repository permissions and API limits.",
        )


@router.get(
    "/{repository_id}/sources",
    response_model=SourceChunksResponse,
    summary="List ingested source chunks",
    description="Retrieve paginated source chunks for an ingested repository.",
)
def get_repository_sources(
    repository_id: str,
    source_type: Optional[str] = Query(None, description="Filter by source type: commit, issue, pull_request"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> SourceChunksResponse:
    """Retrieve paginated source chunks."""
    service = _get_ingestion_service()
    repo = service.get_repository_by_id(repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    chunks_data = service.get_source_chunks(
        repo_id=repository_id,
        source_type=source_type,
        limit=limit,
        offset=offset,
    )
    return SourceChunksResponse(
        repository_id=chunks_data["repository_id"],
        total=chunks_data["total"],
        limit=chunks_data["limit"],
        offset=chunks_data["offset"],
        sources=[SourceChunkItem(**s) for s in chunks_data["sources"]],
    )


@router.get(
    "/{repository_id}/sources/{source_id}",
    response_model=SourceChunkItem,
    summary="Get single source chunk",
    description="Retrieve a specific source chunk by primary key.",
)
def get_source_chunk(repository_id: str, source_id: str) -> SourceChunkItem:
    """Retrieve single source chunk by ID."""
    service = _get_ingestion_service()
    chunk = service.get_source_chunk_by_id(source_id)
    if not chunk or chunk.get("repository_id") != repository_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source chunk '{source_id}' not found in repository '{repository_id}'.",
        )
    return SourceChunkItem(**chunk)


@router.get(
    "/{repository_id}/activity",
    response_model=List[ActivityItem],
    summary="Get repository activity timeline",
    description="Retrieve a unified chronological activity timeline of commits, issues, and PRs.",
)
def get_repository_activity(
    repository_id: str,
    limit: int = Query(50, ge=1, le=100, description="Maximum activity items to return"),
) -> List[ActivityItem]:
    """Retrieve normalized activity timeline."""
    service = _get_ingestion_service()
    repo = service.get_repository_by_id(repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    timeline = service.get_activity_timeline(repo_id=repository_id, limit=limit)
    return [ActivityItem(**item) for item in timeline]
