import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import logging
import uuid

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, host: str = "localhost", port: int = 8000):
        self.host = host
        self.port = port
        self.client = None
        self.text_collection = None
        self.image_collection = None
        self._connect()

    def _connect(self):
        try:
            self.client = chromadb.HttpClient(
                host=self.host,
                port=self.port,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info("Connected to ChromaDB successfully")
        except Exception as e:
            logger.warning(f"Failed to connect to ChromaDB: {e}, using persistent client")
            self.client = chromadb.PersistentClient(
                path="./chroma_data",
                settings=ChromaSettings(anonymized_telemetry=False)
            )

    def _get_collection_name(self, knowledge_base_id: int, content_type: str = "text") -> str:
        return f"kb_{knowledge_base_id}_{content_type}"

    def create_collection(self, knowledge_base_id: int, content_type: str = "text"):
        collection_name = self._get_collection_name(knowledge_base_id, content_type)
        try:
            collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Collection {collection_name} created/loaded")
            return collection
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            raise

    def delete_collection(self, knowledge_base_id: int, content_type: str = "text"):
        collection_name = self._get_collection_name(knowledge_base_id, content_type)
        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Collection {collection_name} deleted")
        except Exception as e:
            logger.warning(f"Failed to delete collection {collection_name}: {e}")

    def add_chunks(
        self,
        knowledge_base_id: int,
        chunks: List[Dict[str, Any]],
        embeddings: List[np.ndarray],
        content_type: str = "text"
    ) -> List[str]:
        collection = self.create_collection(knowledge_base_id, content_type)

        ids = []
        documents = []
        metadatas = []
        embedding_list = []

        for chunk, embedding in zip(chunks, embeddings):
            chunk_id = str(uuid.uuid4())
            ids.append(chunk_id)
            documents.append(chunk["content"])
            metadatas.append({
                "chunk_id": chunk.get("id", 0),
                "document_id": chunk.get("document_id", 0),
                "chunk_index": chunk.get("chunk_index", 0),
                "page_number": chunk.get("page_number", 0) or 0,
                "content_type": content_type,
            })
            embedding_list.append(embedding.tolist())

        try:
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embedding_list
            )
            logger.info(f"Added {len(ids)} chunks to collection {self._get_collection_name(knowledge_base_id, content_type)}")
            return ids
        except Exception as e:
            logger.error(f"Failed to add chunks: {e}")
            raise

    def search(
        self,
        knowledge_base_id: int,
        query_embedding: np.ndarray,
        top_k: int = 10,
        content_type: str = "text",
        filter_document_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        collection_name = self._get_collection_name(knowledge_base_id, content_type)
        try:
            collection = self.client.get_collection(name=collection_name)
        except Exception as e:
            logger.warning(f"Collection {collection_name} not found: {e}")
            return []

        where = None
        if filter_document_ids:
            where = {"document_id": {"$in": filter_document_ids}}

        try:
            results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k,
                where=where,
                include=["metadatas", "documents", "distances"]
            )

            formatted_results = []
            if results.get("ids") and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    metadata = results["metadatas"][0][i]
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    similarity = 1.0 - distance if distance else 0.0

                    formatted_results.append({
                        "chunk_id": metadata.get("chunk_id"),
                        "document_id": metadata.get("document_id"),
                        "chunk_index": metadata.get("chunk_index"),
                        "page_number": metadata.get("page_number"),
                        "content": results["documents"][0][i],
                        "semantic_score": float(similarity),
                    })

            return formatted_results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def delete_chunks_by_document(self, knowledge_base_id: int, document_id: int, content_type: str = "text"):
        collection_name = self._get_collection_name(knowledge_base_id, content_type)
        try:
            collection = self.client.get_collection(name=collection_name)
            collection.delete(
                where={"document_id": document_id}
            )
            logger.info(f"Deleted chunks for document {document_id}")
        except Exception as e:
            logger.warning(f"Failed to delete chunks for document {document_id}: {e}")

    def get_collection_count(self, knowledge_base_id: int, content_type: str = "text") -> int:
        collection_name = self._get_collection_name(knowledge_base_id, content_type)
        try:
            collection = self.client.get_collection(name=collection_name)
            return collection.count()
        except Exception:
            return 0
