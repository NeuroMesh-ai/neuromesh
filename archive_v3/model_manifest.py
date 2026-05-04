#!/usr/bin/env python3
"""
Model Manifest — Structure and validation for model files.

Defines the manifest structure for P2P model sharing.
"""

import hashlib
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import logging

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger("ModelManifest")


@dataclass
class ModelManifest:
    """Manifest for a shared model file."""

    model_id: str                     # e.g., "qwen3:8b"
    name: str                         # e.g., "Qwen 2.5 7B"
    file_hash: str                    # SHA256 du fichier complet
    file_size: int                    # Bytes
    chunk_size: int                   # Bytes par chunk
    chunks: int                       # Nombre total de chunks
    version: str                      # Model version
    timestamp: str                    # ISO timestamp
    signature: Optional[str] = None   # Signature Ed25519
    creator: Optional[str] = None     # Peer ID du créateur

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "chunk_size": self.chunk_size,
            "chunks": self.chunks,
            "version": self.version,
            "timestamp": self.timestamp,
            "creator": self.creator,
            "signature": self.signature
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ModelManifest':
        """Create from dictionary."""
        return cls(**data)

    def get_payload_for_signing(self) -> bytes:
        """Get data that should be signed (exclude signature field)."""
        payload = {
            "model_id": self.model_id,
            "name": self.name,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "chunk_size": self.chunk_size,
            "chunks": self.chunks,
            "version": self.version,
            "timestamp": self.timestamp,
            "creator": self.creator
        }
        return json.dumps(payload, sort_keys=True).encode()

    def sign(self, private_key: ed25519.Ed25519PrivateKey) -> None:
        """Sign the manifest with private key."""
        payload = self.get_payload_for_signing()
        signature = private_key.sign(payload)
        self.signature = signature.hex()
        self.creator = "signed"

    def verify(self, public_key: ed25519.Ed25519PublicKey) -> bool:
        """Verify signature with public key."""
        if not self.signature:
            return False

        try:
            payload = self.get_payload_for_signing()
            signature = bytes.fromhex(self.signature)
            public_key.verify(signature, payload)
            return True
        except InvalidSignature:
            logger.warning(f"Invalid signature for model {self.model_id}")
            return False

    def get_chunk_hash(self, chunk_index: int, chunk_data: bytes) -> str:
        """Calculate hash for a specific chunk."""
        h = hashlib.sha256()
        h.update(chunk_data)
        return h.hexdigest()


class ManifestManager:
    """Manage model manifests."""

    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def create_manifest(self, model_id: str, name: str, file_path: str,
                        chunk_size: int = 80 * 1024 * 1024) -> ModelManifest:
        """Create manifest from model file."""

        file_path = Path(file_path)
        file_size = file_path.stat().st_size
        chunks = (file_size + chunk_size - 1) // chunk_size

        # Calculate file hash
        logger.info(f"Calculating hash for {file_size / 1024 / 1024 / 1024:.2f} GB...")
        sha256_hash = self.calculate_file_hash(file_path)

        # Create manifest
        manifest = ModelManifest(
            model_id=model_id,
            name=name,
            file_hash=sha256_hash,
            file_size=file_size,
            chunk_size=chunk_size,
            chunks=chunks,
            version="v1.0",
            timestamp=datetime.now().isoformat()
        )

        logger.info(f"Created manifest: {model_id} ({chunks} chunks)")
        return manifest

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256 = hashlib.sha256()

        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                sha256.update(chunk)

        return sha256.hexdigest()

    def save_manifest(self, manifest: ModelManifest) -> str:
        """Save manifest to file."""
        manifest_path = self.storage_dir / f"{manifest.model_id}_manifest.json"

        with open(manifest_path, 'w') as f:
            json.dump(manifest.to_dict(), f, indent=2)

        logger.info(f"Saved manifest to {manifest_path}")
        return str(manifest_path)

    def load_manifest(self, model_id: str) -> Optional[ModelManifest]:
        """Load manifest from file."""
        manifest_path = self.storage_dir / f"{model_id}_manifest.json"

        if not manifest_path.exists():
            logger.warning(f"Manifest not found for {model_id}")
            return None

        with open(manifest_path, 'r') as f:
            data = json.load(f)
            manifest = ModelManifest.from_dict(data)

        logger.info(f"Loaded manifest for {model_id}")
        return manifest

    def verify_model_file(self, model_id: str, file_path: Path) -> bool:
        """Verify model file matches manifest."""
        manifest = self.load_manifest(model_id)

        if not manifest:
            return False

        # Check hash
        file_hash = self.calculate_file_hash(file_path)
        if file_hash != manifest.file_hash:
            logger.error(f"File hash mismatch for {model_id}")
            return False

        # Check size
        file_size = file_path.stat().st_size
        if file_size != manifest.file_size:
            logger.error(f"File size mismatch for {model_id}")
            return False

        logger.info(f"Model file {model_id} verified")
        return True


# ============ CLI ============

def main():
    import sys

    if len(sys.argv) < 3:
        print("Usage: python model_manifest.py <model_id> <name> <file_path>")
        return 1

    model_id = sys.argv[1]
    name = sys.argv[2]
    file_path = sys.argv[3]

    manager = ManifestManager("/tmp/unitybrain_models")

    # Create manifest
    manifest = manager.create_manifest(model_id, name, file_path)

    # Sign with dummy key (in real usage, would use actual P2P peer key)
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    manifest.sign(private_key)

    # Verify
    if manifest.verify(public_key):
        print("✅ Signature valid")
    else:
        print("❌ Signature invalid")

    # Save
    manager.save_manifest(manifest)

    print(f"\n✅ Manifest created: {model_id}")
    print(f"   Hash: {manifest.file_hash[:16]}...")
    print(f"   Size: {manifest.file_size / 1024 / 1024 / 1024:.2f} GB")
    print(f"   Chunks: {manifest.chunks}")

    return 0


if __name__ == "__main__":
    main()