#!/usr/bin/env python3
"""
Model Sharing — P2P model file distribution system.

BitTorrent-style chunk-based model sharing.
"""

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import aiohttp

from model_manifest import ModelManifest, ManifestManager

logger = logging.getLogger("ModelSharing")


@dataclass
class ChunkInfo:
    """Information about a model chunk."""
    chunk_index: int
    chunk_hash: str
    chunk_size: int
    offset: int
    download_progress: float = 0.0  # 0-100%
    peers: Set[str] = field(default_factory=set)  # Peers who have this chunk


@dataclass
class DownloadModelRequest:
    """Request to download a model."""
    model_id: str
    manifest: ModelManifest
    peers: Set[str]  # Peers that have this model
    chunks_incomplete: List[int]  # Chunks not yet downloaded
    chunks_downloading: Set[int] = field(default_factory=set)
    complete: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ChunkManager:
    """Manage model file chunks."""

    def __init__(self, storage_dir: str, chunk_size: int = 80 * 1024 * 1024):
        self.storage_dir = Path(storage_dir)
        self.chunk_size = chunk_size
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def split_file_into_chunks(self, file_path: Path, manifest: ModelManifest) -> List[ChunkInfo]:
        """Split file into chunks and calculate hashes."""

        chunks = []
        file_size = file_path.stat().st_size
        chunks_count = (file_size + self.chunk_size - 1) // self.chunk_size

        logger.info(f"Splitting {file_path} into {chunks_count} chunks...")

        with open(file_path, 'rb') as f:
            for i in range(chunks_count):
                offset = i * self.chunk_size
                chunk_data = f.read(self.chunk_size)

                # Calculate chunk hash
                h = hashlib.sha256()
                h.update(chunk_data)
                chunk_hash = h.hexdigest()

                chunk_info = ChunkInfo(
                    chunk_index=i,
                    chunk_hash=chunk_hash,
                    chunk_size=len(chunk_data),
                    offset=offset
                )

                chunks.append(chunk_info)

                # Optionally store chunk separately (for RAM-based sharing)
                # self._store_chunk(manifest.model_id, i, chunk_data)

        logger.info(f"Split complete: {len(chunks)} chunks")
        return chunks

    def read_chunk(self, file_path: Path, chunk_index: int, chunk_size: int) -> bytes:
        """Read a specific chunk from file."""

        offset = chunk_index * chunk_size

        with open(file_path, 'rb') as f:
            f.seek(offset)
            chunk_data = f.read(chunk_size)

        return chunk_data

    def write_chunk(self, output_file: Path, chunk_index: int, chunk_data: bytes, chunk_size: int) -> bool:
        """Write a chunk to output file."""

        offset = chunk_index * chunk_size

        try:
            with open(output_file, 'r+b') as f:
                f.seek(offset)
                f.write(chunk_data)
            return True
        except Exception as e:
            logger.error(f"Failed to write chunk {chunk_index}: {e}")
            return False


