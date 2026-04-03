from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
from scipy import stats
import httpx
from datetime import datetime
from io import BytesIO, StringIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import csv
import os

app = FastAPI(title="Property Market Analysis API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ML_MODEL_URL = "http://localhost:8001"
csv_path = "D:\\house-project\\data\\House Price Dataset.csv"

# Load dataset
if os.path.exists(csv_path):
    df = pd.read_csv(csv_path)
    TOTAL_PROPERTIES = len(df)
    print("DF SHAPE:", df.shape)
    print("HEAD:", df.head())
    print("COLUMNS:", df.columns.tolist())
    print(f"✅ Loaded {TOTAL_PROPERTIES} properties from {csv_path}")
    print(f"📊 Available bedroom counts: {sorted(df['bedrooms'].unique())}")
    print(f"💰 Price range: ${df['price'].min():,.2f} - ${df['price'].max():,.2f}")
else:
    raise FileNotFoundError(
        f"CSV file not found at {csv_path}. "
        "Please ensure the file exists and the path is correct."
    )


class FilterParams(BaseModel):
    min_bedrooms: Optional[int] = None
    max_bedrooms: Optional[int] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_square_footage: Optional[float] = None
    max_square_footage: Optional[float] = None


class WhatIfRequest(BaseModel):
    feature: str
    base_property: Dict[str, Any]
    min_value: float
    max_value: float
    steps: int = 10


class ComparisonRequest(BaseModel):
    property_ids: List[int]


def apply_filters(df: pd.DataFrame, filters: FilterParams) -> pd.DataFrame:
    filtered_df = df.copy()

    if filters.min_bedrooms is not None:
        filtered_df = filtered_df[filtered_df['bedrooms'] >= filters.min_bedrooms]
    if filters.max_bedrooms is not None:
        filtered_df = filtered_df[filtered_df['bedrooms'] <= filters.max_bedrooms]
    if filters.min_price is not None:
        filtered_df = filtered_df[filtered_df['price'] >= filters.min_price]
    if filters.max_price is not None:
        filtered_df = filtered_df[filtered_df['price'] <= filters.max_price]
    if filters.min_square_footage is not None:
        filtered_df = filtered_df[filtered_df['square_footage'] >= filters.min_square_footage]
    if filters.max_square_footage is not None:
        filtered_df = filtered_df[filtered_df['square_footage'] <= filters.max_square_footage]

    return filtered_df


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "market-analysis-python",
        "data_loaded": True,
        "total_properties": TOTAL_PROPERTIES
    }


@app.get("/api/market/available-filters")
async def get_available_filters():
    """Get available filter ranges from actual data"""
    return {
        "bedrooms": {
            "min": int(df['bedrooms'].min()),
            "max": int(df['bedrooms'].max()),
            "available": sorted(df['bedrooms'].unique().tolist()),
            "distribution": {str(k): int(v) for k, v in df['bedrooms'].value_counts().sort_index().to_dict().items()}
        },
        "price": {
            "min": float(df['price'].min()),
            "max": float(df['price'].max()),
            "mean": float(df['price'].mean()),
            "median": float(df['price'].median())
        },
        "square_footage": {
            "min": float(df['square_footage'].min()),
            "max": float(df['square_footage'].max()),
            "mean": float(df['square_footage'].mean())
        },
        "year_built": {
            "min": int(df['year_built'].min()),
            "max": int(df['year_built'].max())
        },
        "school_rating": {
            "min": float(df['school_rating'].min()),
            "max": float(df['school_rating'].max()),
            "mean": float(df['school_rating'].mean())
        },
        "total_properties": TOTAL_PROPERTIES
    }


