"""
GraphQL Controller
──────────────────────────────────────────────────────────────────────────
FastAPI integration for GraphQL endpoint with Strawberry.
"""

from fastapi import APIRouter, Depends, Request
from strawberry.fastapi import GraphQLRouter
from strawberry.subscriptions import GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL

from app.core.security import get_current_user
from app.graphql.schema import schema


# Create GraphQL app with authentication
def get_context(request: Request):
    """Get context for GraphQL resolvers."""
    return {
        "request": request,
        "user": None  # Will be populated by authentication
    }


async def get_context_with_auth(
    request: Request,
    user = Depends(get_current_user)
):
    """Get context with authenticated user."""
    return {
        "request": request,
        "user": user
    }


# Create GraphQL router
graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context,
    subscription_protocols=[
        GRAPHQL_TRANSPORT_WS_PROTOCOL,
        GRAPHQL_WS_PROTOCOL,
    ],
)

# Create protected GraphQL router (requires authentication)
protected_graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context_with_auth,
    subscription_protocols=[
        GRAPHQL_TRANSPORT_WS_PROTOCOL,
        GRAPHQL_WS_PROTOCOL,
    ],
)

# Create API router
router = APIRouter(prefix="/graphql", tags=["GraphQL"])

# Add both public and protected endpoints
router.include_router(graphql_app, prefix="")
router.include_router(protected_graphql_app, prefix="/protected")