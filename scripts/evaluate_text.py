"""Opt-in real localhost Ollama evaluation; synthetic records, temporary storage only.

Run from repository root: .venv/bin/python -m scripts.evaluate_text --output docs/text-evaluation.json
No model downloads or settings changes. This is text evaluation, never vision evidence.
"""

import argparse
import asyncio
import json
import platform
import statistics
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.config import OLLAMA_URL, TEXT_MODELS, Settings
from app.contracts import ManualCreate, Recall
from app.evidence_store import EvidenceStore
from app.inference.text import TextAdapter
from app.item_repository import ItemRepository
from app.recall_service import RecallService

# Query phrasings are not inserted as aliases or included in prompts.
CASES = [
    ("blue craft scissors", "Where did I put the blue craft scissors?"),
    ("spare water bottle", "Can you find my spare water bottle?"),
    ("red travel mug", "Where is the red travel mug kept?"),
    ("small measuring tape", "Locate the small measuring tape please"),
    ("silver bike lock", "Tell me where my silver bike lock is"),
    ("green garden gloves", "Where are the green garden gloves?"),
    ("yellow utility knife", "Find the yellow utility knife"),
    ("black sewing kit", "Where have I stored my black sewing kit?"),
    ("white spare charger", "Where is my white spare charger?"),
    ("purple paint brush", "Where was the purple paint brush placed?"),
    ("orange extension cable", "Where did I leave the orange extension cable?"),
    ("large soup ladle", "What is the last recorded place for the large soup ladle?"),
    ("blue picnic plate", "Can you tell me where the blue picnic plate is?"),
    ("wooden serving spoon", "Please locate my wooden serving spoon"),
    ("spare blue umbrella", "Where have I kept the spare blue umbrella?"),
    ("small tool pouch", "Find my small tool pouch please"),
    ("metal storage tin", "Where did I store the metal storage tin?"),
    ("red spare flashlight", "Where are my red spare flashlight items?"),
    ("white cooking timer", "Tell me about my white cooking timer's last recorded place"),
    ("green reusable bag", "Where can I find the green reusable bag?"),
]


def p90(values):
    return sorted(values)[max(0, int(len(values) * 0.9) - 1)]


async def evaluate(output: Path) -> None:
    result: dict[str, Any] = {
        "kind": "real local text inference; no vision",
        "python": platform.python_version(),
        "cases": len(CASES),
        "rounds": 3,
        "models": {},
        "synthetic_data": True,
    }
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=2) as client:
        result["runtime_version"] = (await client.get(OLLAMA_URL + "/api/version")).json()
        result["installed_metadata"] = (await client.get(OLLAMA_URL + "/api/tags")).json()
    with tempfile.TemporaryDirectory(prefix="appbuilderhck-text-eval-") as folder:
        settings = Settings(data_dir=Path(folder) / "data")
        store = EvidenceStore(settings)
        try:
            repo = ItemRepository(settings, store)
            ids = {}
            for number, (name, _) in enumerate(CASES):
                create_request = ManualCreate(
                    confirmed=True,
                    idempotency_key=uuid4(),
                    personal_name=name,
                    location=f"Synthetic cabinet {number}",
                )
                ids[name] = repo.create_manual(create_request)["items"][0]["id"]
            for model in (None, *TEXT_MODELS):
                adapter = TextAdapter(replace(settings, text_model=model))
                service = RecallService(repo, adapter)
                rounds: list[int] = []
                timings: list[float] = []
                statuses: dict[str, int] = {}
                metrics = {
                    "attempts": 0,
                    "first_schema_valid": 0,
                    "first_semantic_valid": 0,
                    "repair_schema_valid": 0,
                }
                repairs, used = 0, 0
                for iteration in range(3):
                    successes = 0
                    for name, query in CASES:
                        start = time.monotonic()
                        request = Recall(
                            query=query, request_id=uuid4(), use_inference=model is not None
                        )
                        answer = await service.recall(request, asyncio.Event(), repo.generation())
                        timings.append((time.monotonic() - start) * 1000)
                        status = answer["inference_status"]
                        statuses[status] = statuses.get(status, 0) + 1
                        repairs += int(answer["repair_used"])
                        used += int(answer["inference_used"])
                        for metric in metrics:
                            metrics[metric] += int(adapter.last_metrics[metric])
                        if answer["kind"] == "found" and answer["items"][0]["id"] == ids[name]:
                            successes += 1
                        if answer["items"]:
                            assert (
                                answer["items"][0]["location"]
                                == repo.get(answer["items"][0]["id"])["location"]
                            )
                    rounds.append(successes)
                    print(
                        json.dumps(
                            {
                                "model": model or "deterministic",
                                "round": iteration + 1,
                                "retrieval_successes": successes,
                                "statuses_so_far": statuses,
                            }
                        ),
                        flush=True,
                    )
                    result["models"][model or "deterministic"] = {
                        "retrieval_successes_per_round": rounds.copy(),
                        "statuses": statuses.copy(),
                        "accepted_normalizations": used,
                        "repair_attempted_or_used": repairs,
                        "validation_metrics": metrics.copy(),
                        "first_request_ms": round(timings[0], 2),
                        "median_ms": round(statistics.median(timings), 2),
                        "p90_ms": round(p90(timings), 2),
                        "max_ms": round(max(timings), 2),
                    }
                    output.write_text(json.dumps(result, indent=2) + "\n")
        finally:
            store.close()
    print("Evaluation complete; raw metadata and aggregate metrics saved.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(evaluate(args.output))