@app.get("/api/market/statistics")
async def get_statistics(
        min_bedrooms: Optional[int] = Query(None, description="Minimum number of bedrooms"),
        max_bedrooms: Optional[int] = Query(None, description="Maximum number of bedrooms"),
        min_price: Optional[float] = Query(None, description="Minimum price"),
        max_price: Optional[float] = Query(None, description="Maximum price"),
        min_square_footage: Optional[float] = Query(None, description="Minimum square footage"),
        max_square_footage: Optional[float] = Query(None, description="Maximum square footage")
):
    filters = FilterParams(
        min_bedrooms=min_bedrooms,
        max_bedrooms=max_bedrooms,
        min_price=min_price,
        max_price=max_price,
        min_square_footage=min_square_footage,
        max_square_footage=max_square_footage
    )

    filtered_df = apply_filters(df, filters)

    if len(filtered_df) == 0:
        available_bedrooms = sorted(df['bedrooms'].unique())

        error_detail = {
            "error": "NO_DATA_FOUND",
            "message": f"No properties match the specified filters",
            "filters_applied": {
                "min_bedrooms": min_bedrooms,
                "max_bedrooms": max_bedrooms,
                "min_price": min_price,
                "max_price": max_price,
                "min_square_footage": min_square_footage,
                "max_square_footage": max_square_footage
            },
            "available_data_range": {
                "bedrooms": {
                    "min": int(df['bedrooms'].min()),
                    "max": int(df['bedrooms'].max()),
                    "available": available_bedrooms
                },
                "price": {
                    "min": float(df['price'].min()),
                    "max": float(df['price'].max())
                }
            },
            "suggestions": []
        }

        if min_bedrooms is not None and min_bedrooms > df['bedrooms'].max():
            error_detail["suggestions"].append(
                f"min_bedrooms={min_bedrooms} is too high. Maximum available bedrooms is {int(df['bedrooms'].max())}. "
                f"Try min_bedrooms <= {int(df['bedrooms'].max())}"
            )
        elif min_bedrooms is not None and min_bedrooms < df['bedrooms'].min():
            error_detail["suggestions"].append(
                f"min_bedrooms={min_bedrooms} is too low. Minimum available bedrooms is {int(df['bedrooms'].min())}"
            )

        if max_bedrooms is not None and max_bedrooms < df['bedrooms'].min():
            error_detail["suggestions"].append(
                f"max_bedrooms={max_bedrooms} is too low. Minimum available bedrooms is {int(df['bedrooms'].min())}"
            )

        if min_price is not None and min_price > df['price'].max():
            error_detail["suggestions"].append(
                f"min_price=${min_price:,.0f} is too high. Maximum available price is ${df['price'].max():,.0f}"
            )

        if max_price is not None and max_price < df['price'].min():
            error_detail["suggestions"].append(
                f"max_price=${max_price:,.0f} is too low. Minimum available price is ${df['price'].min():,.0f}"
            )

        error_detail["suggestions"].append(
            f"Try one of these bedroom counts: {available_bedrooms}"
        )

        raise HTTPException(status_code=404, detail=error_detail)

    statistics = {
        "price": {
            "mean": float(filtered_df['price'].mean()),
            "median": float(filtered_df['price'].median()),
            "std": float(filtered_df['price'].std()),
            "min": float(filtered_df['price'].min()),
            "max": float(filtered_df['price'].max()),
            "q1": float(filtered_df['price'].quantile(0.25)),
            "q3": float(filtered_df['price'].quantile(0.75)),
            "iqr": float(filtered_df['price'].quantile(0.75) - filtered_df['price'].quantile(0.25))
        },
        "square_footage": {
            "mean": float(filtered_df['square_footage'].mean()),
            "min": float(filtered_df['square_footage'].min()),
            "max": float(filtered_df['square_footage'].max())
        },
        "avg_price_by_bedrooms": {str(k): float(v) for k, v in
                                  filtered_df.groupby('bedrooms')['price'].mean().to_dict().items()},
        "total_properties_filtered": len(filtered_df),
        "total_properties_available": TOTAL_PROPERTIES,
        "price_per_sqft": {
            "mean": float((filtered_df['price'] / filtered_df['square_footage']).mean()),
            "min": float((filtered_df['price'] / filtered_df['square_footage']).min()),
            "max": float((filtered_df['price'] / filtered_df['square_footage']).max())
        },
        "filters_applied": {
            "min_bedrooms": min_bedrooms,
            "max_bedrooms": max_bedrooms,
            "min_price": min_price,
            "max_price": max_price
        }
    }

    return statistics


