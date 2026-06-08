from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy import func

from ..database import get_db
from .. import models, schemas
from ..services.pipeline_service import service_manager

router = APIRouter(prefix="/api/knowledge-bases", tags=["知识库管理"])


@router.get("", response_model=List[schemas.KnowledgeBase])
def list_knowledge_bases(db: Session = Depends(get_db)):
    kbs = db.query(models.KnowledgeBase).order_by(models.KnowledgeBase.created_at.desc()).all()
    result = []
    for kb in kbs:
        doc_count = db.query(func.count(models.Document.id)).filter(
            models.Document.knowledge_base_id == kb.id
        ).scalar()
        kb_dict = {
            "id": kb.id,
            "name": kb.name,
            "description": kb.description,
            "created_at": kb.created_at,
            "updated_at": kb.updated_at,
            "document_count": doc_count
        }
        result.append(schemas.KnowledgeBase(**kb_dict))
    return result


@router.post("", response_model=schemas.KnowledgeBase, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    kb_data: schemas.KnowledgeBaseCreate,
    db: Session = Depends(get_db)
):
    kb = models.KnowledgeBase(**kb_data.model_dump())
    db.add(kb)
    db.commit()
    db.refresh(kb)

    service_manager.vector_store.create_collection(kb.id, "text")
    service_manager.bm25_index.build_index(kb.id, [])

    return schemas.KnowledgeBase(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
        document_count=0
    )


@router.get("/{kb_id}", response_model=schemas.KnowledgeBase)
def get_knowledge_base(kb_id: int, db: Session = Depends(get_db)):
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    doc_count = db.query(func.count(models.Document.id)).filter(
        models.Document.knowledge_base_id == kb.id
    ).scalar()

    return schemas.KnowledgeBase(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
        document_count=doc_count
    )


@router.put("/{kb_id}", response_model=schemas.KnowledgeBase)
def update_knowledge_base(
    kb_id: int,
    kb_data: schemas.KnowledgeBaseUpdate,
    db: Session = Depends(get_db)
):
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    update_data = kb_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(kb, key, value)

    db.commit()
    db.refresh(kb)

    doc_count = db.query(func.count(models.Document.id)).filter(
        models.Document.knowledge_base_id == kb.id
    ).scalar()

    return schemas.KnowledgeBase(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
        document_count=doc_count
    )


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(kb_id: int, db: Session = Depends(get_db)):
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    documents = db.query(models.Document).filter(models.Document.knowledge_base_id == kb_id).all()
    for doc in documents:
        service_manager.pipeline.delete_document_data(db, doc.id)

    service_manager.vector_store.delete_collection(kb_id, "text")
    service_manager.bm25_index.clear_index(kb_id)

    db.delete(kb)
    db.commit()

    return None
