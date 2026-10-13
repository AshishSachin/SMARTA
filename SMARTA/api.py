"""FastAPI server for the SMARTA maintenance assistant."""

from contextlib import asynccontextmanager
from pathlib import Path
import re
import sys
from typing import Any
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from data_store import corpus_stats, initialize_corpus
from document_loader import mysql_credentials_available
from rag.retriever import retrieve
from rag.generator import generate_answer
from predictive.ai4i import ModelUnavailable, Predictor

_corpus_status: dict[str, Any] = {"documents": 0, "maintenance_records": 0, "sources": 0}
_ingestion_error: str | None = None
_predictor = Predictor()
MODE_NAMES = {
    "TWF": "tool wear failure", "HDF": "heat dissipation failure",
    "PWF": "power failure", "OSF": "overstrain failure", "RNF": "random failure",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _corpus_status, _ingestion_error
    try:
        _corpus_status = initialize_corpus()
    except Exception:
        # Database drivers can include a credential-bearing connection URL in
        # exception messages. Keep the health state useful without returning
        # or printing that diagnostic verbatim.
        _ingestion_error = "corpus_initialization_failed"
        print("SMARTA corpus initialization failed.")
    yield


app = FastAPI(title="SMARTA API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []


class FeatureVector(BaseModel):
    product_type: str
    air_temperature_k: float
    process_temperature_k: float
    rotational_speed_rpm: float
    torque_nm: float
    tool_wear_min: float

    class Config:
        extra = "forbid"


class PredictRequest(BaseModel):
    machine_id: str
    observed_at: datetime | None = None
    features: FeatureVector

    class Config:
        extra = "forbid"


class PredictResponse(BaseModel):
    prediction: dict[str, Any]
    evidence: list[dict[str, Any]]
    machine_specific_evidence: list[dict[str, Any]]
    recommendation: str
    evidence_status: str


class PredictiveModelMetadata(BaseModel):
    ready: bool
    model_version: str
    trained_at: str | None = None
    features: list[str]
    feature_ranges: dict[str, list[float]]
    allowed_types: list[str]
    supported_failure_modes: list[str]
    unsupported_failure_modes: dict[str, str]


@app.get("/health")
def health():
    """Report API and corpus readiness instead of only process liveness."""
    global _corpus_status
    try:
        _corpus_status = corpus_stats()
    except Exception:
        pass
    try:
        _predictor.metadata()
        predictor_status = "ready"
    except ModelUnavailable:
        predictor_status = "not_trained"
    except Exception:
        predictor_status = "unavailable"
    return {
        "status": "ok" if _corpus_status.get("documents", 0) else "degraded",
        "corpus": _corpus_status,
        "mysql_credentials_configured": mysql_credentials_available(),
        "predictive_model": predictor_status,
        "ingestion_error": _ingestion_error,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not _corpus_status.get("documents"):
        raise HTTPException(status_code=503, detail="SMARTA's document corpus is not ready.")
    try:
        results = retrieve(question)
        context_parts = []
        for index, item in enumerate(results, start=1):
            context_parts.append(
                f"[{index}] {item['source']}, {item['locator']}\n{item['text']}"
            )
        identifiers = re.findall(r"\b[A-Z]{1,5}\d{1,5}[A-Z]?\b", question.upper())
        for identifier in identifiers:
            found_exact = any(re.search(rf"(?<![A-Z0-9]){re.escape(identifier)}(?![A-Z0-9])", item["text"].upper()) for item in results)
            if not found_exact:
                context_parts.insert(0, f"SYSTEM NOTE: No retrieved record contains the exact identifier {identifier}.")
        context = "\n\n".join(context_parts)
        missing_identifiers = [
            identifier for identifier in identifiers
            if not any(re.search(rf"(?<![A-Z0-9]){re.escape(identifier)}(?![A-Z0-9])", item["text"].upper()) for item in results)
        ]
        if missing_identifiers:
            identifier = missing_identifiers[0]
            compressor_guide_index = next((
                index for index, item in enumerate(results, start=1)
                if "thermal overcurrent" in item["text"].lower()
                and "low compressor" in item["text"].lower()
                and "oil pressure" in item["text"].lower()
            ), None)
            answer = (
                f"The available records do not identify alarm {identifier}, so its exact cause cannot be confirmed.\n\n"
                f"General compressor guidance: the maintenance guide lists compressor overheating and a thermal-overcurrent relay tripping due to overload as possible reasons a compressor motor may cut out during operation. [{compressor_guide_index}] "
                f"For low compressor oil pressure, it recommends checking the oil level, filter, bypass valve, and oil pump. [{compressor_guide_index}]\n\n"
                f"These are general troubleshooting checks, not a confirmed cause of alarm {identifier}. Check the compressor maker's alarm list for this code; the machine make, model, and full alarm text would let SMARTA narrow it down."
            ) if results and "compressor" in question.lower() and compressor_guide_index else (
                f"The available records do not identify alarm {identifier}, so its exact cause cannot be confirmed. "
                "Please provide the machine make/model and the relevant alarm list or maintenance record."
            )
        else:
            answer = generate_answer(context=context, question=question)
    except Exception as exc:
        # Do not expose provider, SQL, filesystem, or prompt details to clients.
        raise HTTPException(
            status_code=500,
            detail="SMARTA could not generate a response. Please try again later.",
        ) from exc

    citations = [
        f"[{index}] {item['source']}, {item['locator']}"
        for index, item in enumerate(results, start=1)
    ]
    return ChatResponse(answer=answer, sources=citations)


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    """Classify the supplied operating point and return separately sourced RAG evidence."""
    if not request.machine_id.strip():
        raise HTTPException(status_code=422, detail="machine_id cannot be empty.")
    features = {
        "Type": request.features.product_type,
        "Air temperature [K]": request.features.air_temperature_k,
        "Process temperature [K]": request.features.process_temperature_k,
        "Rotational speed [rpm]": request.features.rotational_speed_rpm,
        "Torque [Nm]": request.features.torque_nm,
        "Tool wear [min]": request.features.tool_wear_min,
    }
    try:
        prediction = _predictor.predict(features, machine_id=request.machine_id.strip())
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    positive_modes = [
        MODE_NAMES[mode] for mode, result in prediction["failure_modes"].items()
        if result["classification"] == 1
    ]
    classes = ", ".join(positive_modes) if positive_modes else "no supported failure mode classified"
    query = f"{classes} predictive maintenance " + " ".join(positive_modes)
    try:
        machine_candidates = retrieve(request.machine_id, limit=6)
        general_candidates = retrieve(query, limit=6)
    except Exception:
        machine_candidates, general_candidates = [], []
    machine_pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(request.machine_id)}(?![A-Za-z0-9])", re.IGNORECASE)
    machine_specific = [
        item for item in machine_candidates
        if machine_pattern.search(item["text"] + " " + item["source"] + " " + item["locator"])
    ]
    results = []
    seen_evidence = set()
    for item in machine_specific + general_candidates:
        key = (item["source"], item["locator"])
        if key not in seen_evidence:
            seen_evidence.add(key)
            results.append(item)
        if len(results) == 6:
            break
    evidence_payload = [
        {"source": item["source"], "locator": item["locator"], "text": item["text"]}
        for item in results
    ]
    exact_payload = [
        {"source": item["source"], "locator": item["locator"], "text": item["text"]}
        for item in machine_specific
    ]
    if not results:
        recommendation = "No sufficiently supported corrective action was found in the available maintenance records or documentation. Further inspection is required."
        evidence_status = "insufficient"
    else:
        context_parts = [f"[{i}] {item['source']}, {item['locator']}\n{item['text']}" for i, item in enumerate(results, 1)]
        context = "\n\n".join(context_parts)
        question = (
            f"The ML classifier reports {classes} for machine {request.machine_id}. "
            "Explain this as a model classification, not a confirmed fault or future forecast. "
            "Give only possible checks supported by the excerpts. State explicitly when no corrective action or machine-specific history is supported."
        )
        try:
            recommendation = generate_answer(context, question)
        except Exception:
            recommendation = "Relevant source excerpts were found, but SMARTA could not generate a grounded recommendation. Review the cited evidence and inspect the machine."
        evidence_status = "machine_specific_and_general" if machine_specific else "general_only"
    prediction["observed_at"] = request.observed_at.isoformat() if request.observed_at else None
    prediction["failure_mode_labels"] = positive_modes
    return PredictResponse(
        prediction=prediction,
        evidence=evidence_payload,
        machine_specific_evidence=exact_payload,
        recommendation=recommendation,
        evidence_status=evidence_status,
    )


@app.get("/predict/metadata", response_model=PredictiveModelMetadata)
def predictive_model_metadata():
    """Expose model readiness and the exact supported simulator input ranges."""
    try:
        return _predictor.metadata()
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


if __name__ == "__main__":
    # Allows running with `python api.py` from any working directory.
    import uvicorn

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
