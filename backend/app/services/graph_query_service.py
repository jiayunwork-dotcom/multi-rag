import json
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, deque
import numpy as np
import networkx as nx
from networkx.algorithms import community as nx_community
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models, schemas
from ..config import settings
from .embedding_service import EmbeddingService
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class GraphQueryService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_service: Optional[LLMService] = None
    ):
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    def _build_networkx_graph(
        self,
        db: Session,
        knowledge_base_id: int
    ) -> nx.DiGraph:
        G = nx.DiGraph()

        entities = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id
        ).all()

        for entity in entities:
            occurrence_count = db.query(models.EntityOccurrence).filter(
                models.EntityOccurrence.entity_id == entity.id
            ).count()
            document_count = db.query(func.count(func.distinct(models.EntityOccurrence.document_id))).filter(
                models.EntityOccurrence.entity_id == entity.id
            ).scalar() or 0
            degree = len(entity.source_relations) + len(entity.target_relations)

            G.add_node(
                str(entity.id),
                name=entity.name,
                entity_type=entity.entity_type,
                description=entity.description,
                occurrence_count=occurrence_count,
                document_count=document_count,
                degree=degree
            )

        relations = db.query(models.GraphRelation).filter(
            models.GraphRelation.knowledge_base_id == knowledge_base_id
        ).all()

        for relation in relations:
            G.add_edge(
                str(relation.source_entity_id),
                str(relation.target_entity_id),
                relation_type=relation.relation_type,
                frequency=relation.frequency,
                description=relation.description
            )

        return G

    def get_graph_stats(
        self,
        db: Session,
        knowledge_base_id: int
    ) -> schemas.GraphStats:
        G = self._build_networkx_graph(db, knowledge_base_id)

        entity_count = G.number_of_nodes()
        relation_count = G.number_of_edges()

        if entity_count > 0:
            connected_components = nx.number_weakly_connected_components(G.to_undirected())
            degrees = [d for n, d in G.degree()]
            avg_degree = sum(degrees) / len(degrees) if degrees else 0.0
            max_degree = max(degrees) if degrees else 0

            try:
                communities = nx_community.greedy_modularity_communities(G.to_undirected())
                community_count = len(communities)
            except Exception as e:
                logger.warning(f"Community detection failed: {e}")
                community_count = 0
        else:
            connected_components = 0
            avg_degree = 0.0
            max_degree = 0
            community_count = 0

        entity_types_distribution = defaultdict(int)
        for _, data in G.nodes(data=True):
            etype = data.get("entity_type", "unknown")
            entity_types_distribution[etype] += 1

        relation_types_distribution = defaultdict(int)
        for _, _, data in G.edges(data=True):
            rtype = data.get("relation_type", "unknown")
            relation_types_distribution[rtype] += 1

        stats_record = db.query(models.KnowledgeBaseGraphStats).filter(
            models.KnowledgeBaseGraphStats.knowledge_base_id == knowledge_base_id
        ).first()

        build_status = models.GraphBuildStatus.PENDING
        last_built_at = None
        if stats_record:
            build_status = stats_record.build_status
            last_built_at = stats_record.last_built_at
            if entity_count == 0:
                entity_count = stats_record.entity_count
            if relation_count == 0:
                relation_count = stats_record.relation_count

        return schemas.GraphStats(
            knowledge_base_id=knowledge_base_id,
            entity_count=entity_count,
            relation_count=relation_count,
            connected_components=connected_components,
            avg_degree=float(avg_degree),
            max_degree=max_degree,
            community_count=community_count,
            entity_types_distribution=dict(entity_types_distribution),
            relation_types_distribution=dict(relation_types_distribution),
            build_status=build_status,
            last_built_at=last_built_at
        )

    def get_graph_data(
        self,
        db: Session,
        knowledge_base_id: int,
        filter_entity_types: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> schemas.GraphData:
        stats = self.get_graph_stats(db, knowledge_base_id)
        G = self._build_networkx_graph(db, knowledge_base_id)

        max_nodes = settings.GRAPH_MAX_NODES_VISUALIZATION

        if filter_entity_types:
            nodes_to_remove = []
            for node_id, data in G.nodes(data=True):
                if data.get("entity_type") not in filter_entity_types:
                    nodes_to_remove.append(node_id)
            G.remove_nodes_from(nodes_to_remove)

        if limit and G.number_of_nodes() > limit:
            nodes_by_degree = sorted(G.degree(), key=lambda x: x[1], reverse=True)
            top_nodes = [n for n, d in nodes_by_degree[:limit]]
            G = G.subgraph(top_nodes)

        use_community_aggregation = G.number_of_nodes() > max_nodes
        communities = []

        if use_community_aggregation:
            try:
                undirected_G = G.to_undirected()
                communities = list(nx_community.greedy_modularity_communities(
                    undirected_G,
                    resolution=1.0
                ))
            except Exception as e:
                logger.warning(f"Community detection failed: {e}")
                communities = []

        community_map = {}
        if communities:
            for i, comm in enumerate(communities):
                for node in comm:
                    community_map[node] = i

        pos = {}
        if G.number_of_nodes() > 0:
            try:
                pos = nx.spring_layout(
                    G,
                    k=0.5,
                    iterations=50,
                    seed=42,
                    scale=1000.0
                )
            except Exception as e:
                logger.warning(f"Layout calculation failed: {e}")
                for i, node in enumerate(G.nodes()):
                    angle = 2 * np.pi * i / G.number_of_nodes()
                    pos[node] = (np.cos(angle) * 500, np.sin(angle) * 500)

        nodes: List[schemas.GraphNode] = []
        edges: List[schemas.GraphEdge] = []

        degree_dict = dict(G.degree())
        max_degree = max(degree_dict.values()) if degree_dict else 1

        for node_id, data in G.nodes(data=True):
            degree = degree_dict.get(node_id, 0)
            size = 8 + (degree / max_degree * 22) if max_degree > 0 else 10

            x, y = pos.get(node_id, (0, 0))

            nodes.append(schemas.GraphNode(
                id=str(node_id),
                name=data.get("name", ""),
                entity_type=data.get("entity_type", "tech_concept"),
                size=size,
                degree=degree,
                community_id=community_map.get(node_id),
                x=float(x),
                y=float(y),
                is_super_node=False
            ))

        frequency_dict = defaultdict(int)
        for _, _, data in G.edges(data=True):
            freq = data.get("frequency", 1)
            frequency_dict[(_, _)] = freq

        max_frequency = max(frequency_dict.values()) if frequency_dict else 1

        for u, v, data in G.edges(data=True):
            freq = data.get("frequency", 1)
            width = 1.0 + (freq / max_frequency * 4.0) if max_frequency > 0 else 1.0

            edges.append(schemas.GraphEdge(
                id=f"{u}-{v}",
                source=str(u),
                target=str(v),
                relation_type=data.get("relation_type", "related_to"),
                width=width,
                frequency=freq
            ))

        if use_community_aggregation and communities:
            super_nodes = []
            super_edges = []
            kept_nodes = set()

            for i, comm in enumerate(communities):
                if len(comm) >= settings.GRAPH_COMMUNITY_THRESHOLD:
                    member_names = [G.nodes[n].get("name", "") for n in comm]
                    super_node_name = f"社区{i+1} ({len(comm)}个节点)"

                    centroid_x = np.mean([pos.get(n, (0, 0))[0] for n in comm])
                    centroid_y = np.mean([pos.get(n, (0, 0))[1] for n in comm])

                    super_nodes.append(schemas.GraphNode(
                        id=f"super-{i}",
                        name=super_node_name,
                        entity_type="tech_concept",
                        size=20 + len(comm) * 2,
                        degree=len(comm),
                        community_id=i,
                        x=float(centroid_x),
                        y=float(centroid_y),
                        is_super_node=True,
                        super_node_members=member_names
                    ))
                else:
                    kept_nodes.update(comm)

            filtered_nodes = [n for n in nodes if n.id in kept_nodes or n.is_super_node]
            filtered_nodes.extend(super_nodes)

            node_id_set = {n.id for n in filtered_nodes}
            filtered_edges = [e for e in edges if e.source in node_id_set and e.target in node_id_set]

            nodes = filtered_nodes
            edges = filtered_edges

        return schemas.GraphData(
            nodes=nodes,
            edges=edges,
            stats=stats
        )

    def get_entity_detail(
        self,
        db: Session,
        entity_id: int
    ) -> schemas.GraphEntityDetail:
        entity = db.query(models.GraphEntity).filter(
            models.GraphEntity.id == entity_id
        ).first()

        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        occurrence_count = db.query(models.EntityOccurrence).filter(
            models.EntityOccurrence.entity_id == entity_id
        ).count()

        document_count = db.query(func.count(func.distinct(models.EntityOccurrence.document_id))).filter(
            models.EntityOccurrence.entity_id == entity_id
        ).scalar() or 0

        degree = len(entity.source_relations) + len(entity.target_relations)

        related_chunks = []
        occurrences = db.query(models.EntityOccurrence).filter(
            models.EntityOccurrence.entity_id == entity_id
        ).order_by(models.EntityOccurrence.confidence.desc()).limit(10).all()

        for occ in occurrences:
            chunk = db.query(models.Chunk).filter(models.Chunk.id == occ.chunk_id).first()
            if chunk:
                doc = db.query(models.Document).filter(models.Document.id == chunk.document_id).first()
                related_chunks.append({
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "document_title": doc.title if doc else "Unknown",
                    "chunk_index": chunk.chunk_index,
                    "content_preview": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                    "confidence": occ.confidence
                })

        source_relations = []
        for rel in entity.source_relations:
            target = db.query(models.GraphEntity).filter(
                models.GraphEntity.id == rel.target_entity_id
            ).first()
            source_relations.append(schemas.GraphRelation(
                id=rel.id,
                knowledge_base_id=rel.knowledge_base_id,
                source_entity_id=rel.source_entity_id,
                target_entity_id=rel.target_entity_id,
                relation_type=rel.relation_type,
                description=rel.description,
                neo4j_id=rel.neo4j_id,
                frequency=rel.frequency,
                source_entity_name=entity.name,
                target_entity_name=target.name if target else "",
                source_entity_type=entity.entity_type,
                target_entity_type=target.entity_type if target else None,
                created_at=rel.created_at,
                updated_at=rel.updated_at
            ))

        target_relations = []
        for rel in entity.target_relations:
            source = db.query(models.GraphEntity).filter(
                models.GraphEntity.id == rel.source_entity_id
            ).first()
            target_relations.append(schemas.GraphRelation(
                id=rel.id,
                knowledge_base_id=rel.knowledge_base_id,
                source_entity_id=rel.source_entity_id,
                target_entity_id=rel.target_entity_id,
                relation_type=rel.relation_type,
                description=rel.description,
                neo4j_id=rel.neo4j_id,
                frequency=rel.frequency,
                source_entity_name=source.name if source else "",
                target_entity_name=entity.name,
                source_entity_type=source.entity_type if source else None,
                target_entity_type=entity.entity_type,
                created_at=rel.created_at,
                updated_at=rel.updated_at
            ))

        occ_list = []
        for occ in entity.occurrences:
            doc = db.query(models.Document).filter(models.Document.id == occ.document_id).first()
            chunk = db.query(models.Chunk).filter(models.Chunk.id == occ.chunk_id).first()
            occ_list.append(schemas.EntityOccurrence(
                id=occ.id,
                entity_id=occ.entity_id,
                document_id=occ.document_id,
                chunk_id=occ.chunk_id,
                document_title=doc.title if doc else None,
                chunk_index=chunk.chunk_index if chunk else None,
                context_snippet=occ.context_snippet,
                start_pos=occ.start_pos,
                end_pos=occ.end_pos,
                confidence=occ.confidence,
                created_at=occ.created_at
            ))

        return schemas.GraphEntityDetail(
            id=entity.id,
            knowledge_base_id=entity.knowledge_base_id,
            name=entity.name,
            entity_type=entity.entity_type,
            description=entity.description,
            neo4j_id=entity.neo4j_id,
            occurrence_count=occurrence_count,
            document_count=document_count,
            degree=degree,
            related_chunks=related_chunks,
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            occurrences=occ_list,
            source_relations=source_relations,
            target_relations=target_relations
        )

    def extract_query_entities(
        self,
        question: str,
        knowledge_base_id: int,
        db: Session
    ) -> List[str]:
        if not self.llm_service:
            return self._rule_based_entity_extraction(question, db, knowledge_base_id)

        prompt = f"""你是一个专业的问题实体提取助手。请从用户问题中提取关键实体，这些实体应该是知识图谱中的节点类型。

实体类型：
- person: 人物
- organization: 组织、公司、机构
- location: 地点、位置
- tech_concept: 技术概念、技术术语
- event: 事件、活动

用户问题：
\"\"\"{question}\"\"\"

请以JSON格式输出提取到的实体名称列表，格式如下：
{{
    "entities": ["实体1", "实体2", "实体3"]
}}

只输出JSON，不要有其他文字说明。如果问题中没有明确的实体，返回空数组。"""

        messages = [
            {"role": "system", "content": "你是一个专业的实体提取助手，能够准确从问题中提取关键实体。"},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.llm_service.generate(messages)
            content = response.choices[0].message.content

            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group(0))
                entities = data.get("entities", [])
                if entities:
                    return entities
        except Exception as e:
            logger.error(f"LLM entity extraction failed: {e}")

        return self._rule_based_entity_extraction(question, db, knowledge_base_id)

    def _rule_based_entity_extraction(
        self,
        question: str,
        db: Session,
        knowledge_base_id: int
    ) -> List[str]:
        all_entities = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id
        ).all()

        question_lower = question.lower()
        matched = []

        for entity in all_entities:
            if entity.name.lower() in question_lower:
                matched.append(entity.name)

        if not matched:
            question_embedding = self.embedding_service.encode_text(question)

            scored = []
            for entity in all_entities:
                if entity.embedding:
                    entity_embedding = np.array(entity.embedding)
                    similarity = np.dot(question_embedding, entity_embedding) / (
                        np.linalg.norm(question_embedding) * np.linalg.norm(entity_embedding)
                    )
                    if similarity > 0.5:
                        scored.append((entity.name, similarity))

            scored.sort(key=lambda x: x[1], reverse=True)
            matched = [name for name, score in scored[:5]]

        return matched[:settings.GRAPH_MAX_RELATED_ENTITIES]

    def find_entity_by_name(
        self,
        db: Session,
        knowledge_base_id: int,
        entity_name: str
    ) -> Optional[models.GraphEntity]:
        entity = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id,
            models.GraphEntity.name == entity_name
        ).first()

        if entity:
            return entity

        entity_lower = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id,
            func.lower(models.GraphEntity.name) == entity_name.lower()
        ).first()

        return entity_lower

    def query_graph(
        self,
        db: Session,
        request: schemas.GraphQueryRequest
    ) -> Tuple[schemas.GraphQueryResult, schemas.GraphQueryDebug]:
        knowledge_base_id = request.knowledge_base_id
        query_entities = self.extract_query_entities(request.question, knowledge_base_id, db)

        cypher_queries = []
        all_paths: List[Dict[str, Any]] = []
        visited_entities = set()
        graph_context_parts = []

        G = self._build_networkx_graph(db, knowledge_base_id)

        entity_id_map = {}
        for node_id, data in G.nodes(data=True):
            entity_id_map[data["name"]] = node_id
            entity_id_map[node_id] = node_id

        matched_entity_ids = []
        for entity_name in query_entities:
            entity = self.find_entity_by_name(db, knowledge_base_id, entity_name)
            if entity:
                matched_entity_ids.append(str(entity.id))
                visited_entities.add(str(entity.id))

        cypher_queries.append(
            f"MATCH (e) WHERE e.id IN {[int(eid) for eid in matched_entity_ids]} RETURN e.name as name"
        )

        for start_id in matched_entity_ids:
            if start_id not in G:
                continue

            paths = self._find_paths(
                G, start_id,
                max_hops=request.max_hops,
                max_paths=5
            )

            for path in paths:
                path_data = []
                for i, node_id in enumerate(path):
                    node_data = G.nodes[node_id]
                    path_data.append({
                        "entity_id": node_id,
                        "name": node_data["name"],
                        "entity_type": node_data["entity_type"]
                    })
                    if i < len(path) - 1:
                        next_id = path[i + 1]
                        if G.has_edge(node_id, next_id):
                            edge_data = G[node_id][next_id]
                            path_data.append({
                                "relation": edge_data["relation_type"],
                                "frequency": edge_data["frequency"]
                            })
                        elif G.has_edge(next_id, node_id):
                            edge_data = G[next_id][node_id]
                            path_data.append({
                                "relation": edge_data["relation_type"],
                                "frequency": edge_data["frequency"]
                            })

                all_paths.append({
                    "path": path_data,
                    "score": 1.0 / len(path)
                })

                for node_id in path:
                    visited_entities.add(node_id)

        related_entities = []
        for entity_id in visited_entities:
            if entity_id not in G:
                continue

            node_data = G.nodes[entity_id]
            entity = db.query(models.GraphEntity).filter(
                models.GraphEntity.id == int(entity_id)
            ).first()

            if entity:
                occurrence_count = db.query(models.EntityOccurrence).filter(
                    models.EntityOccurrence.entity_id == entity.id
                ).count()
                document_count = db.query(func.count(func.distinct(models.EntityOccurrence.document_id))).filter(
                    models.EntityOccurrence.entity_id == entity.id
                ).scalar() or 0
                degree = len(entity.source_relations) + len(entity.target_relations)

                related_entities.append(schemas.GraphEntity(
                    id=entity.id,
                    knowledge_base_id=entity.knowledge_base_id,
                    name=entity.name,
                    entity_type=entity.entity_type,
                    description=entity.description,
                    neo4j_id=entity.neo4j_id,
                    occurrence_count=occurrence_count,
                    document_count=document_count,
                    degree=degree,
                    related_chunks=[],
                    metadata=entity.metadata,
                    created_at=entity.created_at,
                    updated_at=entity.updated_at
                ))

        if related_entities:
            graph_context_parts.append("## 知识图谱关联信息")

            grouped_by_type = defaultdict(list)
            for ent in related_entities:
                grouped_by_type[ent.entity_type].append(ent.name)

            for etype, names in grouped_by_type.items():
                type_label = {
                    "person": "人物",
                    "organization": "组织",
                    "location": "地点",
                    "tech_concept": "技术概念",
                    "event": "事件"
                }.get(etype, etype)
                graph_context_parts.append(f"### {type_label}:")
                graph_context_parts.append(f"{', '.join(names)}")

            if all_paths:
                graph_context_parts.append("\n### 关联路径:")
                for i, path_data in enumerate(all_paths[:5]):
                    path_str = ""
                    for step in path_data["path"]:
                        if "name" in step:
                            path_str += f"[{step['name']}]"
                        elif "relation" in step:
                            rel_label = {
                                "belongs_to": "属于",
                                "located_in": "位于",
                                "created_by": "由...创建",
                                "uses": "使用",
                                "depends_on": "依赖",
                                "contains": "包含"
                            }.get(step["relation"], step["relation"])
                            path_str += f" --({rel_label})--> "
                    graph_context_parts.append(f"{i+1}. {path_str}")

        graph_context = "\n".join(graph_context_parts) if graph_context_parts else ""

        graph_paths = [
            schemas.GraphPath(path=p["path"], score=p["score"])
            for p in all_paths
        ]

        result = schemas.GraphQueryResult(
            query_entities=query_entities,
            paths=graph_paths,
            related_entities=related_entities,
            graph_context=graph_context
        )

        debug = schemas.GraphQueryDebug(
            query_entities=query_entities,
            cypher_queries=cypher_queries,
            paths_found=len(all_paths),
            graph_context_length=len(graph_context)
        )

        return result, debug

    def _find_paths(
        self,
        G: nx.DiGraph,
        start_node: str,
        max_hops: int = 2,
        max_paths: int = 5
    ) -> List[List[str]]:
        paths = []
        queue = deque([(start_node, [start_node])])
        visited = set([start_node])

        while queue and len(paths) < max_paths:
            current, path = queue.popleft()

            if len(path) > 1 and len(path) <= max_hops + 1:
                paths.append(path)

            if len(path) < max_hops + 1:
                neighbors = list(G.neighbors(current)) + list(G.predecessors(current))
                neighbors = sorted(neighbors, key=lambda n: G.degree(n), reverse=True)

                for neighbor in neighbors:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))

        return paths[:max_paths]

    def create_entity(
        self,
        db: Session,
        data: schemas.GraphEntityCreate,
        graph_service
    ) -> schemas.GraphEntity:
        new_entity = models.GraphEntity(
            knowledge_base_id=data.knowledge_base_id,
            name=data.name,
            entity_type=data.entity_type,
            description=data.description,
            metadata=data.metadata
        )
        db.add(new_entity)
        db.flush()
        db.refresh(new_entity)

        graph_service._create_neo4j_entity(new_entity)
        db.commit()

        return schemas.GraphEntity(
            id=new_entity.id,
            knowledge_base_id=new_entity.knowledge_base_id,
            name=new_entity.name,
            entity_type=new_entity.entity_type,
            description=new_entity.description,
            neo4j_id=new_entity.neo4j_id,
            occurrence_count=0,
            document_count=0,
            degree=0,
            related_chunks=[],
            metadata=new_entity.metadata,
            created_at=new_entity.created_at,
            updated_at=new_entity.updated_at
        )

    def update_entity(
        self,
        db: Session,
        entity_id: int,
        data: schemas.GraphEntityUpdate,
        graph_service
    ) -> schemas.GraphEntity:
        entity = db.query(models.GraphEntity).filter(
            models.GraphEntity.id == entity_id
        ).first()

        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(entity, key, value)

        db.commit()
        db.refresh(entity)

        try:
            with graph_service._get_neo4j_session() as session:
                label = graph_service._get_entity_label(entity.entity_type)
                session.run(
                    f"""
                    MATCH (e:{label} {{id: $id}})
                    SET e.name = $name,
                        e.entity_type = $entity_type,
                        e.description = $description
                    """,
                    id=entity.id,
                    name=entity.name,
                    entity_type=entity.entity_type,
                    description=entity.description or ""
                )
        except Exception as e:
            logger.error(f"Failed to update Neo4j entity: {e}")

        occurrence_count = db.query(models.EntityOccurrence).filter(
            models.EntityOccurrence.entity_id == entity_id
        ).count()
        document_count = db.query(func.count(func.distinct(models.EntityOccurrence.document_id))).filter(
            models.EntityOccurrence.entity_id == entity_id
        ).scalar() or 0
        degree = len(entity.source_relations) + len(entity.target_relations)

        return schemas.GraphEntity(
            id=entity.id,
            knowledge_base_id=entity.knowledge_base_id,
            name=entity.name,
            entity_type=entity.entity_type,
            description=entity.description,
            neo4j_id=entity.neo4j_id,
            occurrence_count=occurrence_count,
            document_count=document_count,
            degree=degree,
            related_chunks=[],
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )

    def delete_entity(
        self,
        db: Session,
        entity_id: int,
        graph_service
    ):
        entity = db.query(models.GraphEntity).filter(
            models.GraphEntity.id == entity_id
        ).first()

        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        graph_service._delete_neo4j_entity(entity)

        db.delete(entity)
        db.commit()

    def create_relation(
        self,
        db: Session,
        data: schemas.GraphRelationCreate,
        graph_service
    ) -> schemas.GraphRelation:
        source = db.query(models.GraphEntity).filter(
            models.GraphEntity.id == data.source_entity_id
        ).first()
        target = db.query(models.GraphEntity).filter(
            models.GraphEntity.id == data.target_entity_id
        ).first()

        if not source or not target:
            raise ValueError("Source or target entity not found")

        new_relation = models.GraphRelation(
            knowledge_base_id=data.knowledge_base_id,
            source_entity_id=data.source_entity_id,
            target_entity_id=data.target_entity_id,
            relation_type=data.relation_type,
            description=data.description,
            frequency=1,
            metadata=data.metadata
        )
        db.add(new_relation)
        db.flush()
        db.refresh(new_relation)

        graph_service._create_neo4j_relation(source, target, new_relation)
        db.commit()

        return schemas.GraphRelation(
            id=new_relation.id,
            knowledge_base_id=new_relation.knowledge_base_id,
            source_entity_id=new_relation.source_entity_id,
            target_entity_id=new_relation.target_entity_id,
            relation_type=new_relation.relation_type,
            description=new_relation.description,
            neo4j_id=new_relation.neo4j_id,
            frequency=new_relation.frequency,
            source_entity_name=source.name,
            target_entity_name=target.name,
            source_entity_type=source.entity_type,
            target_entity_type=target.entity_type,
            created_at=new_relation.created_at,
            updated_at=new_relation.updated_at
        )

    def update_relation(
        self,
        db: Session,
        relation_id: int,
        data: schemas.GraphRelationUpdate,
        graph_service
    ) -> schemas.GraphRelation:
        relation = db.query(models.GraphRelation).filter(
            models.GraphRelation.id == relation_id
        ).first()

        if not relation:
            raise ValueError(f"Relation {relation_id} not found")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(relation, key, value)

        db.commit()
        db.refresh(relation)

        source = db.query(models.GraphEntity).filter(
            models.GraphEntity.id == relation.source_entity_id
        ).first()
        target = db.query(models.GraphEntity).filter(
            models.GraphEntity.id == relation.target_entity_id
        ).first()

        return schemas.GraphRelation(
            id=relation.id,
            knowledge_base_id=relation.knowledge_base_id,
            source_entity_id=relation.source_entity_id,
            target_entity_id=relation.target_entity_id,
            relation_type=relation.relation_type,
            description=relation.description,
            neo4j_id=relation.neo4j_id,
            frequency=relation.frequency,
            source_entity_name=source.name if source else "",
            target_entity_name=target.name if target else "",
            source_entity_type=source.entity_type if source else None,
            target_entity_type=target.entity_type if target else None,
            created_at=relation.created_at,
            updated_at=relation.updated_at
        )

    def delete_relation(
        self,
        db: Session,
        relation_id: int,
        graph_service
    ):
        relation = db.query(models.GraphRelation).filter(
            models.GraphRelation.id == relation_id
        ).first()

        if not relation:
            raise ValueError(f"Relation {relation_id} not found")

        graph_service._delete_neo4j_relation(relation)

        db.delete(relation)
        db.commit()

    def _parse_graph_query(
        self,
        query: str,
        knowledge_base_id: int,
        db: Session
    ) -> Tuple[str, Dict[str, Any]]:
        query_lower = query.strip().lower()

        find_match = re.match(r'find\s+entity\s+where\s+(.+)', query_lower)
        if find_match:
            conditions = find_match.group(1).strip()
            filters = {}

            type_match = re.search(r'type\s*=\s*(\w+)', conditions)
            if type_match:
                filters['entity_type'] = type_match.group(1)

            name_match = re.search(r'name\s+contains\s*"([^"]+)"', conditions)
            if name_match:
                filters['name_contains'] = name_match.group(1)

            name_eq_match = re.search(r'name\s*=\s*"([^"]+)"', conditions)
            if name_eq_match:
                filters['name'] = name_eq_match.group(1)

            return 'find', filters

        path_match = re.match(r'path\s+from\s*"([^"]+)"\s+to\s*"([^"]+)"(?:\s+max_hops\s+(\d+))?', query_lower)
        if path_match:
            from_entity = path_match.group(1)
            to_entity = path_match.group(2)
            max_hops = int(path_match.group(3)) if path_match.group(3) else 3

            return 'path', {
                'from': from_entity,
                'to': to_entity,
                'max_hops': max_hops
            }

        return 'natural_language', {'query': query}

    def _execute_find_query(
        self,
        db: Session,
        knowledge_base_id: int,
        filters: Dict[str, Any]
    ) -> Tuple[List[schemas.GraphEntity], List[str], List[str]]:
        query = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id
        )

        if 'entity_type' in filters:
            query = query.filter(models.GraphEntity.entity_type == filters['entity_type'])

        if 'name' in filters:
            query = query.filter(models.GraphEntity.name == filters['name'])
        elif 'name_contains' in filters:
            query = query.filter(models.GraphEntity.name.ilike(f"%{filters['name_contains']}%"))

        entities = query.limit(100).all()

        result = []
        highlight_node_ids = []
        for entity in entities:
            occurrence_count = db.query(models.EntityOccurrence).filter(
                models.EntityOccurrence.entity_id == entity.id
            ).count()
            document_count = db.query(func.count(func.distinct(models.EntityOccurrence.document_id))).filter(
                models.EntityOccurrence.entity_id == entity.id
            ).scalar() or 0
            degree = len(entity.source_relations) + len(entity.target_relations)

            result.append(schemas.GraphEntity(
                id=entity.id,
                knowledge_base_id=entity.knowledge_base_id,
                name=entity.name,
                entity_type=entity.entity_type,
                description=entity.description,
                neo4j_id=entity.neo4j_id,
                occurrence_count=occurrence_count,
                document_count=document_count,
                degree=degree,
                related_chunks=[],
                metadata=entity.metadata,
                created_at=entity.created_at,
                updated_at=entity.updated_at
            ))
            highlight_node_ids.append(str(entity.id))

        return result, highlight_node_ids, []

    def _execute_path_query(
        self,
        db: Session,
        knowledge_base_id: int,
        params: Dict[str, Any],
        max_hops: int
    ) -> Tuple[List[schemas.GraphEntity], List[Dict[str, Any]], List[schemas.GraphRelation], List[str], List[str]]:
        from_name = params['from']
        to_name = params['to']
        actual_max_hops = params.get('max_hops', max_hops)

        from_entity = self.find_entity_by_name(db, knowledge_base_id, from_name)
        to_entity = self.find_entity_by_name(db, knowledge_base_id, to_name)

        if not from_entity or not to_entity:
            return [], [], [], [], []

        G = self._build_networkx_graph(db, knowledge_base_id)

        paths = self._find_all_paths(
            G,
            str(from_entity.id),
            str(to_entity.id),
            max_hops=actual_max_hops,
            max_paths=10
        )

        matched_entities = {}
        matched_relations = {}
        highlight_node_ids = set()
        highlight_edge_ids = set()

        highlight_node_ids.add(str(from_entity.id))
        highlight_node_ids.add(str(to_entity.id))

        matched_paths = []
        for path in paths:
            path_entities = []
            path_relations = []
            for i, node_id in enumerate(path):
                node_data = G.nodes[node_id]
                if node_id not in matched_entities:
                    entity = db.query(models.GraphEntity).filter(
                        models.GraphEntity.id == int(node_id)
                    ).first()
                    if entity:
                        occurrence_count = db.query(models.EntityOccurrence).filter(
                            models.EntityOccurrence.entity_id == entity.id
                        ).count()
                        document_count = db.query(func.count(func.distinct(models.EntityOccurrence.document_id))).filter(
                            models.EntityOccurrence.entity_id == entity.id
                        ).scalar() or 0
                        degree = len(entity.source_relations) + len(entity.target_relations)
                        matched_entities[node_id] = schemas.GraphEntity(
                            id=entity.id,
                            knowledge_base_id=entity.knowledge_base_id,
                            name=entity.name,
                            entity_type=entity.entity_type,
                            description=entity.description,
                            neo4j_id=entity.neo4j_id,
                            occurrence_count=occurrence_count,
                            document_count=document_count,
                            degree=degree,
                            related_chunks=[],
                            metadata=entity.metadata,
                            created_at=entity.created_at,
                            updated_at=entity.updated_at
                        )
                highlight_node_ids.add(node_id)

                path_entities.append({
                    'id': int(node_id),
                    'name': node_data['name'],
                    'entity_type': node_data['entity_type']
                })

                if i < len(path) - 1:
                    next_id = path[i + 1]
                    edge_key = None
                    edge_data = None
                    if G.has_edge(node_id, next_id):
                        edge_key = f"{node_id}-{next_id}"
                        edge_data = G[node_id][next_id]
                    elif G.has_edge(next_id, node_id):
                        edge_key = f"{next_id}-{node_id}"
                        edge_data = G[next_id][node_id]

                    if edge_key and edge_key not in matched_relations:
                        rel = db.query(models.GraphRelation).filter(
                            ((models.GraphRelation.source_entity_id == int(node_id)) &
                             (models.GraphRelation.target_entity_id == int(next_id))) |
                            ((models.GraphRelation.source_entity_id == int(next_id)) &
                             (models.GraphRelation.target_entity_id == int(node_id)))
                        ).first()
                        if rel:
                            source = db.query(models.GraphEntity).filter(
                                models.GraphEntity.id == rel.source_entity_id
                            ).first()
                            target = db.query(models.GraphEntity).filter(
                                models.GraphEntity.id == rel.target_entity_id
                            ).first()
                            matched_relations[edge_key] = schemas.GraphRelation(
                                id=rel.id,
                                knowledge_base_id=rel.knowledge_base_id,
                                source_entity_id=rel.source_entity_id,
                                target_entity_id=rel.target_entity_id,
                                relation_type=rel.relation_type,
                                description=rel.description,
                                neo4j_id=rel.neo4j_id,
                                frequency=rel.frequency,
                                source_entity_name=source.name if source else "",
                                target_entity_name=target.name if target else "",
                                source_entity_type=source.entity_type if source else None,
                                target_entity_type=target.entity_type if target else None,
                                created_at=rel.created_at,
                                updated_at=rel.updated_at
                            )
                    if edge_key:
                        highlight_edge_ids.add(edge_key)

                    rel_type = edge_data['relation_type'] if edge_data else 'related_to'
                    path_relations.append({
                        'id': edge_key or f"rel_{i}",
                        'source_entity_id': int(node_id),
                        'target_entity_id': int(next_id),
                        'relation_type': rel_type,
                        'source_entity_name': node_data['name'],
                        'target_entity_name': G.nodes[next_id]['name'] if next_id in G.nodes else ''
                    })

            matched_paths.append({
                'entities': path_entities,
                'relations': path_relations,
                'hops': len(path) - 1
            })

        return list(matched_entities.values()), matched_paths, list(matched_relations.values()), list(highlight_node_ids), list(highlight_edge_ids)

    def _find_all_paths(
        self,
        G: nx.DiGraph,
        start: str,
        end: str,
        max_hops: int = 3,
        max_paths: int = 10
    ) -> List[List[str]]:
        paths = []
        visited = set()

        def dfs(current: str, path: List[str], depth: int):
            if len(paths) >= max_paths:
                return
            if current == end and len(path) > 1:
                paths.append(path.copy())
                return
            if depth >= max_hops:
                return

            neighbors = list(G.neighbors(current)) + list(G.predecessors(current))
            neighbors = sorted(neighbors, key=lambda n: G.degree(n), reverse=True)

            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    path.append(neighbor)
                    dfs(neighbor, path, depth + 1)
                    path.pop()
                    visited.remove(neighbor)

        visited.add(start)
        dfs(start, [start], 0)
        return paths[:max_paths]

    def execute_graphql_query(
        self,
        db: Session,
        request: schemas.GraphQLQueryRequest
    ) -> schemas.GraphQLQueryResult:
        import time
        start_time = time.time()

        query_type, params = self._parse_graph_query(
            request.query,
            request.knowledge_base_id,
            db
        )

        matched_entities = []
        matched_paths = []
        path_edges = []
        highlight_node_ids = []
        highlight_edge_ids = []
        parsed_query = None

        if query_type == 'find':
            matched_entities, highlight_node_ids, highlight_edge_ids = self._execute_find_query(
                db, request.knowledge_base_id, params
            )
            parsed_query = f"FIND entity WHERE {params}"

        elif query_type == 'path':
            matched_entities, matched_paths, path_edges, highlight_node_ids, highlight_edge_ids = self._execute_path_query(
                db, request.knowledge_base_id, params, request.max_hops
            )
            parsed_query = f"PATH FROM \"{params['from']}\" TO \"{params['to']}\" MAX_HOPS {params.get('max_hops', request.max_hops)}"

        else:
            extracted_entities = self.extract_query_entities(
                request.query, request.knowledge_base_id, db
            )
            if extracted_entities:
                matched_entities, highlight_node_ids, _ = self._execute_find_query(
                    db,
                    request.knowledge_base_id,
                    {'name_contains': extracted_entities[0]}
                )
                if len(extracted_entities) >= 2:
                    _, paths, edges, path_nodes, path_edges_list = self._execute_path_query(
                        db,
                        request.knowledge_base_id,
                        {'from': extracted_entities[0], 'to': extracted_entities[1]},
                        request.max_hops
                    )
                    matched_paths = paths
                    path_edges = edges
                    highlight_node_ids = list(set(highlight_node_ids) | set(path_nodes))
                    highlight_edge_ids = path_edges_list

            parsed_query = f"Natural language: {request.query}"

        execution_time = (time.time() - start_time) * 1000

        self._save_query_history(db, request.knowledge_base_id, request.query)

        return schemas.GraphQLQueryResult(
            query_type=query_type,
            parsed_query=parsed_query,
            matched_entities=matched_entities,
            matched_paths=matched_paths,
            path_edges=path_edges,
            highlight_node_ids=highlight_node_ids,
            highlight_edge_ids=highlight_edge_ids,
            execution_time_ms=execution_time
        )

    def _save_query_history(
        self,
        db: Session,
        knowledge_base_id: int,
        query: str
    ):
        existing = db.query(models.GraphQueryHistory).filter(
            models.GraphQueryHistory.knowledge_base_id == knowledge_base_id,
            models.GraphQueryHistory.query == query
        ).first()

        if existing:
            existing.created_at = func.now()
            db.commit()
            return

        history = models.GraphQueryHistory(
            knowledge_base_id=knowledge_base_id,
            query=query
        )
        db.add(history)
        db.commit()

        max_history = settings.GRAPH_MAX_QUERY_HISTORY
        count = db.query(models.GraphQueryHistory).filter(
            models.GraphQueryHistory.knowledge_base_id == knowledge_base_id
        ).count()

        if count > max_history:
            old_entries = db.query(models.GraphQueryHistory).filter(
                models.GraphQueryHistory.knowledge_base_id == knowledge_base_id
            ).order_by(models.GraphQueryHistory.created_at.asc()).limit(count - max_history).all()
            for entry in old_entries:
                db.delete(entry)
            db.commit()

    def get_query_history(
        self,
        db: Session,
        knowledge_base_id: int
    ) -> schemas.GraphQueryHistoryResponse:
        history = db.query(models.GraphQueryHistory).filter(
            models.GraphQueryHistory.knowledge_base_id == knowledge_base_id
        ).order_by(models.GraphQueryHistory.created_at.desc()).limit(settings.GRAPH_MAX_QUERY_HISTORY).all()

        return schemas.GraphQueryHistoryResponse(
            history=[
                schemas.GraphQueryHistoryItem(
                    id=h.id,
                    query=h.query,
                    created_at=h.created_at
                ) for h in history
            ]
        )

    def get_autocomplete_suggestions(
        self,
        db: Session,
        knowledge_base_id: int,
        prefix: str,
        limit: int = 10
    ) -> schemas.GraphQLAutocompleteResult:
        if not prefix:
            return schemas.GraphQLAutocompleteResult(suggestions=[])

        entities = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id,
            func.lower(models.GraphEntity.name).like(f"{prefix.lower()}%")
        ).order_by(
            func.length(models.GraphEntity.name)
        ).limit(limit).all()

        suggestions = [e.name for e in entities]
        return schemas.GraphQLAutocompleteResult(suggestions=suggestions)