@app.get("/api/market/correlations")
async def get_correlations():
    features = ['square_footage', 'bedrooms', 'bathrooms', 'year_built', 'lot_size', 'distance_to_city_center',
                'school_rating']
    correlations = {}
    p_values = {}

    for feature in features:
        correlation = df[feature].corr(df['price'])
        correlations[feature] = float(correlation)
        _, p_value = stats.pearsonr(df[feature], df['price'])
        p_values[feature] = float(p_value)

    return {
        "correlations": correlations,
        "p_values": p_values,
        "top_features": sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
    }


@app.post("/api/market/what-if")
async def what_if_analysis(request: WhatIfRequest):
    try:
        values = np.linspace(request.min_value, request.max_value, request.steps).tolist()
        scenarios = []

        async with httpx.AsyncClient() as client:
            for value in values:
                property_data = request.base_property.copy()
                property_data[request.feature] = value

                feature_data = {
                    "square_footage": float(property_data.get("square_footage", 0)),
                    "bedrooms": int(property_data.get("bedrooms", 1)),
                    "bathrooms": float(property_data.get("bathrooms", 1)),
                    "year_built": int(property_data.get("year_built", 2000)),
                    "lot_size": float(property_data.get("lot_size", 5000)),
                    "distance_to_city_center": float(property_data.get("distance_to_city_center", 5)),
                    "school_rating": float(property_data.get("school_rating", 5))
                }

                response = await client.post(
                    f"{ML_MODEL_URL}/predict",
                    json={"features": [feature_data]}
                )
                response.raise_for_status()
                prediction = response.json()['predictions'][0]

                scenarios.append({
                    "value": float(value),
                    "predicted_price": float(prediction)
                })

        return {
            "feature": request.feature,
            "scenarios": scenarios,
            "analysis": {
                "price_range": f"${min(s['predicted_price'] for s in scenarios):,.0f} - ${max(s['predicted_price'] for s in scenarios):,.0f}",
                "sensitivity": float((scenarios[-1]['predicted_price'] - scenarios[0]['predicted_price']) / (
                        request.max_value - request.min_value)),
                "optimal_value": float(max(scenarios, key=lambda x: x['predicted_price'])['value'])
            }
        }

    except httpx.HTTPError as e:
        error_detail = f"ML Model error: {str(e)}"
        if e.response:
            error_detail += f" - Response: {e.response.text}"
        raise HTTPException(status_code=400, detail=error_detail)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/market/segments")
