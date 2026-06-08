from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import logging
import asyncio

from ..database import get_db
from .. import models, schemas
from ..services.pipeline_service import service_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-graph", tags=["知识图谱"])


@router.get("/{kb_id}/stats", response_model=schemas.GraphStats)
def get_graph_stats(kb_id: int, db: Session = Depends(get_db)):
    kb = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.id == kb_id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    try:
        stats = service_manager.graph_query_service.get_graph_stats(db, kb_id)
        return stats
    except Exception as e:
        logger.error(f"Failed to get graph stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}/graph-data", response_model=schemas.GraphData)
def get_graph_data(
    kb_id: int,
    filter_entity_types: Optional[List[str]] = Query(None),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    kb = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.id == kb_id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    try:
        graph_data = service_manager.graph_query_service.get_graph_data(
            db, kb_id, filter_entity_types, limit
        )
        return graph_data
    except Exception as e:
        logger.error(f"Failed to get graph data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/{entity_id}", response_model=schemas.GraphEntityDetail)
def get_entity_detail(entity_id: int, db: Session = Depends(get_db)):
    try:
        entity = service_manager.graph_query_service.get_entity_detail(db, entity_id)
        return entity
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get entity detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}/entities", response_model=List[schemas.GraphEntity])
def list_entities(
    kb_id: int,
    entity_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    kb = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.id == kb_id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    query = db.query(models.GraphEntity).filter(
        models.GraphEntity.knowledge_base_id == kb_id
    )
    if entity_type:
        query = query.filter(models.GraphEntity.entity_type == entity_type)

    entities = query.offset(skip).limit(limit).all()

    result = []
    for entity in entities:
        occurrence_count = db.query(models.EntityOccurrence).filter(
            models.EntityOccurrence.entity_id == entity.id
        ).count()
        document_count = db.query(
            func.count(func.distinct(models.EntityOccurrence.document_id))
        ).filter(
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

    return result


@router.get("/{kb_id}/relations", response_model=List[schemas.GraphRelation])
def list_relations(
    kb_id: int,
    relation_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    kb = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.id == kb_id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    query = db.query(models.GraphRelation).filter(
        models.GraphRelation.knowledge_base_id == kb_id
    )
    if relation_type:
        query = query.filter(models.GraphRelation.relation_type == relation_type)

    relations = query.offset(skip).limit(limit).all()

    result = []
    for rel in relations:
        source = db.query(models.GraphEntity).filter(
            models.GraphEntity.id == rel.source_entity_id
        ).first()
        target = db.query(models.GraphEntity).filter(
            models.GraphEntity.id == rel.target_entity_id
        ).first()

        result.append(schemas.GraphRelation(
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
        ))

    return result


@router.post("/entities", response_model=schemas.GraphEntity, status_code=status.HTTP_201_CREATED)
def create_entity(data: schemas.GraphEntityCreate, db: Session = Depends(get_db)):
    try:
        entity = service_manager.graph_query_service.create_entity(
            db, data, service_manager.graph_service
        )
        return entity
    except Exception as e:
        logger.error(f"Failed to create entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/entities/{entity_id}", response_model=schemas.GraphEntity)
def update_entity(
    entity_id: int,
    data: schemas.GraphEntityUpdate,
    db: Session = Depends(get_db)
):
    try:
        entity = service_manager.graph_query_service.update_entity(
            db, entity_id, data, service_manager.graph_service
        )
        return entity
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(entity_id: int, db: Session = Depends(get_db)):
    try:
        service_manager.graph_query_service.delete_entity(
            db, entity_id, service_manager.graph_service
        )
        return None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/relations", response_model=schemas.GraphRelation, status_code=status.HTTP_201_CREATED)
def create_relation(data: schemas.GraphRelationCreate, db: Session = Depends(get_db)):
    try:
        relation = service_manager.graph_query_service.create_relation(
            db, data, service_manager.graph_service
        )
        return relation
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create relation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/relations/{relation_id}", response_model=schemas.GraphRelation)
def update_relation(
    relation_id: int,
    data: schemas.GraphRelationUpdate,
    db: Session = Depends(get_db)
):
    try:
        relation = service_manager.graph_query_service.update_relation(
            db, relation_id, data, service_manager.graph_service
        )
        return relation
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update relation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/relations/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(relation_id: int, db: Session = Depends(get_db)):
    try:
        service_manager.graph_query_service.delete_relation(
            db, relation_id, service_manager.graph_service
        )
        return None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete relation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build", response_model=schemas.GraphBuildProgress)
def build_graph(
    request: schemas.GraphBuildRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    kb = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.id == request.knowledge_base_id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    stats = db.query(models.KnowledgeBaseGraphStats).filter(
        models.KnowledgeBaseGraphStats.knowledge_base_id == request.knowledge_base_id
    ).first()
    if not stats:
        stats = models.KnowledgeBaseGraphStats(
            knowledge_base_id=request.knowledge_base_id,
            build_status=models.GraphBuildStatus.PENDING,
            build_progress=0.0
        )
        db.add(stats)
        db.commit()

    def build_task():
        from app.database import SessionLocal
        db_bg = SessionLocal()
        try:
            def progress_callback(progress, stage, processed=None, total=None):
                stats.build_progress = progress
                stats.build_status = models.GraphBuildStatus.BUILDING
                db_bg.commit()

            service_manager.graph_service.build_graph_for_knowledge_base(
                db_bg,
                request.knowledge_base_id,
                document_ids=request.document_ids,
                rebuild=request.rebuild,
                progress_callback=progress_callback
            )
        except Exception as e:
            logger.error(f"Graph build task failed: {e}")
            stats.build_status = models.GraphBuildStatus.FAILED
            stats.build_error = str(e)
            db_bg.commit()
        finally:
            db_bg.close()

    background_tasks.add_task(build_task)

    return schemas.GraphBuildProgress(
        status=stats.build_status,
        progress=stats.build_progress,
        stage="开始构建知识图谱..."
    )


@router.get("/{kb_id}/build-progress", response_model=schemas.GraphBuildProgress)
def get_build_progress(kb_id: int, db: Session = Depends(get_db)):
    stats = db.query(models.KnowledgeBaseGraphStats).filter(
        models.KnowledgeBaseGraphStats.knowledge_base_id == kb_id
    ).first()

    if not stats:
        return schemas.GraphBuildProgress(
            status=models.GraphBuildStatus.PENDING,
            progress=0.0
        )

    return schemas.GraphBuildProgress(
        status=stats.build_status,
        progress=stats.build_progress,
        stage=None,
        entity_count=stats.entity_count,
        relation_count=stats.relation_count,
        error=stats.build_error
    )


@router.post("/query")
def query_graph(request: schemas.GraphQueryRequest, db: Session = Depends(get_db)):
    try:
        result, debug = service_manager.graph_query_service.query_graph(db, request)
        return {
            "result": result,
            "debug": debug
        }
    except Exception as e:
        logger.error(f"Failed to query graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}/export", response_class=Response)
def export_graph(kb_id: int, db: Session = Depends(get_db)):
    kb = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.id == kb_id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    try:
        graphml_content = service_manager.graph_service.export_graphml(db, kb_id)

        filename = f"{kb.name}_graph.graphml".replace(" ", "_")

        return Response(
            content=graphml_content,
            media_type="application/graphml+xml",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        logger.error(f"Failed to export graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{kb_id}/clear", status_code=status.HTTP_204_NO_CONTENT)
def clear_graph(kb_id: int, db: Session = Depends(get_db)):
    kb = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.id == kb_id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    try:
        service_manager.graph_service.clear_knowledge_base_graph(db, kb_id)
        return None
    except Exception as e:
        logger.error(f"Failed to clear graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))
