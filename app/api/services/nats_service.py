import os
import json
import asyncio
import logging
from typing import Any, Dict, Optional, Callable
from datetime import datetime
import nats
from nats.errors import ConnectionClosedError, TimeoutError as NatsTimeoutError
from nats.js import JetStreamContext
from nats.js.api import StreamConfig, ConsumerConfig

logger = logging.getLogger(__name__)

class NATSService:
    def __init__(self):
        self.url = os.getenv("NATS_URL", "nats://localhost:4222")
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[JetStreamContext] = None
        self._subscriptions = []
        self._connected = False
        
    async def connect(self) -> None:
        """Connect to NATS server and initialize JetStream"""
        try:
            self.nc = await nats.connect(
                servers=[self.url],
                name="streamops-api",
                reconnect_time_wait=2,
                max_reconnect_attempts=60,
                error_cb=self._error_callback,
                disconnected_cb=self._disconnected_callback,
                reconnected_cb=self._reconnected_callback,
            )
            
            # Initialize JetStream
            self.js = self.nc.jetstream()
            
            # Create streams
            await self._create_streams()
            
            self._connected = True
            logger.info(f"Connected to NATS at {self.url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from NATS"""
        if self.nc and not self.nc.is_closed:
            await self.nc.drain()
            await self.nc.close()
            self._connected = False
            logger.info("Disconnected from NATS")
    
    async def _create_streams(self) -> None:
        """Create JetStream streams for different job types"""
        streams = [
            {
                "name": "JOBS",
                "subjects": ["jobs.>"],
                "max_age": 86400 * 7,  # 7 days
                "max_msgs": 100000,
                "storage": "file",
                "retention": "workqueue",
                "discard": "old",
            },
            {
                "name": "EVENTS",
                "subjects": ["events.>"],
                "max_age": 86400,  # 1 day
                "max_msgs": 10000,
                "storage": "memory",
                "retention": "limits",
                "discard": "old",
            },
            {
                "name": "METRICS",
                "subjects": ["metrics.>"],
                "max_age": 86400 * 30,  # 30 days
                "max_msgs": 100000,
                "storage": "file",
                "retention": "limits",
                "discard": "old",
            },
        ]
        
        for stream_config in streams:
            try:
                config = StreamConfig(**stream_config)
                await self.js.add_stream(config)
                logger.info(f"Created/updated stream: {stream_config['name']}")
            except Exception as e:
                if "stream name already in use" not in str(e):
                    logger.error(f"Failed to create stream {stream_config['name']}: {e}")
    
    async def publish_job(self, job_type: str, job_data: Dict[str, Any]) -> str:
        """Publish a job to the queue"""
        if not self._connected:
            raise ConnectionError("Not connected to NATS")
        
        subject = f"jobs.{job_type}"
        message = {
            "id": job_data.get("id"),
            "type": job_type,
            "data": job_data,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        try:
            ack = await self.js.publish(
                subject,
                json.dumps(message).encode(),
            )
            logger.info(f"Published job {job_data.get('id')} to {subject}")
            return ack.seq
        except Exception as e:
            logger.error(f"Failed to publish job: {e}")
            raise
    
    async def subscribe_jobs(
        self,
        job_type: str,
        handler: Callable,
        queue_group: str = "workers"
    ) -> None:
        """Subscribe to jobs of a specific type"""
        if not self._connected:
            raise ConnectionError("Not connected to NATS")
        
        subject = f"jobs.{job_type}"
        
        async def message_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await handler(data)
                await msg.ack()
            except Exception as e:
                logger.error(f"Error processing job: {e}")
                await msg.nak()
        
        # Create durable consumer
        consumer_config = ConsumerConfig(
            durable_name=f"{job_type}_consumer",
            filter_subject=subject,
            ack_policy="explicit",
            max_deliver=3,
            ack_wait=300,  # 5 minutes
        )
        
        try:
            sub = await self.js.pull_subscribe(
                subject,
                durable=consumer_config.durable_name,
                config=consumer_config,
            )
            self._subscriptions.append(sub)
            
            # Start consuming messages
            asyncio.create_task(self._consume_messages(sub, message_handler))
            
            logger.info(f"Subscribed to {subject}")
        except Exception as e:
            logger.error(f"Failed to subscribe to {subject}: {e}")
            raise
    
    async def _consume_messages(self, subscription, handler):
        """Continuously consume messages from subscription"""
        while self._connected:
            try:
                messages = await subscription.fetch(batch=10, timeout=1)
                for msg in messages:
                    await handler(msg)
            except NatsTimeoutError:
                # Timeout is normal when no messages
                continue
            except Exception as e:
                logger.error(f"Error consuming messages: {e}")
                await asyncio.sleep(1)
    
    async def publish_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Publish an event"""
        if not self._connected:
            return
        
        subject = f"events.{event_type}"
        message = {
            "type": event_type,
            "data": event_data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        try:
            await self.nc.publish(
                subject,
                json.dumps(message).encode(),
            )
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
    
    async def publish_metric(self, metric_name: str, value: Any, tags: Dict[str, str] = None) -> None:
        """Publish a metric"""
        if not self._connected:
            return
        
        subject = f"metrics.{metric_name}"
        message = {
            "name": metric_name,
            "value": value,
            "tags": tags or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        try:
            await self.nc.publish(
                subject,
                json.dumps(message).encode(),
            )
        except Exception as e:
            logger.error(f"Failed to publish metric: {e}")
    
    async def _error_callback(self, e):
        logger.error(f"NATS error: {e}")
    
    async def _disconnected_callback(self):
        logger.warning("Disconnected from NATS")
        self._connected = False
    
    async def _reconnected_callback(self):
        logger.info("Reconnected to NATS")
        self._connected = True
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self.nc and not self.nc.is_closed