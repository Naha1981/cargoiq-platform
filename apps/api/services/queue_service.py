"""
CargoIQ — Queue Service
Enqueues CargoWise execution jobs into BullMQ via Redis.
"""
import json, uuid, time, logging
from typing import Optional
import redis as redis_lib
from ..core.config import settings

logger = logging.getLogger(__name__)
_redis: Optional[redis_lib.Redis] = None

def get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=5)
    return _redis

def enqueue_cw_execution(execution_id: str, shipment_id: str, org_id: str,
                         execution_type: str = "playwright", priority: int = 1) -> str:
    r      = get_redis()
    job_id = str(uuid.uuid4())
    ts     = int(time.time() * 1000)
    key    = f"bull:cw-executions:{job_id}"

    payload = {
        "id": job_id, "name": "execute-cargowise",
        "data": json.dumps({"execution_id": execution_id, "shipment_id": shipment_id,
                             "org_id": org_id, "execution_type": execution_type}),
        "opts": json.dumps({"attempts": 3, "backoff": {"type": "exponential", "delay": 5000},
                             "removeOnComplete": 100, "removeOnFail": 50, "priority": priority}),
        "timestamp": str(ts), "processedOn": "", "finishedOn": "",
        "returnvalue": "", "stacktrace": "[]", "attemptsMade": "0",
        "delay": "0", "priority": str(priority),
    }
    pipe = r.pipeline()
    pipe.hset(key, mapping=payload)
    pipe.zadd("bull:cw-executions:wait", {job_id: ts})
    pipe.publish("bull:cw-executions:events", json.dumps({"event": "waiting", "jobId": job_id}))
    pipe.execute()
    logger.info(f"Enqueued CW job {job_id} for shipment {shipment_id}")
    return job_id

def get_queue_stats() -> dict:
    r = get_redis()
    try:
        return {
            "waiting":   r.zcard("bull:cw-executions:wait"),
            "active":    r.llen("bull:cw-executions:active"),
            "completed": r.zcard("bull:cw-executions:completed"),
            "failed":    r.zcard("bull:cw-executions:failed"),
        }
    except Exception as e:
        return {"error": str(e)}
