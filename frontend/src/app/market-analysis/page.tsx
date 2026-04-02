'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts'
import { Download, Filter, RefreshCw, Target, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec489a']

interface Statistics {
  price: {
    mean: number
    median: number
    std: number
    min: number
    max: number
    q1: number
    q3: number
  }
  avg_price_by_bedrooms: Record<string, number>

  // ✅ FIXED
  total_properties_filtered: number
  total_properties_available: number

  price_per_sqft: {
    mean: number
    min: number
    max: number
  }
}

interface Correlations {
  correlations: Record<string, number>
  top_features: Array<[string, number]>
}

interface WhatIfScenario {
  value: number
  predicted_price: number
}

interface AvailableFilters {
  bedrooms: {
    min: number
    max: number
    available: number[]
    distribution: Record<string, number>
  }
  price: {
    min: number
    max: number
    mean: number
    median: number
  }
  total_properties: number
}

export default function MarketAnalysisPage() {
  const [statistics, setStatistics] = useState<Statistics | null>(null)
  const [correlations, setCorrelations] = useState<Correlations | null>(null)
  const [segments, setSegments] = useState<any>(null)
  const [whatIfData, setWhatIfData] = useState<WhatIfScenario[]>([])
  const [whatIfFeature, setWhatIfFeature] = useState('square_footage')
  const [filters, setFilters] = useState({
    minBedrooms: '',
    maxBedrooms: '',
    minPrice: '',
    maxPrice: '',
  })
  const [availableFilters, setAvailableFilters] = useState<AvailableFilters | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const [error, setError] = useState<{
    type: string
    message: string
    suggestions?: string[]
    availableData?: any
  } | null>(null)

  // Fetch available filters on component mount
  useEffect(() => {
    fetchAvailableFilters()
  }, [])

  const fetchAvailableFilters = async () => {
    try {
      const response = await axios.get('http://localhost:8003/api/market/available-filters')
      setAvailableFilters(response.data)
    } catch (error) {
      console.error('Error fetching available filters:', error)
    }
  }

  const fetchAllData = async () => {
    setLoading(true)
    setError(null)

    try {
      const params: any = {}
      if (filters.minBedrooms) params.min_bedrooms = parseInt(filters.minBedrooms)
      if (filters.maxBedrooms) params.max_bedrooms = parseInt(filters.maxBedrooms)
      if (filters.minPrice) params.min_price = parseFloat(filters.minPrice)
      if (filters.maxPrice) params.max_price = parseFloat(filters.maxPrice)

      const [statsRes, corrRes, segmentsRes] = await Promise.all([
        axios.get('http://localhost:8003/api/market/statistics', { params }),
        axios.get('http://localhost:8003/api/market/correlations'),
        axios.get('http://localhost:8003/api/market/segments'),
      ])

      setStatistics(statsRes.data)
      setCorrelations(corrRes.data)
      setSegments(segmentsRes.data)
      setError(null)
    } catch (error: any) {
      console.error('Error fetching data:', error)

      if (error.response?.status === 404) {
        // Handle 404 error with detailed message from API
        const errorDetail = error.response.data.detail
        setError({
          type: 'NO_DATA',
          message: errorDetail.message || 'No properties match the selected filters',
          suggestions: errorDetail.suggestions || [],
          availableData: errorDetail.available_data_range || null
        })
        setStatistics(null)
        setSegments(null)
        toast.error('No data found with current filters')
      } else if (error.response?.status === 503) {
        setError({
          type: 'SERVICE_UNAVAILABLE',
          message: 'ML model service is unavailable. Please try again later.'
        })
        toast.error('Service unavailable')
      } else {
        setError({
          type: 'UNKNOWN',
          message: 'Failed to fetch market data. Please try again.'
        })
        toast.error('Failed to fetch market data')
      }
    } finally {
      setLoading(false)
    }
  }

  const runWhatIfAnalysis = async () => {
    try {
      const baseProperty = {
        square_footage: 1800,
        bedrooms: 3,
        bathrooms: 2,
        year_built: 2000,
        lot_size: 7500,
        distance_to_city_center: 5,
        school_rating: 8
      }

      const minMax: Record<string, { min: number; max: number }> = {
        square_footage: { min: 1000, max: 3000 },
        bedrooms: { min: 1, max: 5 },
        school_rating: { min: 5, max: 10 }
      }

      const response = await axios.post('http://localhost:8003/api/market/what-if', {
        feature: whatIfFeature,
        base_property: baseProperty,
        min_value: minMax[whatIfFeature].min,
        max_value: minMax[whatIfFeature].max,
        steps: 15
      })
      setWhatIfData(response.data.scenarios)
    } catch (error) {
      console.error('Error running what-if analysis:', error)
      toast.error('Failed to run what-if analysis')
    }
  }

  useEffect(() => {
    fetchAllData()
  }, [filters])

  useEffect(() => {
    runWhatIfAnalysis()
  }, [whatIfFeature])

  const handleResetFilters = () => {
    setFilters({
      minBedrooms: '',
      maxBedrooms: '',
      minPrice: '',
      maxPrice: '',
    })
  }

  const exportData = async (format: string) => {
    try {
      const params: any = {}
      if (filters.minBedrooms) params.min_bedrooms = parseInt(filters.minBedrooms)
      if (filters.maxBedrooms) params.max_bedrooms = parseInt(filters.maxBedrooms)
      if (filters.minPrice) params.min_price = parseFloat(filters.minPrice)
      if (filters.maxPrice) params.max_price = parseFloat(filters.maxPrice)

      const response = await axios.get(`http://localhost:8003/api/market/export/${format.toLowerCase()}`, {
        params,
        responseType: 'blob'
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `market-analysis.${format.toLowerCase()}`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success(`Data exported as ${format}`)
    } catch (error) {
      toast.error('Failed to export data')
    }
  }

  if (loading && !statistics) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  const bedroomData = statistics?.avg_price_by_bedrooms
    ? Object.entries(statistics.avg_price_by_bedrooms).map(([beds, price]) => ({
        bedrooms: beds,
        price: price
      }))
    : []

  const correlationData = correlations?.correlations
    ? Object.entries(correlations.correlations).map(([feature, value]) => ({
        feature: feature.replace(/_/g, ' '),
        correlation: value
      }))
    : []

  const pieData = [
    { name: 'Budget (<$200k)', value: 25 },
    { name: 'Mid-Range ($200-300k)', value: 35 },
    { name: 'Premium ($300-400k)', value: 25 },
    { name: 'Luxury ($400k+)', value: 15 },
  ]

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Market Analysis</h1>
          <p className="text-gray-600 mt-2">Deep dive into property market trends and analytics</p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => exportData('CSV')} className="btn-secondary flex items-center gap-2">
            <Download className="h-4 w-4" />
            Export CSV
          </button>
          <button onClick={() => exportData('PDF')} className="btn-secondary flex items-center gap-2">
            <Download className="h-4 w-4" />
            Export PDF
          </button>
          <button onClick={fetchAllData} className="btn-secondary">
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {['overview', 'segments', 'what-if'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-2 px-1 border-b-2 font-medium text-sm capitalize ${
                activeTab === tab
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {/* Filters */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Filter className="h-5 w-5" />
          Filters
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="label">Min Bedrooms</label>
            <input
              type="number"
              value={filters.minBedrooms}
              onChange={(e) => setFilters({...filters, minBedrooms: e.target.value})}
              className="input-field"
              placeholder={`Min ${availableFilters?.bedrooms?.min || 1}`}
              min={availableFilters?.bedrooms?.min}
              max={availableFilters?.bedrooms?.max}
            />
            {availableFilters && (
              <p className="text-xs text-gray-500 mt-1">
                Available: {availableFilters.bedrooms.available.join(', ')}
              </p>
            )}
          </div>
          <div>
            <label className="label">Max Bedrooms</label>
            <input
              type="number"
              value={filters.maxBedrooms}
              onChange={(e) => setFilters({...filters, maxBedrooms: e.target.value})}
              className="input-field"
              placeholder={`Max ${availableFilters?.bedrooms?.max || 10}`}
              min={availableFilters?.bedrooms?.min}
              max={availableFilters?.bedrooms?.max}
            />
          </div>
          <div>
            <label className="label">Min Price</label>
            <input
              type="number"
              value={filters.minPrice}
              onChange={(e) => setFilters({...filters, minPrice: e.target.value})}
              className="input-field"
              placeholder={`Min $${availableFilters?.price?.min?.toLocaleString() || 0}`}
            />
          </div>
          <div>
            <label className="label">Max Price</label>
            <input
              type="number"
              value={filters.maxPrice}
              onChange={(e) => setFilters({...filters, maxPrice: e.target.value})}
              className="input-field"
              placeholder={`Max $${availableFilters?.price?.max?.toLocaleString() || 0}`}
            />
          </div>
        </div>

        {(filters.minBedrooms || filters.maxBedrooms || filters.minPrice || filters.maxPrice) && (
          <div className="mt-4 flex justify-end">
            <button onClick={handleResetFilters} className="text-sm text-red-600 hover:text-red-800">
              Clear Filters
            </button>
          </div>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-6 w-6 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-red-800">
                {error.type === 'NO_DATA' ? 'No Properties Found' : 'Error Loading Data'}
              </h3>
              <p className="text-red-700 mt-1">{error.message}</p>

              {error.suggestions && error.suggestions.length > 0 && (
                <div className="mt-3">
                  <p className="font-medium text-red-800">Suggestions:</p>
                  <ul className="list-disc list-inside mt-1 space-y-1">
                    {error.suggestions.map((suggestion, idx) => (
                      <li key={idx} className="text-red-700 text-sm">{suggestion}</li>
                    ))}
                  </ul>
                </div>
              )}

              {error.availableData && (
                <div className="mt-3 p-3 bg-red-100 rounded-md">
                  <p className="font-medium text-red-800">Available Data Range:</p>
                  <div className="grid grid-cols-2 gap-2 mt-2 text-sm">
                    <div>
                      <span className="text-red-700">Bedrooms:</span>
                      <span className="ml-2 font-medium">
                        {error.availableData.bedrooms.min} - {error.availableData.bedrooms.max}
                      </span>
                      <br />
                      <span className="text-red-600 text-xs">
                        Available: {error.availableData.bedrooms.available.join(', ')}
                      </span>
                    </div>
                    <div>
                      <span className="text-red-700">Price Range:</span>
                      <span className="ml-2 font-medium">
                        ${error.availableData.price.min.toLocaleString()} - ${error.availableData.price.max.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <button
                onClick={handleResetFilters}
                className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
              >
                Reset Filters
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Only show data if no error and data exists */}
      {!error && activeTab === 'overview' && statistics && (
        <>
          {/* Statistics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
            <div className="card">
              <p className="text-sm text-gray-600">Average Price</p>
              <p className="text-2xl font-bold mt-1">${statistics.price?.mean?.toLocaleString() || '0'}</p>
              <p className="text-xs text-gray-500 mt-1">±${statistics.price?.std?.toLocaleString() || '0'}</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-600">Median Price</p>
              <p className="text-2xl font-bold mt-1">${statistics.price?.median?.toLocaleString() || '0'}</p>
              <p className="text-xs text-gray-500 mt-1">IQR: ${((statistics.price?.q3 || 0) - (statistics.price?.q1 || 0)).toLocaleString()}</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-600">Price per Sq Ft</p>
              <p className="text-2xl font-bold mt-1">${statistics.price_per_sqft?.mean?.toFixed(2) || '0'}</p>
              <p className="text-xs text-gray-500 mt-1">Range: ${statistics.price_per_sqft?.min?.toFixed(2) || '0'} - ${statistics.price_per_sqft?.max?.toFixed(2) || '0'}</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-600">Filtered Properties</p>
              <p className="text-2xl font-bold mt-1">{statistics.total_properties_filtered || 0}</p>
              <p className="text-xs text-gray-500 mt-1">Matching current filters</p>
            </div>
            <div className="card bg-blue-50 border-blue-200">
              <p className="text-sm text-blue-800">Total Available</p>
              <p className="text-2xl font-bold mt-1 text-blue-900">{statistics.total_properties_available || 0}</p>
              <p className="text-xs text-blue-600 mt-1">All properties in dataset</p>
            </div>
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {bedroomData.length > 0 && (
              <div className="card">
                <h2 className="text-lg font-semibold mb-4">Average Price by Bedrooms</h2>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={bedroomData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="bedrooms" />
                    <YAxis />
                    <Tooltip formatter={(value: any) => `$${value.toLocaleString()}`} />
                    <Bar dataKey="price" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            <div className="card">
              <h2 className="text-lg font-semibold mb-4">Market Distribution</h2>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={(entry) => `${entry.name}: ${entry.value}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {correlationData.length > 0 && (
              <div className="card lg:col-span-2">
                <h2 className="text-lg font-semibold mb-4">Feature Correlations with Price</h2>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={correlationData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" domain={[-1, 1]} />
                    <YAxis dataKey="feature" type="category" width={150} />
                    <Tooltip />
                    <Bar dataKey="correlation" fill="#10b981" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </>
      )}

      {!error && activeTab === 'segments' && segments && (
        <>
          <div className="card">
            <h2 className="text-lg font-semibold mb-4">Analysis by Bedroom Count</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {Object.entries(segments.by_bedrooms || {}).map(([beds, data]: [string, any]) => (
                <div key={beds} className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-600">{beds} Bedroom{beds !== '1' ? 's' : ''}</p>
                  <p className="text-xl font-bold mt-1">${data.avg_price?.toLocaleString() || '0'}</p>
                  <p className="text-xs text-gray-500">{data.count || 0} properties</p>
                  <p className="text-xs text-gray-500 mt-1">{Math.round(data.avg_sqft || 0)} sq ft avg</p>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold mb-4">Price Tier Analysis</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {Object.entries(segments.by_price_tier || {}).map(([tier, data]: [string, any]) => (
                <div key={tier} className="p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg">
                  <p className="text-sm font-medium text-blue-800">{tier}</p>
                  <p className="text-lg font-bold mt-1">${data.avg_price?.toLocaleString() || '0'}</p>
                  <p className="text-xs text-gray-600">{data.count || 0} properties</p>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold mb-4">Location Analysis</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(segments.by_location || {}).map(([location, data]: [string, any]) => (
                <div key={location} className="p-4 border border-gray-200 rounded-lg">
                  <p className="text-sm font-medium text-gray-700">{location}</p>
                  <p className="text-lg font-bold mt-1">${data.avg_price?.toLocaleString() || '0'}</p>
                  <p className="text-xs text-gray-500">{data.count || 0} properties</p>
                  <p className="text-xs text-gray-500 mt-1">{data.avg_distance?.toFixed(1) || '0'} miles from center</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {!error && activeTab === 'what-if' && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Target className="h-5 w-5" />
            What-If Analysis Tool
          </h2>
          <div className="flex gap-4 mb-6">
            <select
              value={whatIfFeature}
              onChange={(e) => setWhatIfFeature(e.target.value)}
              className="input-field max-w-xs"
            >
              <option value="square_footage">Square Footage</option>
              <option value="bedrooms">Bedrooms</option>
              <option value="school_rating">School Rating</option>
            </select>
            <button onClick={runWhatIfAnalysis} className="btn-primary">
              Run Analysis
            </button>
          </div>

          {whatIfData.length > 0 && (
            <>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={whatIfData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="value" label={{ value: whatIfFeature.replace(/_/g, ' '), position: 'bottom' }} />
                  <YAxis label={{ value: 'Predicted Price ($)', angle: -90, position: 'left' }} />
                  <Tooltip formatter={(value: any) => `$${value.toLocaleString()}`} />
                  <Line type="monotone" dataKey="predicted_price" stroke="#3b82f6" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>

              <div className="mt-4 p-4 bg-blue-50 rounded-lg">
                <p className="font-semibold">Analysis Summary</p>
                <p className="text-sm text-gray-700 mt-1">
                  {whatIfFeature.replace(/_/g, ' ')} impact:
                  ${((whatIfData[whatIfData.length-1]?.predicted_price || 0) - (whatIfData[0]?.predicted_price || 0)).toLocaleString()} difference
                  across the analyzed range
                </p>
                <p className="text-sm text-gray-600 mt-2">
                  Optimal value: {whatIfData.reduce((max, item) => item.predicted_price > max.predicted_price ? item : max, whatIfData[0]).value.toFixed(1)}
                </p>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}