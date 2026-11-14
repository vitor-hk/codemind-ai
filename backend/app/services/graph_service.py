import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.schemas import GraphAnalysisResponse, NodeNeighborhoodResponse
from app.graph.graph_engine import DependencyGraphEngine
from app.infrastructure.database.models import (
    CodeSymbolModel,
    RepositoryFileModel,
    SymbolRelationshipModel,
)
from app.services.repository_service import RepositoryService

graph_engine = DependencyGraphEngine()


class GraphService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _load_graph(self, repo_id: uuid.UUID, scope: str):
        await RepositoryService(self.db).get_repository(repo_id)

        rels_res = await self.db.execute(
            select(SymbolRelationshipModel).where(
                SymbolRelationshipModel.repository_id == repo_id
            )
        )
        relationships = list(rels_res.scalars().all())

        if scope == "symbol":
            sym_res = await self.db.execute(
                select(CodeSymbolModel).where(CodeSymbolModel.repository_id == repo_id)
            )
            symbols = list(sym_res.scalars().all())
            return graph_engine.build_symbol_graph(symbols, relationships)

        files_res = await self.db.execute(
            select(RepositoryFileModel).where(RepositoryFileModel.repository_id == repo_id)
        )
        files = list(files_res.scalars().all())
        return graph_engine.build_file_graph(files, relationships)

    async def get_repository_graph(
        self,
        repo_id: uuid.UUID,
        scope: str = "file",
        max_nodes: int = 80,
    ) -> GraphAnalysisResponse:
        nx_graph = await self._load_graph(repo_id, scope)
        return graph_engine.analyze_graph(
            repo_id=repo_id,
            graph=nx_graph,
            scope=scope,
            max_nodes=max_nodes,
        )

    async def get_node_neighborhood(
        self,
        repo_id: uuid.UUID,
        node_id: str,
        scope: str = "file",
    ) -> NodeNeighborhoodResponse:
        nx_graph = await self._load_graph(repo_id, scope)
        return graph_engine.get_node_neighborhood(
            repo_id=repo_id,
            graph=nx_graph,
            node_id=node_id,
            scope=scope,
        )
