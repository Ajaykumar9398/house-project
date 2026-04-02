from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Union, Dict, Any
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from datetime import datetime
import os
import json

app = FastAPI(title="Housing Price Prediction ML API", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Data models
class HouseFeatures(BaseModel):
    square_footage: float = Field(..., gt=0)
    bedrooms: int = Field(..., ge=1)
    bathrooms: float = Field(..., ge=0.5)
    year_built: int = Field(..., ge=1800)
    lot_size: float = Field(..., gt=0)
    distance_to_city_center: float = Field(..., ge=0)
    school_rating: float = Field(..., ge=0, le=10)


class PredictionRequest(BaseModel):
    features: Union[HouseFeatures, List[HouseFeatures]]


class PredictionResponse(BaseModel):
    predictions: List[float]
    count: int
    timestamp: str
    model_version: str


class ModelInfoResponse(BaseModel):
    model_type: str
    coefficients: dict = None
    feature_importance: dict = None
    intercept: float = None
    metrics: dict
    feature_names: List[str]
    training_date: str
    data_statistics: dict


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_type: str
    timestamp: str


def get_data_statistics(df: pd.DataFrame, feature_columns: List[str]) -> Dict[str, Any]:
    """Calculate comprehensive statistics from training data"""
    statistics = {}

    for col in feature_columns:
        statistics[col] = {
            'min': float(df[col].min()),
            'max': float(df[col].max()),
            'mean': float(df[col].mean()),
            'median': float(df[col].median()),
            'q1': float(df[col].quantile(0.25)),
            'q3': float(df[col].quantile(0.75)),
            'std': float(df[col].std()),
            'unique_values': int(df[col].nunique())
        }

    # Add target statistics
    statistics['price'] = {
        'min': float(df['price'].min()),
        'max': float(df['price'].max()),
        'mean': float(df['price'].mean()),
        'median': float(df['price'].median()),
        'std': float(df['price'].std())
    }

    # Calculate valid ranges with padding
    statistics['valid_ranges'] = {}
    for col in feature_columns:
        min_val = df[col].min()
        max_val = df[col].max()
        padding = (max_val - min_val) * 0.1

        # Determine step value
        if col == 'bedrooms':
            step = 1.0
        elif col == 'bathrooms':
            unique_baths = sorted(df[col].unique())
            if len(unique_baths) > 1:
                step = float(min(np.diff(unique_baths)))
            else:
                step = 0.5
        elif col == 'year_built':
            step = 1.0
        elif col == 'school_rating':
            step = 0.5
        else:
            range_val = max_val - min_val
            if range_val > 1000:
                step = 100.0
            elif range_val > 100:
                step = 10.0
            elif range_val > 10:
                step = 1.0
            else:
                step = 0.5

        statistics['valid_ranges'][col] = {
            'min': float(max(0, min_val - padding)),
            'max': float(max_val + padding),
            'suggested_min': float(min_val),
            'suggested_max': float(max_val),
            'suggested_median': float(df[col].median()),
            'step': step,
            'unit': get_unit(col)
        }

    return statistics


def get_unit(column: str) -> str:
    """Get unit for feature"""
    units = {
        'square_footage': 'sq ft',
        'bedrooms': 'rooms',
        'bathrooms': 'rooms',
        'year_built': 'year',
        'lot_size': 'sq ft',
        'distance_to_city_center': 'miles',
        'school_rating': '/10'
    }
    return units.get(column, '')


def train_model():
    """Train machine learning model"""
    csv_path = "D:\\house-project\\data\\House Price Dataset.csv"

    if not os.path.exists(csv_path):
        # Generate sample data if CSV doesn't exist
        np.random.seed(42)
        n_samples = 1000

        data = {
            'square_footage': np.random.normal(2000, 500, n_samples),
            'bedrooms': np.random.randint(1, 6, n_samples),
            'bathrooms': np.random.choice([1, 1.5, 2, 2.5, 3, 3.5, 4], n_samples),
            'year_built': np.random.randint(1950, 2024, n_samples),
            'lot_size': np.random.normal(8000, 2000, n_samples),
            'distance_to_city_center': np.random.exponential(5, n_samples),
            'school_rating': np.random.uniform(3, 10, n_samples),
        }

        df = pd.DataFrame(data)

        # Generate realistic prices
        df['price'] = (
                df['square_footage'] * 150 +
                df['bedrooms'] * 15000 +
                df['bathrooms'] * 10000 +
                (df['year_built'] - 2000) * 1000 +
                df['lot_size'] * 2 +
                -df['distance_to_city_center'] * 5000 +
                df['school_rating'] * 15000 +
                np.random.normal(0, 50000, n_samples)
        )

        # Ensure positive prices
        df['price'] = df['price'].clip(lower=50000)

        print("✅ Generated sample dataset with 1000 properties")
    else:
        df = pd.read_csv(csv_path)
        print(f"✅ Loaded {len(df)} properties from {csv_path}")

    feature_columns = ['square_footage', 'bedrooms', 'bathrooms', 'year_built',
                       'lot_size', 'distance_to_city_center', 'school_rating']
    target_column = 'price'

    X = df[feature_columns]
    y = df[target_column]

    # Train both models for comparison
    linear_model = LinearRegression()
    linear_model.fit(X, y)

    rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
    rf_model.fit(X, y)

    # Use Random Forest as primary (better for non-linear relationships)
    model = rf_model
    model_type = "Random Forest Regressor"

    # Calculate metrics
    y_pred = model.predict(X)
    metrics = {
        'r2_score': round(r2_score(y, y_pred), 4),
        'mean_squared_error': round(mean_squared_error(y, y_pred), 2),
        'root_mean_squared_error': round(np.sqrt(mean_squared_error(y, y_pred)), 2),
        'mean_absolute_error': round(mean_absolute_error(y, y_pred), 2),
        'training_samples': len(df),
        'model_type': model_type
    }

    # Get feature importance for Random Forest
    feature_importance = dict(zip(feature_columns, model.feature_importances_.tolist()))

    # Get statistics
    statistics = get_data_statistics(df, feature_columns)

    return model, feature_columns, metrics, feature_importance, statistics, model_type


# Initialize model
model, feature_names, metrics, feature_importance, data_statistics, model_type = train_model()
training_date = datetime.now().isoformat()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        model_loaded=model is not None,
        model_type=model_type,
        timestamp=datetime.now().isoformat()
    )


