'use client'

import { useEffect, useState } from 'react'
import { TrendingUp, Home, Award, DollarSign, Activity, MapPin, Star, Maximize2 } from 'lucide-react'
import axios from 'axios'

interface Statistics {
  price: {
    mean: number
    median: number
    min: number
    max: number
  }
  total_properties_filtered: number
  total_properties_available: number
  price_per_sqft: {
    mean: number
  }
}

export default function Dashboard() {
  const [statistics, setStatistics] = useState<Statistics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const response = await axios.get('http://localhost:8003/api/market/statistics')
      setStatistics(response.data)
    } catch (error) {
      console.error('Error fetching data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  const statsCards = [
    {
      title: 'Average Price',
      value: `$${statistics?.price?.mean?.toLocaleString() || '0'}`,
      icon: DollarSign,
      color: 'text-green-600',
      bg: 'bg-green-50'
    },
    {
      title: 'Median Price',
      value: `$${statistics?.price?.median?.toLocaleString() || '0'}`,
      icon: TrendingUp,
      color: 'text-blue-600',
      bg: 'bg-blue-50'
    },
    {
      title: 'Price Range',
      value: `$${statistics?.price?.min?.toLocaleString()} - $${statistics?.price?.max?.toLocaleString()}`,
      icon: Activity,
      color: 'text-purple-600',
      bg: 'bg-purple-50'
    },
    {
      title: 'Total Properties',
      value: statistics?.total_properties_available || 0,
      icon: Award,
      color: 'text-orange-600',
      bg: 'bg-orange-50'
    },
    {
      title: 'Avg Price/Sq Ft',
      value: `$${statistics?.price_per_sqft?.mean?.toFixed(2) || '0'}`,
      icon: Maximize2,
      color: 'text-pink-600',
      bg: 'bg-pink-50'
    },
  ]

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Welcome to PropertyPortal</h1>
        <p className="text-gray-600 mt-2">Your comprehensive real estate analysis platform</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
        {statsCards.map((stat, index) => (
          <div key={index} className="card hover:shadow-lg transition-shadow duration-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">{stat.title}</p>
                <p className="text-xl font-bold mt-2">{stat.value}</p>
              </div>
              <div className={`${stat.bg} p-3 rounded-full`}>
                <stat.icon className={`h-6 w-6 ${stat.color}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Home className="h-5 w-5 text-blue-600" />
            Quick Start
          </h2>
          <div className="space-y-4">
            <div className="p-4 bg-blue-50 rounded-lg">
              <h3 className="font-medium text-blue-900">Property Value Estimator</h3>
              <p className="text-sm text-blue-700 mt-1">
                Get instant property price predictions using our ML model
              </p>
              <a href="/estimator" className="inline-block mt-3 text-sm font-medium text-blue-600 hover:text-blue-700">
                Try it now →
              </a>
            </div>
            <div className="p-4 bg-green-50 rounded-lg">
              <h3 className="font-medium text-green-900">Market Analysis</h3>
              <p className="text-sm text-green-700 mt-1">
                Explore market trends, correlations, and what-if scenarios
              </p>
              <a href="/market-analysis" className="inline-block mt-3 text-sm font-medium text-green-600 hover:text-green-700">
                Explore insights →
              </a>
            </div>
          </div>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <MapPin className="h-5 w-5 text-purple-600" />
            Key Features
          </h2>
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <div className="w-2 h-2 bg-blue-600 rounded-full mt-2"></div>
              <div>
                <p className="font-medium">AI-Powered Predictions</p>
                <p className="text-sm text-gray-600">Machine learning model trained on real estate data</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-2 h-2 bg-green-600 rounded-full mt-2"></div>
              <div>
                <p className="font-medium">Market Analysis</p>
                <p className="text-sm text-gray-600">Comprehensive statistics and trend analysis</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-2 h-2 bg-purple-600 rounded-full mt-2"></div>
              <div>
                <p className="font-medium">What-If Scenarios</p>
                <p className="text-sm text-gray-600">Analyze how different features affect property values</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-2 h-2 bg-orange-600 rounded-full mt-2"></div>
              <div>
                <p className="font-medium">Data Export</p>
                <p className="text-sm text-gray-600">Export analysis results in CSV and PDF formats</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Star className="h-5 w-5 text-yellow-600" />
          How It Works
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-blue-600 font-bold text-xl">1</span>
            </div>
            <h3 className="font-medium">Enter Property Details</h3>
            <p className="text-sm text-gray-600 mt-1">Fill in property features like size, bedrooms, location</p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-green-600 font-bold text-xl">2</span>
            </div>
            <h3 className="font-medium">Get AI Prediction</h3>
            <p className="text-sm text-gray-600 mt-1">Our ML model predicts the property value instantly</p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-purple-600 font-bold text-xl">3</span>
            </div>
            <h3 className="font-medium">Analyze & Compare</h3>
            <p className="text-sm text-gray-600 mt-1">View market insights and compare different scenarios</p>
          </div>
        </div>
      </div>
    </div>
  )
}