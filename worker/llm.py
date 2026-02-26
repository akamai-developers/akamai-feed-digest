"""Direct vLLM API calls for the Feed Digest pipeline.

Replaces CrewAI agents with simple HTTP calls — one LLM call per batch
for scoring, one call for the newsletter briefing.
"""

import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

BATCH_SIZE = 20
MAX_CONTENT_LEN_SCORE = 500
MAX_CONTENT_LEN_BRIEF = 1000


def _get_model_name(base_url: str) -> str:
    """Discover the served model name from the vLLM /v1/models endpoint."""
    resp = httpx.get(f"{base_url}/v1/models", timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("data"):
        raise ValueError("vLLM server returned no models")

    model_id = data["data"][0]["id"]
    logger.info(f"Discovered vLLM model: {model_id}")
    return model_id


def _chat(base_url: str, model: str, system: str, user: str,
          temperature: float = 0.7, max_tokens: int = 2500) -> str:
    """Send a single chat-completion request to the vLLM OpenAI-compatible API."""
    resp = httpx.post(
        f"{base_url}/v1/chat/completions",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_scores(raw: str) -> dict:
    """Extract a JSON array of {id, score} objects from raw LLM output."""
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        logger.error(f"No JSON array found in scorer output: {raw[:200]}")
        return {}

    try:
        items = json.loads(match.group())
        scores = {}
        for item in items:
            if isinstance(item, dict) and "id" in item and "score" in item:
                score = int(item["score"])
                scores[int(item["id"])] = max(1, min(10, score))
        return scores
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse scores: {e}")
        return {}


SCORER_SYSTEM = """/no_think

You are a strict content relevance scorer. You evaluate articles ONLY
against the specific interests listed by the user. Be harsh and
discriminating:

- 8-10: Article is directly and primarily about one of the listed interests
- 5-7: Article is tangentially related or touches on a listed interest as a subtopic
- 1-4: Article is NOT about any of the listed interests, even if it is interesting

An article about AI should score LOW if AI is not in the interest list.
An article about databases should score LOW if databases is not listed.
Do not give high scores just because an article is well-written or popular.
ONLY the user's stated interests matter. Return structured JSON output."""

EDITOR_SYSTEM = """/no_think

You are a skilled newsletter editor who creates compelling daily briefings.
You identify common themes across articles, highlight key insights, and
connect ideas in ways that add value beyond the individual pieces. Your
writing is clear, informative, and organized with sections and source
citations. You output clean HTML markup (no markdown)."""


def score_articles(articles: list, interests: str, base_url: str,
                   model: str) -> dict:
    """Score articles in batches of BATCH_SIZE. Returns {article_id: score}."""
    all_scores = {}

    for i in range(0, len(articles), BATCH_SIZE):
        batch = articles[i:i + BATCH_SIZE]

        summaries = []
        for a in batch:
            content = (a["content"] or "")[:MAX_CONTENT_LEN_SCORE]
            summaries.append(
                f'ID: {a["id"]}\nTitle: {a["title"]}\nContent: {content}'
            )
        articles_text = "\n---\n".join(summaries)

        user_prompt = (
            f"The user's ONLY interests are: {interests}\n\n"
            "Score each article STRICTLY by how directly it relates to "
            "the interests listed above. Articles about topics NOT in the "
            "list should score 1-4 even if they are tech-related.\n\n"
            f"Articles to score:\n{articles_text}\n\n"
            "Return ONLY a JSON array. Each element must have \"id\" (integer) "
            "and \"score\" (integer 1-10).\n"
            "Example: [{\"id\": 1, \"score\": 8}, {\"id\": 2, \"score\": 3}]\n\n"
            "Do not include any text outside the JSON array."
        )

        raw = _chat(base_url, model, SCORER_SYSTEM, user_prompt)
        batch_scores = _parse_scores(raw)
        all_scores.update(batch_scores)
        logger.info(f"Scored batch {i // BATCH_SIZE + 1}: {len(batch_scores)} articles")

    return all_scores


def write_briefing(articles: list, interests: str, base_url: str,
                   model: str) -> str:
    """Write a newsletter briefing from the top-scored articles."""
    texts = []
    for a in articles:
        content = (a["content"] or "")[:MAX_CONTENT_LEN_BRIEF]
        url = a.get("url", "")
        texts.append(
            f'Title: {a["title"]}\nURL: {url}\nSource: {a["source"]}\n'
            f'Score: {a["score"]}/10\nContent: {content}'
        )
    articles_text = "\n---\n".join(texts)

    user_prompt = (
        f"Write a newsletter briefing for a reader interested in: {interests}\n\n"
        f"Articles:\n{articles_text}\n\n"
        "Requirements:\n"
        f"- There are EXACTLY {len(articles)} articles — each one must appear ONCE and only once\n"
        "- Each article MUST start with its title as an HTML link: "
        '<a href="URL" target="_blank"><strong>Title</strong></a> '
        "(source)\n"
        "- Keep each article summary to 2-3 sentences\n"
        "- Group articles into 2-4 thematic sections with <h3> headings\n"
        "- Do NOT repeat any article in multiple sections\n"
        "- Wrap each article entry in a <p> tag\n"
        "- Keep the total briefing under 800 words\n"
        "- START with an <h3>What to Watch</h3> section: a short italic (<em>) "
        "paragraph previewing the key themes, specific to the reader's interests "
        "— do NOT write generic AI industry commentary\n"
        "- Follow it with an <hr> divider, then the article sections\n"
        "- Output ONLY raw HTML — no markdown, no code fences\n\n"
        "Return the briefing as raw HTML."
    )

    result = _chat(base_url, model, EDITOR_SYSTEM, user_prompt).strip()
    # Strip code fences if the model wraps output in ```html ... ```
    result = re.sub(r'^```html\s*\n?', '', result)
    result = re.sub(r'\n?```\s*$', '', result)
    return result.strip()


def run_pipeline(articles: list, interests: str, vllm_base_url: str,
                 top_n: int = 10) -> tuple:
    """Run the full scoring + briefing pipeline.

    Returns (briefing_text, scored_article_ids, all_scores).
    Same signature as the old crew.run_pipeline so main.py needs minimal changes.
    """
    model = _get_model_name(vllm_base_url)

    # Score articles
    all_scores = score_articles(articles, interests, vllm_base_url, model)

    # Select top-N articles by score
    sorted_ids = sorted(all_scores, key=lambda aid: all_scores[aid], reverse=True)
    top_ids = sorted_ids[:top_n]

    top_articles = []
    for a in articles:
        if a["id"] in top_ids:
            top_articles.append({**a, "score": all_scores[a["id"]]})
    top_articles.sort(key=lambda a: a["score"], reverse=True)

    if not top_articles:
        return "No articles scored high enough to include.", [], all_scores

    # Write briefing
    briefing = write_briefing(top_articles, interests, vllm_base_url, model)

    return briefing, [a["id"] for a in top_articles], all_scores
