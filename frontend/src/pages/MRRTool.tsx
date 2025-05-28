/* eslint-disable */
/* @ts-nocheck */
import React, { useState } from 'react'
import axios from 'axios'
import {
  Box,
  Typography,
  Button,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Table,
  TableHead,
  TableRow,
  TableBody,
  TableCell,
} from '@mui/material'
import { useNotifier } from '../components/Notifier'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
// @ts-ignore – external lib types to be installed separately
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
} from 'react-leaflet'
// @ts-ignore – external library, types installed at runtime or via CDN
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

/* @ts-nocheck */

// Fix default icon path so markers appear
delete (L as any).Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const MRRTool: React.FC = () => {
  const [jobFile, setJobFile] = useState<File | null>(null)
  const [geoFile, setGeoFile] = useState<File | null>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const notify = useNotifier()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!jobFile) {
      setError('Job JSON file is required')
      return
    }
    const formData = new FormData()
    formData.append('job_file', jobFile)
    if (geoFile) formData.append('geojson_file', geoFile)

    try {
      const { data } = await axios.post('/api/mrr-process', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(data)
      setError(null)
      notify({ message: 'MRR processing completed', severity: 'success' })
    } catch (err: any) {
      const msg = err.response?.data?.error || err.message
      setError(msg)
      notify({ message: msg, severity: 'error' })
      setResult(null)
    }
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        MRR Processing Tool
      </Typography>

      {error && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="body2" color="error">
            {error}
          </Typography>
        </Paper>
      )}

      <Paper sx={{ p: 3, mb: 4 }} component="form" onSubmit={handleSubmit}>
        <Box display="flex" flexDirection="column" gap={2}>
          <Button variant="outlined" component="label">
            Select Job JSON
            <input
              type="file"
              hidden
              accept=".json"
              onChange={(e) => setJobFile(e.target.files?.[0] || null)}
            />
          </Button>
          {jobFile && (
            <Typography variant="body2">Selected: {jobFile.name}</Typography>
          )}

          <Button variant="outlined" component="label">
            Select GeoJSON (optional)
            <input
              type="file"
              hidden
              accept=".json,.geojson"
              onChange={(e) => setGeoFile(e.target.files?.[0] || null)}
            />
          </Button>
          {geoFile && (
            <Typography variant="body2">Selected: {geoFile.name}</Typography>
          )}

          <Button type="submit" variant="contained">
            Process
          </Button>
        </Box>
      </Paper>

      {result && (
        <Paper sx={{ p: 2 }}>
          {result.download_available && result.summary?.output_filename && (
            <Box mb={2}>
              <Button
                variant="contained"
                onClick={() => {
                  const url = `/api/download-mrr/${encodeURIComponent(result.summary.output_filename)}`
                  window.open(url, '_blank')
                }}
              >
                Download Excel
              </Button>
            </Box>
          )}

          {/* Map */}
          {result.preview && Array.isArray(result.preview) && result.preview.length > 0 && (
            <Box sx={{ height: 400, width: '100%', mb: 4 }}>
              <MapContainer
                center={getMapCenter(result.preview)}
                zoom={13}
                style={{ height: '100%', width: '100%' }}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {result.preview.map((pole: any) => (
                  pole.lat && pole.lon && (
                    <Marker key={pole.scid || pole.pole_number} position={[pole.lat, pole.lon]}>
                      <Popup>
                        <strong>{pole.pole_number || '—'}</strong><br />
                        SCID: {pole.scid}
                      </Popup>
                    </Marker>
                  )
                ))}
              </MapContainer>
            </Box>
          )}

        </Paper>
      )}

      {/* ---------- Pole preview accordion ---------- */}
      {result?.preview && Array.isArray(result.preview) && result.preview.length > 0 && (
        <Box mt={4}>
          <Typography variant="h6" gutterBottom>
            Pole Preview
          </Typography>
          {result.preview.map((pole: any) => (
            <Accordion key={pole.scid || pole.pole_number}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography sx={{ flexBasis: 150 }}>{pole.pole_number || '—'}</Typography>
                <Typography sx={{ flexBasis: 100 }}>SCID: {pole.scid}</Typography>
                <Typography sx={{ color: 'text.secondary' }}>
                  {pole.attachers.length} attachers
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Attacher</TableCell>
                      <TableCell align="center">Existing</TableCell>
                      <TableCell align="center">Proposed</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {pole.attachers.map((a: any, idx: number) => (
                      <TableRow key={idx} hover>
                        <TableCell>{a.name}</TableCell>
                        <TableCell align="center">{a.existing_height}</TableCell>
                        <TableCell align="center">{a.proposed_height}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AccordionDetails>
            </Accordion>
          ))}
        </Box>
      )}
    </Box>
  )
}

// Helper to compute map center (avg lat/lon or fallback)
function getMapCenter(poles: any[]) {
  const coords = poles.filter((p) => p.lat && p.lon)
  if (coords.length === 0) return [29.42, -98.49] // San Antonio default
  const avgLat = coords.reduce((sum, p) => sum + p.lat, 0) / coords.length
  const avgLon = coords.reduce((sum, p) => sum + p.lon, 0) / coords.length
  return [avgLat, avgLon]
}

export default MRRTool 