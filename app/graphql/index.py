# app/graphql/index.py
"""
GraphQL application entry point - configures and exports the GraphQL app.
"""
from strawberry.fastapi import GraphQLRouter
from .schema import schema

# Create GraphQL app router
graphql_app = GraphQLRouter(
    schema,
    path="/",
    graphiql=True  # Enable GraphiQL interface for development
)