@app.get("/model-info", response_model=ModelInfoResponse)
async def get_model_info():
    return ModelInfoResponse(
        model_type=model_type,
        feature_importance=feature_importance,
        metrics=metrics,
        feature_names=feature_names,
        training_date=training_date,
        data_statistics=data_statistics
    )


@app.get("/validation-rules")
async def get_validation_rules():
    """Return dynamic validation rules based on training data"""
    return {
        'feature_ranges': data_statistics['valid_ranges'],
        'feature_statistics': {k: v for k, v in data_statistics.items()
                               if k not in ['valid_ranges', 'price']},
        'price_range': data_statistics['price'],
        'training_samples': metrics['training_samples'],
        'last_updated': training_date,
        'model_type': model_type,
        'model_metrics': {k: v for k, v in metrics.items() if k != 'training_samples'}
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    try:
        if isinstance(request.features, HouseFeatures):
            features_list = [request.features]
        else:
            features_list = request.features

        X = []
        for features in features_list:
            X.append([
                features.square_footage,
                features.bedrooms,
                features.bathrooms,
                features.year_built,
                features.lot_size,
                features.distance_to_city_center,
                features.school_rating
            ])

        predictions = model.predict(X).tolist()

        return PredictionResponse(
            predictions=predictions,
            count=len(predictions),
            timestamp=datetime.now().isoformat(),
            model_version=model_type
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid input values: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)