async def get_market_segments():
    segments = {
        "by_bedrooms": {},
        "by_price_tier": {},
        "by_location": {}
    }

    for bedrooms in sorted(df['bedrooms'].unique()):
        segment_df = df[df['bedrooms'] == bedrooms]
        segments["by_bedrooms"][str(bedrooms)] = {
            "count": len(segment_df),
            "avg_price": float(segment_df['price'].mean()),
            "avg_sqft": float(segment_df['square_footage'].mean()),
            "avg_school_rating": float(segment_df['school_rating'].mean())
        }

    price_percentiles = df['price'].quantile([0.25, 0.5, 0.75])

    price_tiers = [
        (df['price'].min(), price_percentiles[0.25], "Budget"),
        (price_percentiles[0.25], price_percentiles[0.5], "Mid-Range"),
        (price_percentiles[0.5], price_percentiles[0.75], "Premium"),
        (price_percentiles[0.75], df['price'].max(), "Luxury")
    ]

    for min_price, max_price, tier in price_tiers:
        segment_df = df[(df['price'] >= min_price) & (df['price'] <= max_price)]

        if len(segment_df) > 0:
            segments["by_price_tier"][tier] = {
                "count": len(segment_df),
                "avg_price": float(segment_df['price'].mean()),
                "avg_sqft": float(segment_df['square_footage'].mean()),
                "price_range": f"${min_price:,.0f} - ${max_price:,.0f}"
            }

    distance_percentiles = df['distance_to_city_center'].quantile([0.33, 0.66])

    location_tiers = [
        (df['distance_to_city_center'].min(), distance_percentiles[0.33], "City Center"),
        (distance_percentiles[0.33], distance_percentiles[0.66], "Suburban"),
        (distance_percentiles[0.66], df['distance_to_city_center'].max(), "Rural")
    ]

    for min_dist, max_dist, location in location_tiers:
        segment_df = df[(df['distance_to_city_center'] >= min_dist) & (df['distance_to_city_center'] <= max_dist)]

        if len(segment_df) > 0:
            segments["by_location"][location] = {
                "count": len(segment_df),
                "avg_price": float(segment_df['price'].mean()),
                "avg_sqft": float(segment_df['square_footage'].mean()),
                "avg_distance": float(segment_df['distance_to_city_center'].mean())
            }

    return segments


@app.get("/api/market/trends")
async def get_market_trends():
    trends = {
        "price_by_year": df.groupby('year_built')['price'].mean().sort_index().to_dict(),
        "price_by_school_rating": df.groupby('school_rating')['price'].mean().to_dict(),
        "sqft_by_bedrooms": df.groupby('bedrooms')['square_footage'].mean().to_dict(),
    }

    for key in trends:
        if isinstance(trends[key], dict):
            trends[key] = {str(k): float(v) for k, v in trends[key].items()}

    return trends


@app.get("/api/market/anomalies")
async def detect_anomalies(threshold: float = Query(2.0, ge=1.5, le=3.0)):
    df_copy = df.copy()
    df_copy['price_per_sqft'] = df_copy['price'] / df_copy['square_footage']

    mean_ppsf = df_copy['price_per_sqft'].mean()
    std_ppsf = df_copy['price_per_sqft'].std()
    df_copy['z_score'] = (df_copy['price_per_sqft'] - mean_ppsf) / std_ppsf

    anomalies = df_copy[abs(df_copy['z_score']) > threshold]

    result = {
        "anomalies": [
            {
                "id": int(row['id']),
                "price": float(row['price']),
                "square_footage": float(row['square_footage']),
                "price_per_sqft": float(row['price_per_sqft']),
                "z_score": float(row['z_score']),
                "reason": "Overpriced" if row['z_score'] > threshold else "Underpriced"
            }
            for _, row in anomalies.iterrows()
        ],
        "total_anomalies": len(anomalies),
        "threshold_used": threshold
    }

    return result


@app.get("/api/market/export/csv")
async def export_csv(
        min_bedrooms: Optional[int] = Query(None),
        max_bedrooms: Optional[int] = Query(None),
        min_price: Optional[float] = Query(None),
        max_price: Optional[float] = Query(None)
):
    filters = FilterParams(
        min_bedrooms=min_bedrooms,
        max_bedrooms=max_bedrooms,
        min_price=min_price,
        max_price=max_price
    )

    filtered_df = apply_filters(df, filters)

    if len(filtered_df) == 0:
        raise HTTPException(status_code=404, detail="No properties match the filters")

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(filtered_df.columns.tolist())
    writer.writerows(filtered_df.values.tolist())

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=market_data.csv"}
    )


