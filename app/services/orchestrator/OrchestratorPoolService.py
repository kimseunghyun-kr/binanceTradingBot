"""
OrchestratorPoolService.py
──────────────────────────────────────────────────────────────────────────
Enhanced orchestrator service with container pooling and result streaming.
Provides better resource utilization and performance.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator

import docker
from pymongo import CursorType

from app.core.db.mongodb_config import mongodb_config
from app.core.pydanticConfig.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

@dataclass
class ContainerInfo:
    """Information about a pooled container."""
    container_id: str
    container_obj: Any
    created_at: float
    last_used: float
    in_use: bool = False
    run_count: int = 0


class OrchestratorPoolService:
    """
    Enhanced orchestrator service with container pooling.

    Architecture:
    1. Pre-warmed container pool for instant execution
    2. Result streaming via MongoDB tailable cursor
    3. Automatic container recycling and health checks
    4. Load balancing across containers
    """

    _instance = None
    _docker_client = None
    _container_pool: List[ContainerInfo] = []
    _pool_size = 5
    _max_runs_per_container = 50
    _container_ttl = 3600  # 1 hour
    _image_name = "tradingbot_orchestrator:concurrent"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def initialize(cls):
        """Initialize service with container pool."""
        try:
            cls._docker_client = docker.from_env()

            # Build orchestrator image
            await cls._build_orchestrator_image()

            # Create result collection with capped size for tailing
            await cls._setup_result_collection()

            # Initialize container pool
            await cls._initialize_container_pool()

            # Start maintenance tasks
            asyncio.create_task(cls._pool_maintenance_loop())

            logger.info(f"Orchestrator pool initialized with {cls._pool_size} containers")

        except Exception as e:
            logger.error(f"Failed to initialize orchestrator pool: {e}")
            raise

    @classmethod
    async def _build_orchestrator_image(cls):
        """Build the concurrent orchestrator Docker image."""
        dockerfile_content = """
FROM python:3.9-slim

WORKDIR /orchestrator

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional concurrency libraries
RUN pip install --no-cache-dir numba uvloop aiofiles

# Copy orchestrator code
COPY . .

# Set Python to use uvloop
ENV PYTHONASYNCIODEBUG=1
ENV PYTHONUNBUFFERED=1

