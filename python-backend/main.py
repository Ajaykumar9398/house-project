from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, ValidationInfo
from typing import List, Dict, Any, Optional
import httpx
from datetime import datetime
from collections import deque
import asyncio
import json

app = FastAPI(title="Property Value Estimator API", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
ML_MODEL_URL = "http://localhost:8001"
estimate_history = deque(maxlen=100)
validation_rules: Optional[Dict] = None
cache_timestamp: Optional[datetime] = None


async def fetch_validation_rules():
    """Fetch validation rules from ML model"""
    global validation_rules, cache_timestamp
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ML_MODEL_URL}/validation-rules")
            if response.status_code == 200:
                validation_rules = response.json()
                cache_timestamp = datetime.now()
                print("✅ Validation rules fetched successfully")
                return True
            else:
                print(f"⚠️ Failed to fetch validation rules: {response.status_code}")
                return False
    except Exception as e:
        print(f"⚠️ Could not fetch validation rules: {e}")
        return False


def generate_warnings(property_data: Dict, rules: Optional[Dict]):
    warnings = []

    if not rules:
        return warnings

    feature_ranges = rules.get("feature_ranges", {})

    for field, value in property_data.items():
        if field in feature_ranges:
            ranges = feature_ranges[field]

            min_val = ranges.get("min")
            max_val = ranges.get("max")

            if min_val is not None and max_val is not None:
                if value < min_val or value > max_val:
                    warnings.append({
                        "field": field,
                        "message": f"{field.replace('_', ' ').title()} outside recommended range ({min_val} - {max_val})"
                    })

    return warnings

async def refresh_rules_periodically():
    """Refresh validation rules every hour"""
    while True:
        await asyncio.sleep(3600)
        await fetch_validation_rules()


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    await fetch_validation_rules()
    asyncio.create_task(refresh_rules_periodically())


class PropertyFeatures(BaseModel):
    square_footage: float
    bedrooms: int
    bathrooms: float
    year_built: int
    lot_size: float
    distance_to_city_center: float
    school_rating: float

    @field_validator("square_footage", "bedrooms", "bathrooms", "year_built",
                     "lot_size", "distance_to_city_center", "school_rating")
    @classmethod
    def validate_against_rules(cls, v: float, info: ValidationInfo) -> float:
        # ✅ Only block truly invalid values
        if isinstance(v, (int, float)) and v < 0:
            raise ValueError(f"{info.field_name} cannot be negative")

        return v


class EstimateRequest(BaseModel):
    properties: List[PropertyFeatures]


class EstimateResponse(BaseModel):
    estimates: List[Dict[str, Any]]
    timestamp: str
    model_info: Dict[str, Any]


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "estimator-api",
        "rules_loaded": validation_rules is not None,
        "cache_age": (datetime.now() - cache_timestamp).seconds if cache_timestamp else None
    }


@app.get("/api/validation-rules")
async def get_validation_rules():
    """Get current validation rules"""
    if validation_rules is None:
        success = await fetch_validation_rules()
        if not success:
            raise HTTPException(status_code=503, detail="Validation rules not available")

    return validation_rules


@app.post("/api/refresh-rules")
async def refresh_rules():
    """Manually refresh validation rules"""
    success = await fetch_validation_rules()
    if success:
        return {"message": "Rules refreshed successfully", "rules": validation_rules}
    else:
        raise HTTPException(status_code=503, detail="Could not refresh rules")


@app.post("/api/estimates", response_model=EstimateResponse)
async def create_estimates(request: EstimateRequest, background_tasks: BackgroundTasks):
    if not request.properties:
        raise HTTPException(status_code=400, detail="No properties provided")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:

            # 🔹 CALL ML PREDICT
            response = await client.post(
                f"{ML_MODEL_URL}/predict",
                json={"features": [p.model_dump() for p in request.properties]}
            )

            if response.status_code != 200:
                error_data = response.json()
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_data.get("detail", "Prediction failed")
                )

            ml_response = response.json()

            # ✅ FIX: MOVE THIS INSIDE SAME CLIENT BLOCK
            model_info_response = await client.get(f"{ML_MODEL_URL}/model-info")
            model_info = (
                model_info_response.json()
                if model_info_response.status_code == 200 else {}
            )

        # ⬇️ OUTSIDE CLIENT (SAFE NOW)

        estimates = []
        for prop, pred in zip(request.properties, ml_response["predictions"]):
            prop_dict = prop.model_dump()

            warnings = generate_warnings(prop_dict, validation_rules)

            estimate = {
                "property": prop_dict,
                "predicted_price": round(pred, 2),
                "formatted_price": f"${pred:,.2f}",
                "prediction_timestamp": ml_response.get("timestamp"),
                "confidence_score": calculate_confidence(prop, validation_rules),
                "warnings": warnings  # ✅ NEW
            }
            estimates.append(estimate)

            background_tasks.add_task(
                add_to_history,
                prop.model_dump(),
                pred,
                ml_response.get("timestamp")
            )

        return EstimateResponse(
            estimates=estimates,
            timestamp=datetime.now().isoformat(),
            model_info={
                "type": model_info.get("model_type", "Unknown"),
                "metrics": model_info.get("metrics", {}),
                "training_date": model_info.get("training_date")
            }
        )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ML service timeout")

    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"ML model unavailable: {str(e)}")

    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=400, detail=str(e))


def calculate_confidence(property: PropertyFeatures, rules: Optional[Dict]) -> float:
    """Calculate confidence score based on how well property fits training data"""
    if not rules:
        return 0.85  # Default confidence

    confidence = 1.0
    feature_ranges = rules.get('feature_ranges', {})

    for field, value in property.model_dump().items():
        if field in feature_ranges:
            ranges = feature_ranges[field]
            suggested_min = ranges.get('suggested_min', 0)
            suggested_max = ranges.get('suggested_max', 0)

            # Reduce confidence if value is outside suggested range
            if value < suggested_min or value > suggested_max:
                confidence *= 0.9
            elif value < ranges.get('min', 0) or value > ranges.get('max', 0):
                confidence *= 0.7

    return round(confidence, 2)


async def add_to_history(property_data: Dict, prediction: float, timestamp: str):
    """Add prediction to history"""
    estimate_history.appendleft({
        "id": str(datetime.now().timestamp()),
        "property": property_data,
        "prediction": prediction,
        "formatted_price": f"${prediction:,.2f}",
        "timestamp": timestamp
    })


@app.get("/api/history")
async def get_history(limit: int = 20):
    """Get prediction history"""
    return list(estimate_history)[:limit]


@app.delete("/api/history")
async def clear_history():
    """Clear prediction history"""
    estimate_history.clear()
    return {"message": "History cleared", "count": 0}


@app.get("/api/stats")
async def get_stats():
    """Get statistics about predictions"""
    if not estimate_history:
        return {"message": "No predictions yet"}

    predictions = [h["prediction"] for h in estimate_history]
    return {
        "total_predictions": len(estimate_history),
        "average_price": sum(predictions) / len(predictions),
        "min_price": min(predictions),
        "max_price": max(predictions),
        "last_prediction": estimate_history[0] if estimate_history else None
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)