class ModelDownloader:
    """Download models from P2P network."""

    def __init__(self, storage_dir: str, max_parallel: int = 5):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_parallel = max_parallel
        self.chunk_manager = ChunkManager(str(storage_dir))
        self.active_downloads: Dict[str, DownloadModelRequest] = {}
        self.manifest_manager = ManifestManager(str(storage_dir))

    async def discover_model(self, model_id: str, peers: Set[str],
                            http_client: aiohttp.ClientSession) -> Optional[ModelManifest]:
        """Discover available model manifests from peers."""

        logger.info(f"🔍 Discovering model {model_id} from {len(peers)} peers...")

        for peer_addr in list(peers)[:5]:  # Try first 5 peers
            try:
                url = f"http://{peer_addr}/model/{model_id}/manifest"

                async with http_client.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        manifest = ModelManifest.from_dict(data)
                        logger.info(f"✅ Found manifest for {model_id}")
                        return manifest
            except Exception as e:
                logger.debug(f"Could not get manifest from {peer_addr}: {e}")

        logger.warning(f"❌ Model {model_id} not found")
        return None

    async def discover_chunks(self, model_id: str, peer_addrs: Set[str],
                             http_client: aiohttp.ClientSession) -> List[int]:
        """Discover which chunks are available from each peer."""

        chunk_availability: Dict[int, Set[str]] = {}

        for peer_addr in peer_addrs:
            try:
                url = f"http://{peer_addr}/model/{model_id}/chunks"

                async with http_client.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        available_chunks = data.get('chunks', [])

                        for chunk_index in available_chunks:
                            if chunk_index not in chunk_availability:
                                chunk_availability[chunk_index] = set()
                            chunk_availability[chunk_index].add(peer_addr)

            except Exception as e:
                logger.debug(f"Could not get chunks from {peer_addr}: {e}")

        # Prioritize rarest chunks (fewest sources)
        prioritized = sorted(
            chunk_availability.keys(),
            key=lambda x: len(chunk_availability[x])
        )

        logger.info(f"📊 Found {len(prioritized)} chunks available")
        return prioritized

    async def download_model(self, model_id: str, peer_addrs: Set[str],
                            manifest: Optional[ModelManifest] = None,
                            http_client: Optional[aiohttp.ClientSession] = None) -> bool:
        """Download a model from P2P network."""

        logger.info(f"📥 Starting download of {model_id}...")

        if model_id in self.active_downloads:
            logger.warning(f"Download of {model_id} already in progress")
            return False

        # Discover manifest if not provided
        if not manifest:
            if not http_client:
                http_client = aiohttp.ClientSession()

            manifest = await self.discover_model(model_id, peer_addrs, http_client)
            if not manifest:
                logger.error(f"Could not find manifest for {model_id}")
                return False

        # Save manifest
        self.manifest_manager.save_manifest(manifest)

        # Prepare download request
        chunks_count = manifest.chunks

        request = DownloadModelRequest(
            model_id=model_id,
            manifest=manifest,
            peers=peer_addrs,
            chunks_incomplete=list(range(chunks_count)),
            started_at=datetime.now()
        )

        self.active_downloads[model_id] = request

        # Prepare output file
        output_file = self.storage_dir / f"{model_id}.gguf"
        output_file.touch()  # Create zero-length file
        output_file.truncate(manifest.file_size)  # Allocate space

        # Discover chunk availability
        chunk_priority = await self.discover_chunks(model_id, peer_addrs, http_client)

        # Download chunks in parallel
        success = await self._download_chunks_parallel(
            model_id, chunk_priority, peer_addrs, output_file, http_client
        )

        request.completed_at = datetime.now()

        if success:
            request.complete = True

            # Verify file
            if self.manifest_manager.verify_model_file(model_id, output_file):
                logger.info(f"✅ Model {model_id} download complete and verified")
            else:
                logger.error(f"❌ Model {model_id} verification failed")
                success = False

        del self.active_downloads[model_id]
        return success

    async def _download_chunks_parallel(self, model_id: str, chunk_priority: List[int],
                                        peer_addrs: Set[str], output_file: Path,
                                        http_client: aiohttp.ClientSession) -> bool:
        """Download chunks in parallel."""

        download_tasks = []
        downloaded_count = 0
        total_chunks = len(chunk_priority)
        chunk_size = self.active_downloads[model_id].manifest.chunk_size

        # Create semaphore for parallel limit
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def download_chunk_with_limit(chunk_index: int):
            async with semaphore:
                return await self._download_single_chunk(
                    model_id, chunk_index, peer_addrs, output_file, chunk_size, http_client
                )

        # Download chunks with priority
        for chunk_index in chunk_priority:
            task = asyncio.create_task(download_chunk_with_limit(chunk_index))
            download_tasks.append(task)

        # Wait for all downloads with progress reporting
        completed = 0

        async def update_progress():
            nonlocal completed
            while completed < total_chunks:
                await asyncio.sleep(1)
                progress = (completed / total_chunks) * 100
                logger.info(f"📥 {model_id}: {progress:.1f}% ({completed}/{total_chunks})")

        progress_task = asyncio.create_task(update_progress())

        try:
            for task in asyncio.as_completed(download_tasks):
                success = await task

                if success:
                    completed += 1

        finally:
            progress_task.cancel()

        return completed == total_chunks

    async def _download_single_chunk(self, model_id: str, chunk_index: int,
                                     peer_addrs: Set[str], output_file: Path,
                                     chunk_size: int, http_client: aiohttp.ClientSession) -> bool:
        """Download a single chunk from available peers."""

        request = self.active_downloads[model_id]

        # Try each peer until success
        for peer_addr in peer_addrs:
            if chunk_index in request.chunks_downloading:
                continue  # Downloaded elsewhere

            try:
                url = f"http://{peer_addr}/model/{model_id}/chunk/{chunk_index}"

                async with http_client.get(url, timeout=30) as response:
                    if response.status == 200:
                        chunk_data = await response.read()

                        # Validate chunk hash
                        expected_hash = self.active_downloads[model_id].manifest.get_chunk_hash(
                            chunk_index, chunk_data
                        )

                        calculated_hash = hashlib.sha256(chunk_data).hexdigest()

                        if calculated_hash == expected_hash:
                            # Write chunk to file
                            if self.chunk_manager.write_chunk(output_file, chunk_index, chunk_data, chunk_size):
                                request.chunks_incomplete.remove(chunk_index)
                                logger.debug(f"✅ Chunk {chunk_index} from {peer_addr}")
                                return True
                        else:
                            logger.warning(f"⚠️ Chunk {chunk_index} hash mismatch from {peer_addr}")
            except Exception as e:
                logger.debug(f"Failed to download chunk {chunk_index} from {peer_addr}: {e}")

        request.chunks_downloading.add(chunk_index)
        return False

    def get_download_status(self, model_id: str) -> Optional[Dict]:
        """Get download status for a model."""

        if model_id not in self.active_downloads:
            return None

        request = self.active_downloads[model_id]

        total_chunks = request.manifest.chunks
        downloaded_chunks = total_chunks - len(request.chunks_incomplete)
        progress = (downloaded_chunks / total_chunks) * 100

        return {
            'model_id': model_id,
            'progress': round(progress, 1),
            'downloaded': downloaded_chunks,
            'total': total_chunks,
            'complete': request.complete,
            'started_at': request.started_at.isoformat() if request.started_at else None,
            'peers': len(request.peers)
        }


# ============ CLI ============

async def main():
    import sys

    if len(sys.argv) < 3:
        print("Usage: python model_sharing.py <model_id> <peer_addr1,peer_addr2,...>")
        return 1

    model_id = sys.argv[1]
    peer_addrs = set(sys.argv[2].split(','))

    downloader = ModelDownloader("/tmp/unitybrain_models")

    async with aiohttp.ClientSession() as client:
        success = await downloader.download_model(model_id, peer_addrs, http_client=client)

    if success:
        print(f"✅ Download complete: {model_id}")
    else:
        print(f"❌ Download failed: {model_id}")

    return 0 if success else 1


if __name__ == "__main__":
    asyncio.run(main())