import os
import numpy as np
from typing import List, Optional
import logging
from PIL import Image

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(
        self,
        text_model_name: str = "all-MiniLM-L6-v2",
        clip_model_name: str = "ViT-B-32",
        clip_pretrained: str = "laion2b_s34b_b79k",
        cross_encoder_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        cache_dir: str = "models"
    ):
        self.text_model_name = text_model_name
        self.clip_model_name = clip_model_name
        self.clip_pretrained = clip_pretrained
        self.cross_encoder_name = cross_encoder_name
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        self.text_model = None
        self.clip_model = None
        self.clip_tokenizer = None
        self.clip_preprocess = None
        self.cross_encoder = None

    def _load_text_model(self):
        if self.text_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading text embedding model: {self.text_model_name}")
                self.text_model = SentenceTransformer(
                    self.text_model_name,
                    cache_folder=self.cache_dir
                )
            except Exception as e:
                logger.error(f"Failed to load text model: {e}")
                raise

    def _load_clip_model(self):
        if self.clip_model is None:
            try:
                import open_clip
                import torch
                logger.info(f"Loading CLIP model: {self.clip_model_name}/{self.clip_pretrained}")
                self.clip_model, _, self.clip_preprocess = open_clip.create_model_and_transforms(
                    self.clip_model_name,
                    pretrained=self.clip_pretrained,
                    cache_dir=self.cache_dir
                )
                self.clip_tokenizer = open_clip.get_tokenizer(self.clip_model_name)
                self.clip_model.eval()
                if torch.cuda.is_available():
                    self.clip_model = self.clip_model.cuda()
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            except Exception as e:
                logger.error(f"Failed to load CLIP model: {e}")
                raise

    def _load_cross_encoder(self):
        if self.cross_encoder is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading cross encoder model: {self.cross_encoder_name}")
                self.cross_encoder = CrossEncoder(
                    self.cross_encoder_name,
                    cache_folder=self.cache_dir
                )
            except Exception as e:
                logger.error(f"Failed to load cross encoder: {e}")
                raise

    def encode_text(self, text: str, max_length: int = 512) -> np.ndarray:
        self._load_text_model()
        if not isinstance(text, str):
            text = str(text)
        embedding = self.text_model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embedding.astype(np.float32)

    def encode_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        self._load_text_model()
        texts = [str(t) for t in texts]
        embeddings = self.text_model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=False
        )
        return embeddings.astype(np.float32)

    def encode_image(self, image_path: str) -> np.ndarray:
        self._load_clip_model()
        import torch
        try:
            image = Image.open(image_path).convert("RGB")
            image_tensor = self.clip_preprocess(image).unsqueeze(0).to(self.device)

            with torch.no_grad():
                image_features = self.clip_model.encode_image(image_tensor)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            return image_features.cpu().numpy().flatten().astype(np.float32)
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            raise

    def encode_image_text(self, text: str) -> np.ndarray:
        self._load_clip_model()
        import torch
        try:
            text_tokens = self.clip_tokenizer([text]).to(self.device)

            with torch.no_grad():
                text_features = self.clip_model.encode_text(text_tokens)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            return text_features.cpu().numpy().flatten().astype(np.float32)
        except Exception as e:
            logger.error(f"Failed to encode text with CLIP: {e}")
            raise

    def rerank(self, query: str, documents: List[str], top_n: int = 5) -> List[int]:
        self._load_cross_encoder()
        try:
            pairs = [[query, doc] for doc in documents]
            scores = self.cross_encoder.predict(pairs, show_progress_bar=False)
            ranked_indices = np.argsort(scores)[::-1][:top_n]
            return ranked_indices.tolist(), scores.tolist()
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return list(range(min(top_n, len(documents)))), [1.0] * min(top_n, len(documents))

    def get_text_embedding_dim(self) -> int:
        return 384

    def get_vision_embedding_dim(self) -> int:
        return 512
