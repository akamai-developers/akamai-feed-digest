"""Environment variable configuration"""

import os


DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/feeddigest")
VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://vllm-nemotron.feed-digest.svc.cluster.local")
APP_PORT = int(os.environ.get("APP_PORT", "8080"))