# Entry point
CMD ["python", "-m", "uvloop", "ConcurrentStrategyOrchestrator.py"]
"""

        # Write temporary Dockerfile
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='Dockerfile', delete=False) as f:
            f.write(dockerfile_content)
            dockerfile_path = f.name

        try:
            # Build image
            build_path = os.path.join(settings.BASE_DIR, "strategyOrchestrator")

            image, logs = cls._docker_client.images.build(
                path=build_path,
                dockerfile=dockerfile_path,
                tag=cls._image_name,
                rm=True,
                forcerm=True
            )

            logger.info(f"Built orchestrator image: {cls._image_name}")

        finally:
            os.unlink(dockerfile_path)

    @classmethod
    async def _setup_result_collection(cls):
        """Setup MongoDB collection for result streaming."""
        db = mongodb_config.get_master_client()[settings.MONGO_DB]

        # Create capped collection for real-time updates
        try:
            await db.create_collection(
                "backtest_progress",
                capped=True,
                size=100 * 1024 * 1024,  # 100MB
                max=10000
            )
        except:
            # Collection might already exist
            pass

        # Create indexes
        await db.backtest_progress.create_index([("run_id", 1)])
        await db.backtest_progress.create_index([("timestamp", -1)])

    @classmethod
    async def _initialize_container_pool(cls):
        """Initialize the container pool."""
        tasks = []
        for i in range(cls._pool_size):
            tasks.append(cls._create_container(i))

        containers = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(containers):
            if isinstance(result, Exception):
                logger.error(f"Failed to create container {i}: {result}")
            else:
                cls._container_pool.append(result)

    @classmethod
    async def _create_container(cls, index: int) -> ContainerInfo:
        """Create a new orchestrator container."""
        container_name = f"orchestrator_pool_{index}_{uuid.uuid4().hex[:8]}"

        # Get read-only MongoDB URI
        mongo_read_uri = mongodb_config.get_read_only_uri()

        container = cls._docker_client.containers.create(
            image=cls._image_name,
            name=container_name,
            environment={
                "MONGO_URI": mongo_read_uri,
                "MONGO_DB": settings.MONGO_DB,
                "CONTAINER_INDEX": str(index),
                "PYTHONUNBUFFERED": "1"
            },
            mem_limit="2g",
            cpu_quota=100000,
            stdin_open=True,
            detach=True,
            remove=False  # Keep container for reuse
        )

        # Start container
        container.start()

        # Wait for container to be ready
        await asyncio.sleep(1)

        return ContainerInfo(
            container_id=container.id,
            container_obj=container,
            created_at=time.time(),
            last_used=time.time()
        )

    @classmethod
    async def run_backtest(
            cls,
            strategy_code: str,
            strategy_config: Dict[str, Any],
            symbols: List[str],
            interval: str,
            num_iterations: int,
            additional_params: Optional[Dict[str, Any]] = None,
            stream_progress: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Run backtest with result streaming.

        Yields progress updates and final result.
        """
        run_id = str(uuid.uuid4())

        # Get available container
        container = await cls._get_available_container()
        if not container:
            raise RuntimeError("No available containers in pool")

        try:
            # Mark container as in use
            container.in_use = True
            container.run_count += 1
            container.last_used = time.time()

            # Prepare input
            input_data = cls._prepare_input(
                run_id, strategy_config, symbols, interval,
                num_iterations, additional_params
            )

            # Start progress monitoring
            if stream_progress:
                progress_task = asyncio.create_task(
                    cls._stream_progress(run_id)
                )

            # Execute backtest
            result = await cls._execute_in_container(
                container, strategy_code, input_data, run_id
            )

            # Save final result
            await cls._save_result(run_id, result)

            # Yield final result
            yield result

        finally:
            # Release container
            container.in_use = False

            # Check if container needs recycling
            if container.run_count >= cls._max_runs_per_container:
                await cls._recycle_container(container)

    @classmethod
    async def _get_available_container(cls) -> Optional[ContainerInfo]:
        """Get an available container from the pool."""
        # Try to find available container
        for _ in range(30):  # 30 second timeout
            for container in cls._container_pool:
                if not container.in_use:
                    # Health check
                    try:
                        container.container_obj.reload()
                        if container.container_obj.status == 'running':
                            return container
                    except:
                        # Container is dead, mark for recycling
                        await cls._recycle_container(container)

            await asyncio.sleep(1)

        return None

    @classmethod
    async def _execute_in_container(
            cls,
            container: ContainerInfo,
            strategy_code: str,
            input_data: Dict[str, Any],
            run_id: str
    ) -> Dict[str, Any]:
        """Execute backtest in container."""
        # Write strategy code to container
        exec_result = container.container_obj.exec_run(
            ["sh", "-c", f"cat > /orchestrator/user_strategies/user_strategy.py"],
            stdin=True,
            socket=True
        )

        socket = exec_result.output
        socket._sock.send(strategy_code.encode() + b'\n')
        socket.close()

        # Send input data via stdin
        exec_result = container.container_obj.exec_run(
            ["python", "ConcurrentStrategyOrchestrator.py"],
            stdin=True,
            stdout=True,
            stderr=True,
            stream=True,
            socket=False
        )

        # Send input JSON
        input_json = json.dumps(input_data)

        # Collect output
        output_lines = []
        error_lines = []

        for chunk in exec_result.output:
            line = chunk.decode('utf-8')

            # Check if it's stderr (progress/logs)
            if line.startswith('{"type": "progress"'):
                # Parse and store progress
                try:
                    progress_data = json.loads(line)
                    await cls._update_progress(run_id, progress_data)
                except:
                    pass
            else:
                output_lines.append(line)

        # Parse final output
        output_text = ''.join(output_lines).strip()

        try:
            result = json.loads(output_text)
            result['run_id'] = run_id
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse output: {e}\nOutput: {output_text}")
            raise

    @classmethod
    async def _update_progress(cls, run_id: str, progress_data: Dict[str, Any]):
        """Update progress in MongoDB."""
        db = mongodb_config.get_master_client()[settings.MONGO_DB]

        await db.backtest_progress.insert_one({
            'run_id': run_id,
            'timestamp': datetime.utcnow(),
            **progress_data
        })

    @classmethod
    async def _stream_progress(cls, run_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream progress updates from MongoDB."""
        db = mongodb_config.get_master_client()[settings.MONGO_DB]

        # Create tailable cursor
        cursor = db.backtest_progress.find(
            {'run_id': run_id},
            cursor_type=CursorType.TAILABLE_AWAIT
        )

        while await cursor.fetch_next:
            doc = cursor.next_object()
            if doc:
                yield {
                    'type': 'progress',
                    'progress': doc.get('progress', 0),
                    'timestamp': doc.get('timestamp')
                }

    @classmethod
    async def _save_result(cls, run_id: str, result: Dict[str, Any]):
        """Save final result to MongoDB."""
        db = mongodb_config.get_master_client()[settings.MONGO_DB]

        await db.backtest_results.insert_one({
            'run_id': run_id,
            'created_at': datetime.utcnow(),
            **result
        })

    @classmethod
    async def _recycle_container(cls, container: ContainerInfo):
        """Recycle a container."""
        logger.info(f"Recycling container {container.container_id}")

        try:
            # Stop and remove container
            container.container_obj.stop(timeout=10)
            container.container_obj.remove()
        except:
            pass

        # Remove from pool
        cls._container_pool.remove(container)

        # Create replacement
        try:
            new_container = await cls._create_container(len(cls._container_pool))
            cls._container_pool.append(new_container)
        except Exception as e:
            logger.error(f"Failed to create replacement container: {e}")

    @classmethod
    async def _pool_maintenance_loop(cls):
        """Periodic maintenance of container pool."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                current_time = time.time()

                for container in cls._container_pool[:]:
                    # Check container age
                    if current_time - container.created_at > cls._container_ttl:
                        if not container.in_use:
                            await cls._recycle_container(container)

                    # Health check
                    try:
                        container.container_obj.reload()
                        if container.container_obj.status != 'running':
                            if not container.in_use:
                                await cls._recycle_container(container)
                    except:
                        if not container.in_use:
                            await cls._recycle_container(container)

                # Ensure pool size
                while len(cls._container_pool) < cls._pool_size:
                    try:
                        new_container = await cls._create_container(len(cls._container_pool))
                        cls._container_pool.append(new_container)
                    except:
                        break

            except Exception as e:
                logger.error(f"Pool maintenance error: {e}")

    @classmethod
    def _prepare_input(
            cls,
            run_id: str,
            strategy_config: Dict[str, Any],
            symbols: List[str],
            interval: str,
            num_iterations: int,
            additional_params: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare input for orchestrator."""
        return {
            'run_id': run_id,
            'strategy_config': strategy_config,
            'symbols': symbols,
            'interval': interval,
            'num_iterations': num_iterations,
            'params': additional_params or {},
            'timestamp': datetime.utcnow().isoformat()
        }

    @classmethod
    async def get_pool_status(cls) -> Dict[str, Any]:
        """Get current pool status."""
        return {
            'total_containers': len(cls._container_pool),
            'available_containers': sum(1 for c in cls._container_pool if not c.in_use),
            'in_use_containers': sum(1 for c in cls._container_pool if c.in_use),
            'containers': [
                {
                    'id': c.container_id[:12],
                    'in_use': c.in_use,
                    'run_count': c.run_count,
                    'age_seconds': time.time() - c.created_at
                }
                for c in cls._container_pool
            ]
        }

    @classmethod
    async def cleanup(cls):
        """Cleanup all containers."""
        for container in cls._container_pool:
            try:
                container.container_obj.stop(timeout=5)
                container.container_obj.remove()
            except:
                pass

        cls._container_pool.clear()


# Global instance
orchestrator_pool = OrchestratorPoolService()