"""Feed Digest - AI-curated newsletter system"""

import logging
import os

os.environ.setdefault("LITELLM_LOG", "ERROR")

logging.getLogger("litellm.litellm_core_utils.litellm_logging").setLevel(logging.CRITICAL)
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

