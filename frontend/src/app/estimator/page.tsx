'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'
import toast from 'react-hot-toast'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function EstimatorPage() {
  const [form, setForm] = useState({
    square_footage: 1800,
    bedrooms: 3,
    bathrooms: 2,
    year_built: 2000,
    lot_size: 7500,
    distance_to_city_center: 5,
    school_rating: 7.5,
  })

  const [estimates, setEstimates] = useState<any[]>([])
  const [history, setHistory] = useState<any[]>([])
  const [selected, setSelected] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [rules, setRules] = useState<any>(null)

  // ✅ NEW: inline validation
  const [errors, setErrors] = useState<any>({})

  const FALLBACK_LIMITS: any = {
    square_footage: { min: 300, max: 10000 },
    bedrooms: { min: 1, max: 10 },
    bathrooms: { min: 1, max: 10 },
    year_built: { min: 1900, max: new Date().getFullYear() },
    lot_size: { min: 500, max: 50000 },
    distance_to_city_center: { min: 0, max: 100 },
    school_rating: { min: 0, max: 10 },
  }

  useEffect(() => {
    fetchHistory()

    axios.get('http://localhost:8002/api/validation-rules')
      .then(res => setRules(res.data?.feature_ranges))
      .catch(() => console.log("Using fallback limits"))
  }, [])

  const fetchHistory = async () => {
    const res = await axios.get('http://localhost:8002/api/history')
    setHistory(res.data)
  }

  const getLimits = (field: string) => {
    if (rules && rules[field]) return rules[field]
    return FALLBACK_LIMITS[field]
  }

  // ✅ validation logic
  const validateField = (name: string, value: number) => {
    const limits = getLimits(name)
    if (!limits) return ""
    if (value < limits.min || value > limits.max) {
      return `Recommended ${limits.min} - ${limits.max}`
    }
    return ""
  }

  const handleChange = (e: any) => {
    const value = e.target.value === "" ? "" : Number(e.target.value)

    setForm({ ...form, [e.target.name]: value })

    const errorMsg = validateField(e.target.name, value)
    setErrors({ ...errors, [e.target.name]: errorMsg })
  }

  const submit = async () => {
    setLoading(true)
    try {
      const res = await axios.post('http://localhost:8002/api/estimates', {
        properties: [form]
      })

      const result = res.data.estimates[0]

      setEstimates([result, ...estimates])
      fetchHistory()

      toast.success("Prediction success")

      if (result.warnings?.length) {
        result.warnings.forEach((w: any) => toast(`⚠️ ${w.message}`))
      }

    } catch (e: any) {
      const detail = e.response?.data?.detail
      if (Array.isArray(detail)) {
        toast.error(detail.map((d: any) => d.msg).join(", "))
      } else {
        toast.error("Error occurred")
      }
    }
    setLoading(false)
  }

  const toggleSelect = (item: any) => {
    if (selected.includes(item)) {
      setSelected(selected.filter(i => i !== item))
    } else {
      setSelected([...selected, item])
    }
  }

  const formatPrice = (price: number) =>
    `$${price.toLocaleString('en-US', { maximumFractionDigits: 0 })}`

  return (
    <div className="p-6 space-y-6">

      {/* HEADER */}
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Property Value Estimator</h1>
      </div>

      {/* FORM */}
      <div className="card grid grid-cols-2 gap-4">

        {Object.keys(form).map((key: any) => (
          <div key={key} className={key === "school_rating" ? "col-span-2" : ""}>
            <label className="font-medium capitalize">{key.replaceAll("_", " ")}</label>

            <input
              name={key}
              value={(form as any)[key]}
              onChange={handleChange}
              type="number"
              className="input-field"
            />

            {/* Recommended */}
            <p className="text-xs text-gray-500">
              Recommended: {getLimits(key)?.suggested_min ?? getLimits(key).min}
              {" - "}
              {getLimits(key)?.suggested_max ?? getLimits(key).max}
            </p>

            {/* Inline error */}
            {errors[key] && (
              <p className="text-xs text-yellow-600">{errors[key]}</p>
            )}
          </div>
        ))}

        <button
          onClick={submit}
          disabled={loading}
          className="btn-primary col-span-2 disabled:opacity-50"
        >
          {loading ? "Predicting..." : "Predict"}
        </button>
      </div>

      {/* RESULTS */}
      {estimates.length > 0 && (
        <div className="card">
          <h2 className="text-xl font-bold mb-4">Results</h2>

          <table className="w-full text-sm border">
            <thead className="bg-gray-100">
              <tr>
                <th>Select</th>
                <th>SqFt</th>
                <th>Beds</th>
                <th>Baths</th>
                <th>Year</th>
                <th>Rating</th>
                <th>Price</th>
              </tr>
            </thead>

            <tbody>
              {estimates.map((e, i) => (
                <tr key={i} className="text-center border-t">
                  <td>
                    <input type="checkbox" onChange={() => toggleSelect(e)} />
                  </td>
                  <td>{e.property.square_footage}</td>
                  <td>{e.property.bedrooms}</td>
                  <td>{e.property.bathrooms}</td>
                  <td>{e.property.year_built}</td>
                  <td>{e.property.school_rating}</td>
                  <td className="font-bold text-blue-600">
                    {formatPrice(e.predicted_price)}

                    {e.warnings?.length > 0 && (
                      <div className="text-xs text-yellow-600">⚠ Out of range</div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* CHART */}
      {estimates.length > 0 && (
        <div className="card">
          <h2 className="text-xl font-bold mb-4">Chart</h2>

          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={estimates.map((e, i) => ({
              name: `P${i + 1}`,
              price: e.predicted_price
            }))}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="price" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* COMPARISON */}
      {selected.length > 1 && (
        <div className="card">
          <h2 className="text-xl font-bold mb-4">Comparison</h2>

          <div className="grid grid-cols-2 gap-4">
            {selected.map((s, i) => (
              <div key={i} className="border p-3 rounded">
                <p>{s.property.square_footage} sqft</p>
                <p>{s.property.bedrooms} beds</p>
                <p>{s.property.bathrooms} baths</p>
                <p className="font-bold">{formatPrice(s.predicted_price)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* HISTORY */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">History</h2>

        <div className="grid gap-3">
          {history.map((h) => (
            <div key={h.id} className="p-3 border rounded flex justify-between">
              <div>
                {h.property.bedrooms} Beds • {h.property.bathrooms} Baths
              </div>
              <div className="font-bold text-green-600">
                {formatPrice(h.prediction)}
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}