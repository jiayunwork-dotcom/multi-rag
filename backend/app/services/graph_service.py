import json
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from neo4j import GraphDatabase, Driver, Session as Neo4jSession
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .. import models, schemas
from ..config import settings
from .llm_service import LLMService
from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class GraphService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_service: Optional[LLMService] = None
    ):
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self._driver: Optional[Driver] = None
        self._init_neo4j()

    def _init_neo4j(self):
        if not settings.GRAPH_ENABLED:
            logger.info("Graph feature disabled, skipping Neo4j initialization")
            self._driver = None
            return

        try:
            uri = f"bolt://{settings.NEO4J_HOST}:{settings.NEO4J_PORT}"
            logger.info(f"Attempting to connect to Neo4j at {uri}...")
            self._driver = GraphDatabase.driver(
                uri,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            self._driver.verify_connectivity()
            logger.info(f"Neo4j connected successfully at {uri}")
        except Exception as e:
            logger.warning(f"Failed to connect to Neo4j: {e}. Graph features will be disabled.")
            self._driver = None

    def is_available(self) -> bool:
        return self._driver is not None

    def close(self):
        if self._driver:
            self._driver.close()
            logger.info("Neo4j connection closed")

    def _get_neo4j_session(self) -> Optional[Neo4jSession]:
        if not self._driver:
            logger.warning("Neo4j driver not available, graph operations will be skipped")
            return None
        return self._driver.session(database=settings.NEO4J_DATABASE)

    def _get_entity_label(self, entity_type: str) -> str:
        label_map = {
            "person": "Person",
            "organization": "Organization",
            "location": "Location",
            "tech_concept": "TechConcept",
            "event": "Event"
        }
        return label_map.get(entity_type, "Entity")

    def _get_relation_type(self, relation_type: str) -> str:
        type_map = {
            "belongs_to": "BELONGS_TO",
            "located_in": "LOCATED_IN",
            "created_by": "CREATED_BY",
            "uses": "USES",
            "depends_on": "DEPENDS_ON",
            "contains": "CONTAINS"
        }
        return type_map.get(relation_type, "RELATED_TO")

    def extract_entities_and_relations(
        self,
        chunk_text: str,
        chunk_id: int,
        document_id: int,
        knowledge_base_id: int
    ) -> schemas.GraphExtractionResult:
        if not self.llm_service:
            logger.warning("LLM service not available, using rule-based extraction")
            return self._rule_based_extraction(chunk_text, chunk_id, document_id)

        prompt = f"""你是一个专业的知识图谱构建助手。请从以下文本中提取实体和关系。

实体类型：
- person: 人物
- organization: 组织、公司、机构
- location: 地点、位置
- tech_concept: 技术概念、技术术语
- event: 事件、活动

关系类型：
- belongs_to: 属于
- located_in: 位于
- created_by: 由...创建
- uses: 使用
- depends_on: 依赖
- contains: 包含

文本内容：
\"\"\"{chunk_text}\"\"\"

请以JSON格式输出，格式如下：
{{
    "entities": [
        {{
            "name": "实体名称",
            "entity_type": "person|organization|location|tech_concept|event",
            "context_snippet": "实体在文本中的上下文片段",
            "start_pos": 实体起始字符位置,
            "end_pos": 实体结束字符位置,
            "confidence": 0.0-1.0的置信度
        }}
    ],
    "relations": [
        {{
            "source_entity": "源实体名称",
            "target_entity": "目标实体名称",
            "source_type": "源实体类型",
            "target_type": "目标实体类型",
            "relation_type": "belongs_to|located_in|created_by|uses|depends_on|contains",
            "context_snippet": "关系在文本中的上下文片段",
            "confidence": 0.0-1.0的置信度
        }}
    ]
}}

只输出JSON，不要有其他文字说明。确保提取的实体和关系准确且有上下文支持。"""

        messages = [
            {"role": "system", "content": "你是一个专业的知识图谱构建助手，能够准确从文本中提取实体和关系。"},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.llm_service.generate(messages)
            content = response.choices[0].message.content

            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)

                entities = []
                for e in data.get("entities", []):
                    try:
                        entities.append(schemas.ExtractedEntity(**e))
                    except Exception as e:
                        logger.warning(f"Invalid entity data: {e}")

                relations = []
                for r in data.get("relations", []):
                    try:
                        relations.append(schemas.ExtractedRelation(**r))
                    except Exception as e:
                        logger.warning(f"Invalid relation data: {e}")

                return schemas.GraphExtractionResult(
                    entities=entities,
                    relations=relations
                )

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")

        return self._rule_based_extraction(chunk_text, chunk_id, document_id)

    def _rule_based_extraction(
        self,
        chunk_text: str,
        chunk_id: int,
        document_id: int
    ) -> schemas.GraphExtractionResult:
        entities: List[schemas.ExtractedEntity] = []
        relations: List[schemas.ExtractedRelation] = []

        org_patterns = [
            r'(公司|集团|有限公司|股份有限公司|研究院|实验室|大学|学院|学校|医院|政府|部门|局|委员会)',
            r'(IBM|Google|Microsoft|Apple|Amazon|Meta|Tesla|NVIDIA|Intel|AMD|Oracle|SAP|Salesforce)',
            r'(华为|中兴|小米|阿里|腾讯|百度|字节跳动|京东|美团|拼多多|网易)'
        ]

        tech_patterns = [
            r'(人工智能|机器学习|深度学习|神经网络|自然语言处理|计算机视觉|大语言模型|LLM|GPT|Transformer)',
            r'(Python|Java|JavaScript|TypeScript|C\+\+|Go|Rust|Swift|Kotlin|SQL|NoSQL)',
            r'(PostgreSQL|MySQL|MongoDB|Redis|Elasticsearch|Neo4j|ChromaDB|向量数据库)',
            r'(FastAPI|Django|Flask|Spring|React|Vue|Angular|Node\.js)',
            r'(Docker|Kubernetes|K8s|微服务|云原生|DevOps|CI/CD)',
            r'(RAG|检索增强生成|知识图谱|图数据库|嵌入向量|语义搜索)'
        ]

        person_patterns = [
            r'(张\w{1,2}|李\w{1,2}|王\w{1,2}|刘\w{1,2}|陈\w{1,2}|杨\w{1,2}|黄\w{1,2}|赵\w{1,2})',
            r'(Elon Musk|Bill Gates|Steve Jobs|Tim Cook|Sundar Pichai|Mark Zuckerberg)',
            r'(Sam Altman|Geoffrey Hinton|Yann LeCun|Andrew Ng|李开复)'
        ]

        loc_patterns = [
            r'(北京|上海|广州|深圳|杭州|南京|武汉|成都|西安|重庆|苏州)',
            r'(中国|美国|日本|韩国|欧洲|北美|亚太|硅谷|中关村)'
        ]

        def find_entities(patterns: List[str], entity_type: str) -> List[Tuple[str, int, int]]:
            found = []
            for pattern in patterns:
                for match in re.finditer(pattern, chunk_text):
                    name = match.group(0)
                    if len(name) >= 2:
                        found.append((name, match.start(), match.end()))
            return found

        org_entities = find_entities(org_patterns, "organization")
        tech_entities = find_entities(tech_patterns, "tech_concept")
        person_entities = find_entities(person_patterns, "person")
        loc_entities = find_entities(loc_patterns, "location")

        seen_names = set()
        all_entities = []

        for name, start, end in org_entities + tech_entities + person_entities + loc_entities:
            if name not in seen_names:
                seen_names.add(name)
                all_entities.append((name, start, end,
                    "organization" if any(name == e[0] for e in org_entities) else
                    "tech_concept" if any(name == e[0] for e in tech_entities) else
                    "person" if any(name == e[0] for e in person_entities) else
                    "location"))

        for name, start, end, etype in all_entities:
            context_start = max(0, start - 30)
            context_end = min(len(chunk_text), end + 30)
            entities.append(schemas.ExtractedEntity(
                name=name,
                entity_type=etype,
                context_snippet=chunk_text[context_start:context_end],
                start_pos=start,
                end_pos=end,
                confidence=0.6
            ))

        if len(entities) >= 2:
            for i, e1 in enumerate(entities):
                for e2 in entities[i+1:]:
                    if e1.entity_type == "tech_concept" and e2.entity_type == "organization":
                        relations.append(schemas.ExtractedRelation(
                            source_entity=e2.name,
                            target_entity=e1.name,
                            source_type="organization",
                            target_type="tech_concept",
                            relation_type="uses",
                            context_snippet=f"{e2.name} 使用 {e1.name}",
                            confidence=0.5
                        ))
                    elif e1.entity_type == "person" and e2.entity_type == "organization":
                        relations.append(schemas.ExtractedRelation(
                            source_entity=e2.name,
                            target_entity=e1.name,
                            source_type="organization",
                            target_type="person",
                            relation_type="created_by",
                            context_snippet=f"{e1.name} 创建/任职于 {e2.name}",
                            confidence=0.5
                        ))
                    elif e1.entity_type == "tech_concept" and e2.entity_type == "tech_concept":
                        relations.append(schemas.ExtractedRelation(
                            source_entity=e1.name,
                            target_entity=e2.name,
                            source_type="tech_concept",
                            target_type="tech_concept",
                            relation_type="depends_on",
                            context_snippet=f"{e1.name} 与 {e2.name} 相关",
                            confidence=0.4
                        ))

        return schemas.GraphExtractionResult(
            entities=entities,
            relations=relations
        )

    def _disambiguate_entity(
        self,
        db: Session,
        extracted_entity: schemas.ExtractedEntity,
        knowledge_base_id: int,
        existing_entities: List[models.GraphEntity]
    ) -> Optional[models.GraphEntity]:
        threshold = settings.GRAPH_ENTITY_DISAMBIGUATION_THRESHOLD

        same_name_type = [
            e for e in existing_entities
            if e.name == extracted_entity.name and e.entity_type == extracted_entity.entity_type
        ]
        if same_name_type:
            return same_name_type[0]

        extracted_embedding = self.embedding_service.encode_text(
            f"{extracted_entity.name} {extracted_entity.entity_type} {extracted_entity.context_snippet}"
        )

        best_match = None
        best_score = 0.0

        for entity in existing_entities:
            if entity.entity_type != extracted_entity.entity_type:
                continue

            if entity.embedding is None:
                continue

            entity_embedding = np.array(entity.embedding)
            similarity = cosine_similarity(
                extracted_embedding.reshape(1, -1),
                entity_embedding.reshape(1, -1)
            )[0][0]

            name_similarity = self._name_similarity(extracted_entity.name, entity.name)
            combined_score = similarity * 0.7 + name_similarity * 0.3

            if combined_score > best_score and combined_score >= threshold:
                best_score = combined_score
                best_match = entity

        return best_match

    def _name_similarity(self, name1: str, name2: str) -> float:
        if name1 == name2:
            return 1.0

        set1 = set(name1)
        set2 = set(name2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def build_graph_for_chunk(
        self,
        db: Session,
        chunk: models.Chunk,
        knowledge_base_id: int
    ) -> Tuple[int, int]:
        if not self.is_available():
            logger.warning("Neo4j not available, skipping graph building for chunk")
            return 0, 0

        extraction_result = self.extract_entities_and_relations(
            chunk_text=chunk.content,
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            knowledge_base_id=knowledge_base_id
        )

        existing_entities = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id
        ).all()

        entity_map: Dict[str, models.GraphEntity] = {}
        new_entity_count = 0

        for extracted_entity in extraction_result.entities:
            matched_entity = self._disambiguate_entity(
                db, extracted_entity, knowledge_base_id, existing_entities
            )

            if matched_entity:
                entity_map[extracted_entity.name] = matched_entity
                existing_entities.append(matched_entity)
            else:
                entity_embedding = self.embedding_service.encode_text(
                    f"{extracted_entity.name} {extracted_entity.entity_type} {extracted_entity.context_snippet}"
                )

                new_entity = models.GraphEntity(
                    knowledge_base_id=knowledge_base_id,
                    name=extracted_entity.name,
                    entity_type=extracted_entity.entity_type,
                    description=extracted_entity.context_snippet[:500],
                    embedding=entity_embedding.tolist(),
                    metadata={"confidence": extracted_entity.confidence}
                )
                db.add(new_entity)
                db.flush()
                db.refresh(new_entity)

                self._create_neo4j_entity(new_entity)

                entity_map[extracted_entity.name] = new_entity
                existing_entities.append(new_entity)
                new_entity_count += 1

            entity_id = entity_map[extracted_entity.name].id
            occurrence = models.EntityOccurrence(
                entity_id=entity_id,
                document_id=chunk.document_id,
                chunk_id=chunk.id,
                context_snippet=extracted_entity.context_snippet,
                start_pos=extracted_entity.start_pos,
                end_pos=extracted_entity.end_pos,
                confidence=extracted_entity.confidence
            )
            db.add(occurrence)

        new_relation_count = 0
        for extracted_relation in extraction_result.relations:
            source_entity = entity_map.get(extracted_relation.source_entity)
            target_entity = entity_map.get(extracted_relation.target_entity)

            if not source_entity or not target_entity:
                continue

            if source_entity.id == target_entity.id:
                continue

            existing_relation = db.query(models.GraphRelation).filter(
                models.GraphRelation.knowledge_base_id == knowledge_base_id,
                models.GraphRelation.source_entity_id == source_entity.id,
                models.GraphRelation.target_entity_id == target_entity.id,
                models.GraphRelation.relation_type == extracted_relation.relation_type
            ).first()

            if existing_relation:
                existing_relation.frequency += 1
                self._update_neo4j_relation_frequency(existing_relation)
            else:
                new_relation = models.GraphRelation(
                    knowledge_base_id=knowledge_base_id,
                    source_entity_id=source_entity.id,
                    target_entity_id=target_entity.id,
                    relation_type=extracted_relation.relation_type,
                    description=extracted_relation.context_snippet[:500],
                    frequency=1,
                    metadata={"confidence": extracted_relation.confidence}
                )
                db.add(new_relation)
                db.flush()
                db.refresh(new_relation)

                self._create_neo4j_relation(source_entity, target_entity, new_relation)
                new_relation_count += 1

            relation_id = existing_relation.id if existing_relation else new_relation.id
            rel_occurrence = models.RelationOccurrence(
                relation_id=relation_id,
                document_id=chunk.document_id,
                chunk_id=chunk.id,
                context_snippet=extracted_relation.context_snippet,
                confidence=extracted_relation.confidence
            )
            db.add(rel_occurrence)

        return new_entity_count, new_relation_count

    def _create_neo4j_entity(self, entity: models.GraphEntity):
        if not self.is_available():
            logger.warning("Neo4j not available, skipping entity creation in graph database")
            return
        try:
            session = self._get_neo4j_session()
            if not session:
                return
            with session:
                label = self._get_entity_label(entity.entity_type)
                result = session.run(
                    f"""
                    MERGE (e:{label} {{id: $id}})
                    SET e.name = $name,
                        e.knowledge_base_id = $kb_id,
                        e.entity_type = $entity_type,
                        e.description = $description
                    RETURN elementId(e) as neo4j_id
                    """,
                    id=entity.id,
                    name=entity.name,
                    kb_id=entity.knowledge_base_id,
                    entity_type=entity.entity_type,
                    description=entity.description or ""
                )
                record = result.single()
                if record:
                    entity.neo4j_id = record["neo4j_id"]
        except Exception as e:
            logger.error(f"Failed to create Neo4j entity: {e}")

    def _create_neo4j_relation(
        self,
        source: models.GraphEntity,
        target: models.GraphEntity,
        relation: models.GraphRelation
    ):
        if not self.is_available():
            logger.warning("Neo4j not available, skipping relation creation in graph database")
            return
        try:
            session = self._get_neo4j_session()
            if not session:
                return
            with session:
                rel_type = self._get_relation_type(relation.relation_type)
                result = session.run(
                    f"""
                    MATCH (s {{id: $source_id}}), (t {{id: $target_id}})
                    MERGE (s)-[r:{rel_type} {{id: $rel_id}}]->(t)
                    SET r.frequency = $frequency,
                        r.description = $description,
                        r.knowledge_base_id = $kb_id
                    RETURN elementId(r) as neo4j_id
                    """,
                    source_id=source.id,
                    target_id=target.id,
                    rel_id=relation.id,
                    frequency=relation.frequency,
                    description=relation.description or "",
                    kb_id=relation.knowledge_base_id
                )
                record = result.single()
                if record:
                    relation.neo4j_id = record["neo4j_id"]
        except Exception as e:
            logger.error(f"Failed to create Neo4j relation: {e}")

    def _update_neo4j_relation_frequency(self, relation: models.GraphRelation):
        if not self.is_available():
            return
        try:
            session = self._get_neo4j_session()
            if not session:
                return
            with session:
                rel_type = self._get_relation_type(relation.relation_type)
                session.run(
                    f"""
                    MATCH ()-[r:{rel_type} {{id: $rel_id}}]->()
                    SET r.frequency = $frequency
                    """,
                    rel_id=relation.id,
                    frequency=relation.frequency
                )
        except Exception as e:
            logger.error(f"Failed to update Neo4j relation frequency: {e}")

    def build_graph_for_document(
        self,
        db: Session,
        document: models.Document,
        rebuild: bool = False,
        progress_callback: Optional[callable] = None
    ) -> Tuple[int, int]:
        knowledge_base_id = document.knowledge_base_id

        if rebuild:
            self.clear_document_graph(db, document.id)

        chunks = document.chunks
        total_chunks = len(chunks)

        total_entities = 0
        total_relations = 0

        for i, chunk in enumerate(chunks):
            try:
                entity_count, relation_count = self.build_graph_for_chunk(
                    db, chunk, knowledge_base_id
                )
                total_entities += entity_count
                total_relations += relation_count

                if progress_callback and total_chunks > 0:
                    progress = (i + 1) / total_chunks * 100
                    progress_callback(progress, i + 1, total_chunks)

            except Exception as e:
                logger.error(f"Failed to build graph for chunk {chunk.id}: {e}")
                continue

        db.commit()
        self._update_kb_graph_stats(db, knowledge_base_id)

        return total_entities, total_relations

    def build_graph_for_knowledge_base(
        self,
        db: Session,
        knowledge_base_id: int,
        document_ids: Optional[List[int]] = None,
        rebuild: bool = False,
        progress_callback: Optional[callable] = None
    ) -> Tuple[int, int]:
        kb = db.query(models.KnowledgeBase).filter(
            models.KnowledgeBase.id == knowledge_base_id
        ).first()
        if not kb:
            raise ValueError(f"Knowledge base {knowledge_base_id} not found")

        stats = db.query(models.KnowledgeBaseGraphStats).filter(
            models.KnowledgeBaseGraphStats.knowledge_base_id == knowledge_base_id
        ).first()
        if not stats:
            stats = models.KnowledgeBaseGraphStats(
                knowledge_base_id=knowledge_base_id,
                build_status=models.GraphBuildStatus.BUILDING,
                build_progress=0.0
            )
            db.add(stats)
        else:
            stats.build_status = models.GraphBuildStatus.BUILDING
            stats.build_progress = 0.0
        db.commit()

        query = db.query(models.Document).filter(
            models.Document.knowledge_base_id == knowledge_base_id,
            models.Document.parse_status == models.ParseStatus.COMPLETED
        )
        if document_ids:
            query = query.filter(models.Document.id.in_(document_ids))

        documents = query.all()
        total_docs = len(documents)

        total_entities = 0
        total_relations = 0

        try:
            for i, doc in enumerate(documents):
                def chunk_progress(chunk_progress, processed, total):
                    if progress_callback:
                        overall_progress = (i + chunk_progress / 100) / total_docs * 100
                        progress_callback(
                            overall_progress,
                            f"处理文档 {doc.title}",
                            processed,
                            total
                        )

                try:
                    entities, relations = self.build_graph_for_document(
                        db, doc, rebuild=rebuild,
                        progress_callback=chunk_progress
                    )
                    total_entities += entities
                    total_relations += relations

                except Exception as e:
                    logger.error(f"Failed to build graph for document {doc.id}: {e}")
                    continue

            stats.build_status = models.GraphBuildStatus.COMPLETED
            stats.build_progress = 100.0
            stats.last_built_at = datetime.utcnow()
            db.commit()

            self._update_kb_graph_stats(db, knowledge_base_id)

            if settings.GRAPH_AUTO_CREATE_VERSION:
                try:
                    self.create_version_snapshot(
                        db,
                        knowledge_base_id,
                        description=f"图谱构建完成 - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to create version snapshot: {e}")

        except Exception as e:
            stats.build_status = models.GraphBuildStatus.FAILED
            stats.build_error = str(e)
            db.commit()
            raise

        return total_entities, total_relations

    def _update_kb_graph_stats(self, db: Session, knowledge_base_id: int):
        stats = db.query(models.KnowledgeBaseGraphStats).filter(
            models.KnowledgeBaseGraphStats.knowledge_base_id == knowledge_base_id
        ).first()

        if not stats:
            stats = models.KnowledgeBaseGraphStats(
                knowledge_base_id=knowledge_base_id
            )
            db.add(stats)

        entity_count = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id
        ).count()

        relation_count = db.query(models.GraphRelation).filter(
            models.GraphRelation.knowledge_base_id == knowledge_base_id
        ).count()

        stats.entity_count = entity_count
        stats.relation_count = relation_count

        db.commit()

    def clear_document_graph(self, db: Session, document_id: int):
        document = db.query(models.Document).filter(
            models.Document.id == document_id
        ).first()
        if not document:
            return

        knowledge_base_id = document.knowledge_base_id

        entity_occurrences = db.query(models.EntityOccurrence).filter(
            models.EntityOccurrence.document_id == document_id
        ).all()

        relation_occurrences = db.query(models.RelationOccurrence).filter(
            models.RelationOccurrence.document_id == document_id
        ).all()

        relation_ids_to_check = set()
        for ro in relation_occurrences:
            relation_ids_to_check.add(ro.relation_id)

        entity_ids_to_check = set()
        for eo in entity_occurrences:
            entity_ids_to_check.add(eo.entity_id)

        db.query(models.EntityOccurrence).filter(
            models.EntityOccurrence.document_id == document_id
        ).delete(synchronize_session=False)

        db.query(models.RelationOccurrence).filter(
            models.RelationOccurrence.document_id == document_id
        ).delete(synchronize_session=False)

        for rel_id in relation_ids_to_check:
            relation = db.query(models.GraphRelation).filter(
                models.GraphRelation.id == rel_id
            ).first()
            if relation:
                remaining_occurrences = db.query(models.RelationOccurrence).filter(
                    models.RelationOccurrence.relation_id == rel_id
                ).count()

                if remaining_occurrences == 0:
                    self._delete_neo4j_relation(relation)
                    db.delete(relation)
                else:
                    relation.frequency = remaining_occurrences
                    self._update_neo4j_relation_frequency(relation)

        for ent_id in entity_ids_to_check:
            entity = db.query(models.GraphEntity).filter(
                models.GraphEntity.id == ent_id
            ).first()
            if entity:
                remaining_occurrences = db.query(models.EntityOccurrence).filter(
                    models.EntityOccurrence.entity_id == ent_id
                ).count()

                if remaining_occurrences == 0:
                    self._delete_neo4j_entity(entity)
                    db.delete(entity)

        db.commit()
        self._update_kb_graph_stats(db, knowledge_base_id)

    def _delete_neo4j_entity(self, entity: models.GraphEntity):
        if not self.is_available():
            return
        try:
            session = self._get_neo4j_session()
            if not session:
                return
            with session:
                session.run(
                    """
                    MATCH (e {id: $id})
                    DETACH DELETE e
                    """,
                    id=entity.id
                )
        except Exception as e:
            logger.error(f"Failed to delete Neo4j entity: {e}")

    def _delete_neo4j_relation(self, relation: models.GraphRelation):
        if not self.is_available():
            return
        try:
            session = self._get_neo4j_session()
            if not session:
                return
            with session:
                rel_type = self._get_relation_type(relation.relation_type)
                session.run(
                    f"""
                    MATCH ()-[r:{rel_type} {{id: $rel_id}}]->()
                    DELETE r
                    """,
                    rel_id=relation.id
                )
        except Exception as e:
            logger.error(f"Failed to delete Neo4j relation: {e}")

    def clear_knowledge_base_graph(self, db: Session, knowledge_base_id: int):
        entities = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id
        ).all()

        for entity in entities:
            self._delete_neo4j_entity(entity)

        db.query(models.GraphRelation).filter(
            models.GraphRelation.knowledge_base_id == knowledge_base_id
        ).delete(synchronize_session=False)

        db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id
        ).delete(synchronize_session=False)

        db.query(models.KnowledgeBaseGraphStats).filter(
            models.KnowledgeBaseGraphStats.knowledge_base_id == knowledge_base_id
        ).delete(synchronize_session=False)

        db.commit()

    def export_graphml(self, db: Session, knowledge_base_id: int) -> str:
        entities = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id
        ).all()

        relations = db.query(models.GraphRelation).filter(
            models.GraphRelation.knowledge_base_id == knowledge_base_id
        ).all()

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"',
            '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            '         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns',
            '         http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
            '  <key id="d0" for="node" attr.name="name" attr.type="string"/>',
            '  <key id="d1" for="node" attr.name="entity_type" attr.type="string"/>',
            '  <key id="d2" for="node" attr.name="description" attr.type="string"/>',
            '  <key id="d3" for="edge" attr.name="relation_type" attr.type="string"/>',
            '  <key id="d4" for="edge" attr.name="frequency" attr.type="int"/>',
            '  <key id="d5" for="edge" attr.name="description" attr.type="string"/>',
            f'  <graph id="G" edgedefault="directed">'
        ]

        for entity in entities:
            desc = (entity.description or "").replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            lines.extend([
                f'    <node id="n{entity.id}">',
                f'      <data key="d0">{entity.name}</data>',
                f'      <data key="d1">{entity.entity_type}</data>',
                f'      <data key="d2">{desc}</data>',
                f'    </node>'
            ])

        for relation in relations:
            desc = (relation.description or "").replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            lines.extend([
                f'    <edge id="e{relation.id}" source="n{relation.source_entity_id}" target="n{relation.target_entity_id}">',
                f'      <data key="d3">{relation.relation_type}</data>',
                f'      <data key="d4">{relation.frequency}</data>',
                f'      <data key="d5">{desc}</data>',
                f'    </edge>'
            ])

        lines.extend([
            '  </graph>',
            '</graphml>'
        ])

        return "\n".join(lines)

    def create_version_snapshot(
        self,
        db: Session,
        knowledge_base_id: int,
        description: Optional[str] = None
    ) -> models.GraphVersion:
        if not settings.GRAPH_AUTO_CREATE_VERSION:
            logger.info("Auto version creation disabled")
            return None

        kb = db.query(models.KnowledgeBase).filter(
            models.KnowledgeBase.id == knowledge_base_id
        ).first()
        if not kb:
            raise ValueError(f"Knowledge base {knowledge_base_id} not found")

        last_version = db.query(models.GraphVersion).filter(
            models.GraphVersion.knowledge_base_id == knowledge_base_id
        ).order_by(models.GraphVersion.version_number.desc()).first()

        next_version = 1
        if last_version:
            next_version = last_version.version_number + 1

        stats = service_manager.graph_query_service.get_graph_stats(db, knowledge_base_id)

        entities = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == knowledge_base_id
        ).all()

        relations = db.query(models.GraphRelation).filter(
            models.GraphRelation.knowledge_base_id == knowledge_base_id
        ).all()

        version = models.GraphVersion(
            knowledge_base_id=knowledge_base_id,
            version_number=next_version,
            entity_count=len(entities),
            relation_count=len(relations),
            connected_components=stats.connected_components,
            description=description or f"版本 {next_version} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        db.add(version)
        db.flush()

        for entity in entities:
            snapshot = models.GraphVersionEntity(
                version_id=version.id,
                entity_id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
                description=entity.description,
                snapshot_entity_metadata=entity.entity_metadata
            )
            db.add(snapshot)

        for relation in relations:
            source = db.query(models.GraphEntity).filter(
                models.GraphEntity.id == relation.source_entity_id
            ).first()
            target = db.query(models.GraphEntity).filter(
                models.GraphEntity.id == relation.target_entity_id
            ).first()

            snapshot = models.GraphVersionRelation(
                version_id=version.id,
                relation_id=relation.id,
                source_entity_id=relation.source_entity_id,
                target_entity_id=relation.target_entity_id,
                source_entity_name=source.name if source else "Unknown",
                target_entity_name=target.name if target else "Unknown",
                relation_type=relation.relation_type,
                description=relation.description,
                snapshot_relation_metadata=relation.relation_metadata
            )
            db.add(snapshot)

        db.commit()
        db.refresh(version)

        logger.info(f"Created graph version {next_version} for KB {knowledge_base_id}")
        return version

    def list_versions(
        self,
        db: Session,
        knowledge_base_id: int,
        skip: int = 0,
        limit: int = 50
    ) -> List[models.GraphVersion]:
        versions = db.query(models.GraphVersion).filter(
            models.GraphVersion.knowledge_base_id == knowledge_base_id
        ).order_by(models.GraphVersion.created_at.desc()).offset(skip).limit(limit).all()
        return versions

    def get_version(
        self,
        db: Session,
        version_id: int
    ) -> Optional[models.GraphVersion]:
        version = db.query(models.GraphVersion).filter(
            models.GraphVersion.id == version_id
        ).first()
        return version

    def get_version_with_snapshots(
        self,
        db: Session,
        version_id: int
    ) -> Optional[schemas.GraphVersion]:
        version = db.query(models.GraphVersion).filter(
            models.GraphVersion.id == version_id
        ).first()
        if not version:
            return None

        entity_snapshots = db.query(models.GraphVersionEntity).filter(
            models.GraphVersionEntity.version_id == version_id
        ).all()

        relation_snapshots = db.query(models.GraphVersionRelation).filter(
            models.GraphVersionRelation.version_id == version_id
        ).all()

        return schemas.GraphVersion(
            id=version.id,
            knowledge_base_id=version.knowledge_base_id,
            version_number=version.version_number,
            entity_count=version.entity_count,
            relation_count=version.relation_count,
            connected_components=version.connected_components,
            description=version.description,
            created_at=version.created_at,
            entities=[
                schemas.GraphVersionSnapshotEntity(
                    entity_id=e.entity_id,
                    name=e.name,
                    entity_type=e.entity_type,
                    description=e.description,
                    metadata=e.snapshot_entity_metadata
                ) for e in entity_snapshots
            ],
            relations=[
                schemas.GraphVersionSnapshotRelation(
                    relation_id=r.relation_id,
                    source_entity_id=r.source_entity_id,
                    target_entity_id=r.target_entity_id,
                    source_entity_name=r.source_entity_name,
                    target_entity_name=r.target_entity_name,
                    relation_type=r.relation_type,
                    description=r.description,
                    metadata=r.snapshot_relation_metadata
                ) for r in relation_snapshots
            ]
        )

    def compare_versions(
        self,
        db: Session,
        version_a_id: Optional[int],
        version_b_id: int,
        knowledge_base_id: int
    ) -> schemas.GraphVersionDiff:
        version_b = self.get_version_with_snapshots(db, version_b_id)
        if not version_b:
            raise ValueError(f"Version {version_b_id} not found")

        if version_a_id:
            version_a = self.get_version_with_snapshots(db, version_a_id)
            if not version_a:
                raise ValueError(f"Version {version_a_id} not found")
        else:
            current_entities = db.query(models.GraphEntity).filter(
                models.GraphEntity.knowledge_base_id == knowledge_base_id
            ).all()
            current_relations = db.query(models.GraphRelation).filter(
                models.GraphRelation.knowledge_base_id == knowledge_base_id
            ).all()

            version_a = schemas.GraphVersion(
                id=0,
                knowledge_base_id=knowledge_base_id,
                version_number=0,
                entity_count=len(current_entities),
                relation_count=len(current_relations),
                connected_components=0,
                description="当前版本",
                created_at=datetime.utcnow(),
                entities=[
                    schemas.GraphVersionSnapshotEntity(
                        entity_id=e.id,
                        name=e.name,
                        entity_type=e.entity_type,
                        description=e.description,
                        metadata=e.entity_metadata
                    ) for e in current_entities
                ],
                relations=[]
            )
            for rel in current_relations:
                source = db.query(models.GraphEntity).filter(
                    models.GraphEntity.id == rel.source_entity_id
                ).first()
                target = db.query(models.GraphEntity).filter(
                    models.GraphEntity.id == rel.target_entity_id
                ).first()
                version_a.relations.append(
                    schemas.GraphVersionSnapshotRelation(
                        relation_id=rel.id,
                        source_entity_id=rel.source_entity_id,
                        target_entity_id=rel.target_entity_id,
                        source_entity_name=source.name if source else "Unknown",
                        target_entity_name=target.name if target else "Unknown",
                        relation_type=rel.relation_type,
                        description=rel.description,
                        metadata=rel.relation_metadata
                    )
                )

        a_entity_keys = {(e.name, e.entity_type) for e in version_a.entities}
        b_entity_keys = {(e.name, e.entity_type) for e in version_b.entities}

        added_entity_keys = b_entity_keys - a_entity_keys
        removed_entity_keys = a_entity_keys - b_entity_keys

        added_entities = [e for e in version_b.entities if (e.name, e.entity_type) in added_entity_keys]
        removed_entities = [e for e in version_a.entities if (e.name, e.entity_type) in removed_entity_keys]

        a_rel_keys = {(r.source_entity_id, r.target_entity_id, str(r.relation_type)) for r in version_a.relations}
        b_rel_keys = {(r.source_entity_id, r.target_entity_id, str(r.relation_type)) for r in version_b.relations}

        added_rel_keys = b_rel_keys - a_rel_keys
        removed_rel_keys = a_rel_keys - b_rel_keys

        added_relations = [r for r in version_b.relations if (r.source_entity_id, r.target_entity_id, str(r.relation_type)) in added_rel_keys]
        removed_relations = [r for r in version_a.relations if (r.source_entity_id, r.target_entity_id, str(r.relation_type)) in removed_rel_keys]

        logger.info(f"Version compare: version_a(v{version_a.version_number}) has {len(version_a.entities)} entities, {len(version_a.relations)} relations")
        logger.info(f"Version compare: version_b(v{version_b.version_number}) has {len(version_b.entities)} entities, {len(version_b.relations)} relations")
        logger.info(f"Version compare: a_rel_keys={a_rel_keys}, b_rel_keys={b_rel_keys}")
        logger.info(f"Version compare: added_rels={len(added_relations)}, removed_rels={len(removed_relations)}")

        return schemas.GraphVersionDiff(
            version_a_id=version_a.id,
            version_a_number=version_a.version_number,
            version_b_id=version_b.id,
            version_b_number=version_b.version_number,
            added_entities=added_entities,
            removed_entities=removed_entities,
            added_relations=added_relations,
            removed_relations=removed_relations,
            added_entity_count=len(added_entities),
            removed_entity_count=len(removed_entities),
            added_relation_count=len(added_relations),
            removed_relation_count=len(removed_relations)
        )

    def preview_merge(
        self,
        db: Session,
        source_kb_id: int,
        target_kb_id: int
    ) -> schemas.GraphMergePreview:
        source_kb = db.query(models.KnowledgeBase).filter(
            models.KnowledgeBase.id == source_kb_id
        ).first()
        target_kb = db.query(models.KnowledgeBase).filter(
            models.KnowledgeBase.id == target_kb_id
        ).first()

        if not source_kb or not target_kb:
            raise ValueError("Source or target knowledge base not found")

        source_entities = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == source_kb_id
        ).all()

        target_entities = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == target_kb_id
        ).all()

        source_relations = db.query(models.GraphRelation).filter(
            models.GraphRelation.knowledge_base_id == source_kb_id
        ).all()

        target_relations = db.query(models.GraphRelation).filter(
            models.GraphRelation.knowledge_base_id == target_kb_id
        ).all()

        pending_conflicts: List[schemas.PendingConflict] = []
        auto_merged_count = 0

        low_threshold = settings.GRAPH_MERGE_CONFLICT_LOW_THRESHOLD
        high_threshold = settings.GRAPH_MERGE_CONFLICT_HIGH_THRESHOLD

        for source_entity in source_entities:
            for target_entity in target_entities:
                if source_entity.name == target_entity.name and source_entity.entity_type == target_entity.entity_type:
                    score = 1.0
                elif source_entity.entity_type != target_entity.entity_type:
                    continue
                else:
                    extracted_entity = schemas.ExtractedEntity(
                        name=source_entity.name,
                        entity_type=source_entity.entity_type,
                        context_snippet=source_entity.description or ""
                    )
                    matched = self._disambiguate_entity(
                        db, extracted_entity, target_kb_id, [target_entity]
                    )
                    if matched and matched.id == target_entity.id:
                        score = 1.0
                    else:
                        if source_entity.embedding and target_entity.embedding:
                            source_emb = np.array(source_entity.embedding)
                            target_emb = np.array(target_entity.embedding)
                            score = cosine_similarity(
                                source_emb.reshape(1, -1),
                                target_emb.reshape(1, -1)
                            )[0][0]
                            name_sim = self._name_similarity(source_entity.name, target_entity.name)
                            score = score * 0.7 + name_sim * 0.3
                        else:
                            score = self._name_similarity(source_entity.name, target_entity.name)

                if score >= high_threshold:
                    auto_merged_count += 1
                elif low_threshold <= score < high_threshold:
                    source_docs = db.query(
                        func.distinct(models.EntityOccurrence.document_id)
                    ).filter(
                        models.EntityOccurrence.entity_id == source_entity.id
                    ).all()
                    source_doc_titles = []
                    for (doc_id,) in source_docs:
                        doc = db.query(models.Document).filter(
                            models.Document.id == doc_id
                        ).first()
                        if doc:
                            source_doc_titles.append(doc.title)

                    source_occurrences = db.query(models.EntityOccurrence).filter(
                        models.EntityOccurrence.entity_id == source_entity.id
                    ).order_by(
                        models.EntityOccurrence.confidence.desc()
                    ).limit(3).all()
                    context_snippets = [
                        occ.context_snippet for occ in source_occurrences
                    ]
                    context_summary = source_entity.description or (
                        context_snippets[0] if context_snippets else ""
                    )

                    target_occurrences = db.query(models.EntityOccurrence).filter(
                        models.EntityOccurrence.entity_id == target_entity.id
                    ).order_by(
                        models.EntityOccurrence.confidence.desc()
                    ).limit(3).all()
                    target_context_snippets = [
                        occ.context_snippet for occ in target_occurrences
                    ]
                    target_context_summary = target_entity.description or (
                        target_context_snippets[0] if target_context_snippets else ""
                    )

                    conflict_id = f"conflict_{source_entity.id}_{target_entity.id}"
                    pending_conflicts.append(schemas.PendingConflict(
                        conflict_id=conflict_id,
                        entity_a=schemas.PendingConflictEntity(
                            entity_id=source_entity.id,
                            name=source_entity.name,
                            entity_type=source_entity.entity_type,
                            source_kb_name=source_kb.name,
                            context_summary=context_summary
                        ),
                        entity_b=schemas.PendingConflictEntity(
                            entity_id=target_entity.id,
                            name=target_entity.name,
                            entity_type=target_entity.entity_type,
                            source_kb_name=target_kb.name,
                            context_summary=target_context_summary
                        ),
                        score=float(score)
                    ))

        return schemas.GraphMergePreview(
            source_kb_id=source_kb_id,
            target_kb_id=target_kb_id,
            source_kb_name=source_kb.name,
            target_kb_name=target_kb.name,
            source_entity_count=len(source_entities),
            source_relation_count=len(source_relations),
            target_entity_count=len(target_entities),
            target_relation_count=len(target_relations),
            auto_merged_count=auto_merged_count,
            pending_count=len(pending_conflicts),
            pending_conflicts=pending_conflicts
        )

    def execute_merge(
        self,
        db: Session,
        source_kb_id: int,
        target_kb_id: int,
        resolutions: List[schemas.GraphMergeResolve]
    ) -> schemas.GraphMergeResult:
        source_entities = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == source_kb_id
        ).all()

        source_relations = db.query(models.GraphRelation).filter(
            models.GraphRelation.knowledge_base_id == source_kb_id
        ).all()

        target_entities = db.query(models.GraphEntity).filter(
            models.GraphEntity.knowledge_base_id == target_kb_id
        ).all()

        entity_id_map: Dict[int, int] = {}
        merged_entity_count = 0
        merged_relation_count = 0

        resolution_map = {
            (r.source_entity_id, r.target_entity_id): r.action
            for r in resolutions
        }

        high_threshold = settings.GRAPH_MERGE_CONFLICT_HIGH_THRESHOLD

        for source_entity in source_entities:
            matched_target = None
            for target_entity in target_entities:
                if source_entity.entity_type != target_entity.entity_type:
                    continue

                action = resolution_map.get((source_entity.id, target_entity.id))

                if action == "keep_separate":
                    continue

                if action == "merge":
                    matched_target = target_entity
                    break

                if source_entity.name == target_entity.name and source_entity.entity_type == target_entity.entity_type:
                    matched_target = target_entity
                    break

                extracted_entity = schemas.ExtractedEntity(
                    name=source_entity.name,
                    entity_type=source_entity.entity_type,
                    context_snippet=source_entity.description or ""
                )
                disambiguated = self._disambiguate_entity(
                    db, extracted_entity, target_kb_id, [target_entity]
                )
                if disambiguated and disambiguated.id == target_entity.id:
                    matched_target = target_entity
                    break

                if source_entity.embedding and target_entity.embedding:
                    source_emb = np.array(source_entity.embedding)
                    target_emb = np.array(target_entity.embedding)
                    score = cosine_similarity(
                        source_emb.reshape(1, -1),
                        target_emb.reshape(1, -1)
                    )[0][0]
                    name_sim = self._name_similarity(source_entity.name, target_entity.name)
                    combined_score = score * 0.7 + name_sim * 0.3
                    if combined_score >= high_threshold:
                        matched_target = target_entity
                        break

            if matched_target:
                entity_id_map[source_entity.id] = matched_target.id
                merged_entity_count += 1
            else:
                new_entity = models.GraphEntity(
                    knowledge_base_id=target_kb_id,
                    name=source_entity.name,
                    entity_type=source_entity.entity_type,
                    description=source_entity.description,
                    embedding=source_entity.embedding,
                    entity_metadata=source_entity.entity_metadata
                )
                db.add(new_entity)
                db.flush()
                db.refresh(new_entity)
                self._create_neo4j_entity(new_entity)
                entity_id_map[source_entity.id] = new_entity.id
                merged_entity_count += 1

        source_entity_ids = {e.id for e in source_entities}
        for source_relation in source_relations:
            new_source_id = entity_id_map.get(source_relation.source_entity_id)
            new_target_id = entity_id_map.get(source_relation.target_entity_id)

            if not new_source_id or not new_target_id:
                continue

            if new_source_id == new_target_id:
                continue

            existing = db.query(models.GraphRelation).filter(
                models.GraphRelation.knowledge_base_id == target_kb_id,
                models.GraphRelation.source_entity_id == new_source_id,
                models.GraphRelation.target_entity_id == new_target_id,
                models.GraphRelation.relation_type == source_relation.relation_type
            ).first()

            if existing:
                existing.frequency += source_relation.frequency
                self._update_neo4j_relation_frequency(existing)
            else:
                new_source = db.query(models.GraphEntity).filter(
                    models.GraphEntity.id == new_source_id
                ).first()
                new_target = db.query(models.GraphEntity).filter(
                    models.GraphEntity.id == new_target_id
                ).first()

                new_relation = models.GraphRelation(
                    knowledge_base_id=target_kb_id,
                    source_entity_id=new_source_id,
                    target_entity_id=new_target_id,
                    relation_type=source_relation.relation_type,
                    description=source_relation.description,
                    frequency=source_relation.frequency,
                    relation_metadata=source_relation.relation_metadata
                )
                db.add(new_relation)
                db.flush()
                db.refresh(new_relation)
                self._create_neo4j_relation(new_source, new_target, new_relation)
                merged_relation_count += 1

        db.commit()

        new_version = None
        if settings.GRAPH_AUTO_CREATE_VERSION:
            try:
                new_version = self.create_version_snapshot(
                    db,
                    target_kb_id,
                    description=f"合并图谱 - 从 {source_kb_id} 到 {target_kb_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to create version after merge: {e}")

        return schemas.GraphMergeResult(
            success=True,
            new_version_id=new_version.id if new_version else None,
            merged_entity_count=merged_entity_count,
            merged_relation_count=merged_relation_count,
            conflict_resolved_count=len(resolutions)
        )

from .pipeline_service import service_manager
