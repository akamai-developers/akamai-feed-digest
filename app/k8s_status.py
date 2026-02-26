"""Kubernetes pod status helper for vLLM InferenceService"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

NAMESPACE = "feed-digest"
LABEL_SELECTOR = "serving.kserve.io/inferenceservice=vllm-nemotron"


def _get_pod_status_sync() -> Optional[dict]:
    """Synchronous k8s API call — run via asyncio.to_thread()"""
    from kubernetes import client, config

    config.load_incluster_config()
    v1 = client.CoreV1Api()

    pods = v1.list_namespaced_pod(
        namespace=NAMESPACE,
        label_selector=LABEL_SELECTOR,
    )

    if not pods.items:
        return {"phase": "No pods found", "container_state": None, "ready": False, "events": []}

    pod = pods.items[0]
    phase = pod.status.phase

    container_state = None
    ready = False
    if pod.status.container_statuses:
        cs = pod.status.container_statuses[0]
        ready = cs.ready or False
        state = cs.state
        if state.running:
            container_state = "Running"
        elif state.waiting:
            container_state = f"Waiting: {state.waiting.reason or 'Unknown'}"
        elif state.terminated:
            container_state = f"Terminated: {state.terminated.reason or 'Unknown'}"

    events_api = v1.list_namespaced_event(
        namespace=NAMESPACE,
        field_selector=f"involvedObject.name={pod.metadata.name}",
    )
    recent_events = sorted(events_api.items, key=lambda e: e.last_timestamp or e.event_time or "", reverse=True)[:5]

    events = []
    for ev in recent_events:
        ts = ev.last_timestamp or ev.event_time
        events.append({
            "reason": ev.reason or "",
            "message": ev.message or "",
            "timestamp": ts.isoformat() if ts else None,
            "type": ev.type or "Normal",
        })

    return {
        "phase": phase,
        "container_state": container_state,
        "ready": ready,
        "events": events,
    }


async def get_vllm_pod_status() -> Optional[dict]:
    """Get vLLM pod status. Returns None when not running in-cluster."""
    try:
        return await asyncio.to_thread(_get_pod_status_sync)
    except Exception as e:
        logger.debug(f"Could not fetch pod status (expected outside cluster): {e}")
        return None
