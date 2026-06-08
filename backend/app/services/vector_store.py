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
                "chunk_id": str(chunk.get("id", 0)),
                "document_id": str(chunk.get("document_id", 0)),
                "chunk_index": str(chunk.get("chunk_index", 0)),
                "page_number": str(chunk.get("page_number", 0) or 0),
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
            where = {"document_id": {"$in": [str(doc_id) for doc_id in filter_document_ids]}}

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
                        "chunk_id": int(metadata.get("chunk_id", 0)),
                        "document_id": int(metadata.get("document_id", 0)),
                        "chunk_index": int(metadata.get("chunk_index", 0)),
                        "page_number": int(metadata.get("page_number", 0)),
                        "content": results["documents"][0][i],
                        "semantic_score": float(similarity),
                    })

            return formatted_results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def delete_chunks_by_embedding_ids(self, knowledge_base_id: int, embedding_ids: List[str], content_type: str = "text"):
        collection_name = self._get_collection_name(knowledge_base_id, content_type)
        try:
            collection = self.client.get_collection(name=collection_name)
            collection.delete(ids=embedding_ids)
            logger.info(f"Deleted {len(embedding_ids)} chunks by embedding_ids from ChromaDB")
        except Exception as e:
            logger.warning(f"Failed to delete chunks by embedding_ids: {e}")

    def delete_chunks_by_document(self, knowledge_base_id: int, document_id: int, content_type: str = "text"):
        collection_name = self._get_collection_name(knowledge_base_id, content_type)
        try:
            collection = self.client.get_collection(name=collection_name)

            all_results = collection.get(
                where={"document_id": {"$eq": str(document_id)}},
                include=["metadatas"]
            )

            if all_results and all_results.get("ids"):
                chunk_ids_to_delete = all_results["ids"]
                collection.delete(ids=chunk_ids_to_delete)
                logger.info(f"Deleted {len(chunk_ids_to_delete)} chunks for document {document_id} from ChromaDB")
            else:
                logger.info(f"No chunks found for document {document_id} in ChromaDB")
        except Exception as e:
            logger.warning(f"Failed to delete chunks for document {document_id}: {e}")

    def get_collection_count(self, knowledge_base_id: int, content_type: str = "text") -> int:
        collection_name = self._get_collection_name(knowledge_base_id, content_type)
        try:
            collection = self.client.get_collection(name=collection_name)
            return collection.count()
        except Exception:
            return 0