@app.get("/api/market/export/pdf")
async def export_pdf(
        min_bedrooms: Optional[int] = Query(None),
        max_bedrooms: Optional[int] = Query(None),
        min_price: Optional[float] = Query(None),
        max_price: Optional[float] = Query(None)
):
    """Export market data as PDF report"""
    filters = FilterParams(
        min_bedrooms=min_bedrooms,
        max_bedrooms=max_bedrooms,
        min_price=min_price,
        max_price=max_price
    )

    filtered_df = apply_filters(df, filters)

    if len(filtered_df) == 0:
        raise HTTPException(status_code=404, detail="No properties match the filters")

    # Create PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title="Market Analysis Report")
    styles = getSampleStyleSheet()

    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=12
    )

    story = []

    # Title
    story.append(Paragraph("Market Analysis Report", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 20))

    # Summary Statistics
    story.append(Paragraph("Summary Statistics", heading_style))

    stats_data = [
        ["Metric", "Value"],
        ["Total Properties", str(len(filtered_df))],
        ["Average Price", f"${filtered_df['price'].mean():,.2f}"],
        ["Median Price", f"${filtered_df['price'].median():,.2f}"],
        ["Price Std Dev", f"${filtered_df['price'].std():,.2f}"],
        ["Min Price", f"${filtered_df['price'].min():,.2f}"],
        ["Max Price", f"${filtered_df['price'].max():,.2f}"],
        ["Avg Price per Sq Ft", f"${(filtered_df['price'] / filtered_df['square_footage']).mean():.2f}"],
        ["Avg Square Footage", f"{filtered_df['square_footage'].mean():.0f} sq ft"],
        ["Avg School Rating", f"{filtered_df['school_rating'].mean():.1f}/10"]
    ]

    stats_table = Table(stats_data, colWidths=[200, 150])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    story.append(stats_table)
    story.append(Spacer(1, 20))

    # Price by Bedrooms
    story.append(Paragraph("Average Price by Bedrooms", heading_style))

    bedroom_data = [["Bedrooms", "Average Price", "Count"]]
    for bedrooms in sorted(filtered_df['bedrooms'].unique()):
        subset = filtered_df[filtered_df['bedrooms'] == bedrooms]
        bedroom_data.append([
            str(bedrooms),
            f"${subset['price'].mean():,.2f}",
            str(len(subset))
        ])

    bedroom_table = Table(bedroom_data, colWidths=[100, 150, 100])
    bedroom_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    story.append(bedroom_table)
    story.append(Spacer(1, 20))

    # Price Tiers
    story.append(Paragraph("Price Tier Distribution", heading_style))

    price_tiers_data = [["Tier", "Price Range", "Count", "Avg Price"]]

    price_percentiles = filtered_df['price'].quantile([0.25, 0.5, 0.75])
    tiers = [
        ("Budget", filtered_df['price'].min(), price_percentiles[0.25]),
        ("Mid-Range", price_percentiles[0.25], price_percentiles[0.5]),
        ("Premium", price_percentiles[0.5], price_percentiles[0.75]),
        ("Luxury", price_percentiles[0.75], filtered_df['price'].max())
    ]

    for tier_name, min_price, max_price in tiers:
        tier_df = filtered_df[(filtered_df['price'] >= min_price) & (filtered_df['price'] <= max_price)]
        if len(tier_df) > 0:
            price_tiers_data.append([
                tier_name,
                f"${min_price:,.0f} - ${max_price:,.0f}",
                str(len(tier_df)),
                f"${tier_df['price'].mean():,.2f}"
            ])

    tier_table = Table(price_tiers_data, colWidths=[80, 130, 80, 130])
    tier_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f59e0b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    story.append(tier_table)
    story.append(Spacer(1, 20))

    # Top Correlations
    story.append(Paragraph("Top Feature Correlations with Price", heading_style))

    corr_data = [["Feature", "Correlation"]]
    features = ['square_footage', 'bedrooms', 'bathrooms', 'school_rating', 'year_built']
    for feature in features:
        correlation = filtered_df[feature].corr(filtered_df['price'])
        corr_data.append([feature.replace('_', ' ').title(), f"{correlation:.3f}"])

    corr_table = Table(corr_data, colWidths=[200, 150])
    corr_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    story.append(corr_table)

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=market_analysis_report.pdf"}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)