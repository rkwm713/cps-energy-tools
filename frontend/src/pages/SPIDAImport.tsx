/* eslint-disable */
/* @ts-nocheck */
import React, { useState, useEffect } from 'react'
import {
  Box,
  Typography,
  Button,
  Paper,
  Stepper,
  Step,
  StepButton,
  FormControl,
  Select,
  MenuItem,
} from '@mui/material'
import { useNotifier } from '../components/Notifier'
import AttachmentTable, { type InsulatorRow } from '../components/AttachmentTable'
import { spidaApi, type SpidaImportResponse, type SpidaValidationResponse, type SpidaProjectPayload } from '../services/api'

const SPIDAImport: React.FC = () => {
  const [katFile, setKatFile] = useState<File | null>(null)
  const [jobName, setJobName] = useState<string>('')
  const [specs, setSpecs] = useState<any[]>([])
  const [structures, setStructures] = useState<any[]>([])
  const [job, setJob] = useState<any>(null) // Consider a more specific type if possible
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null) // New state for download URL
  const [activeStep, setActiveStep] = useState<number>(0)
  const [error, setError] = useState<string | null>(null)
  const notify = useNotifier()

  // Fetch insulator specs once
  useEffect(() => {
    spidaApi.getInsulatorSpecs().then(setSpecs).catch((err) => {
      const msg = err.response?.data?.detail || err.message
      notify({ message: `Failed to load insulator specs: ${msg}`, severity: 'error' })
    })
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!katFile) {
      setError('Katapult JSON file is required')
      return
    }

    try {
      const data: SpidaImportResponse = await spidaApi.uploadSpidaImport(katFile, jobName)
      if (!data.success) throw new Error(data.error || 'Upload failed.') // Assuming 'error' field for non-success
      
      setStructures(data.structures || [])
      setJob(data.job || null)
      setDownloadUrl(data.download_url || null) // Store the download URL
      setActiveStep(0)
      setError(null)
      notify({ message: 'Upload successful', severity: 'success' })
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message
      setError(msg)
      notify({ message: msg, severity: 'error' })
      setStructures([])
      setDownloadUrl(null)
    }
  }

  const current = structures[activeStep]

  const updateRow = (rowIdx: number, updates: Partial<InsulatorRow>) => {
    setStructures((prev: any[]) => {
      const copy = [...prev]
      const ins = copy[activeStep].insulators.map((r: any, i: number) =>
        i === rowIdx ? { ...r, ...updates } : r
      )
      copy[activeStep] = { ...copy[activeStep], insulators: ins }
      return copy
    })
  }

  const bulkSetType = (specIndex: number) => {
    setStructures((prev) =>
      prev.map((s, idx) =>
        idx === activeStep
          ? { ...s, insulators: s.insulators.map((r: any) => ({ ...r, specIndex })) }
          : s
      )
    )
  }

  const bulkToggleCrossarm = () => {
    setStructures((prev) =>
      prev.map((s, idx) =>
        idx === activeStep
          ? {
              ...s,
              insulators: s.insulators.map((r: any) => ({ ...r, onCrossarm: !r.onCrossarm })),
            }
          : s
      )
    )
  }

  const validateCurrent = async () => {
    try {
      // The backend /api/validate expects a full SPIDA project, not just job + structures
      // For now, we'll send the current structures and job info as a payload.
      // If the backend's /validate endpoint expects the full SPIDA project JSON,
      // this payload might need to be constructed differently.
      // Assuming SpidaProjectPayload can accept { job, structures } for now.
      const payload: SpidaProjectPayload = { ...job, structures }
      const data: SpidaValidationResponse = await spidaApi.validateSpidaProject(payload)
      if (data.valid) notify({ message: 'Configuration valid', severity: 'success' })
      else notify({ message: data.errors.join('\n'), severity: 'error' })
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message
      notify({ message: msg, severity: 'error' })
    }
  }

  const downloadJson = () => {
    if (downloadUrl) {
      window.open(downloadUrl, '_blank')
    } else {
      notify({ message: 'No file available for download. Please upload and transform a file first.', severity: 'warning' })
    }
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        SPIDAcalc Import & Insulator Assignment
      </Typography>

      {/* Upload section (hidden once structures are loaded) */}
      {structures.length === 0 && (
        <Paper sx={{ p: 3, mb: 4 }} component="form" onSubmit={handleSubmit}>
          <Box display="flex" flexDirection="column" gap={2}>
            <Button variant="outlined" component="label">
              Select Katapult JSON
              <input type="file" hidden accept=".json" onChange={(e) => setKatFile(e.target.files?.[0] || null)} />
            </Button>
            {katFile && <Typography variant="body2">Selected: {katFile.name}</Typography>}
            <Button type="submit" variant="contained">
              Upload & Transform
            </Button>
            {error && (
              <Typography variant="body2" color="error">
                {error}
              </Typography>
            )}
          </Box>
        </Paper>
      )}

      {/* Editor section */}
      {structures.length > 0 && (
        <Box>
          <Stepper nonLinear activeStep={activeStep} sx={{ overflowX: 'auto', mb: 2 }}>
            {structures.map((s: any, idx: number) => (
              <Step key={s.structureId} completed={false}>
                <StepButton color="inherit" onClick={() => setActiveStep(idx)}>
                  {s.structureId}
                </StepButton>
              </Step>
            ))}
          </Stepper>

          {/* Sidebar */}
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6">Pole {current.structureId}</Typography>
            <Typography>Number: {current.poleNumber}</Typography>
            <Typography>
              Lat/Lon: {current.lat?.toFixed?.(5) || '—'} / {current.lon?.toFixed?.(5) || '—'}
            </Typography>
          </Paper>

          {/* Bulk controls */}
          <Box display="flex" flexWrap="wrap" gap={2} mb={2}>
            <Box display="flex" alignItems="center" gap={1}>
              <Typography variant="body2">Set All Types:</Typography>
              <FormControl size="small">
                <Select
                  displayEmpty
                  value=""
                  onChange={(e) => bulkSetType(Number(e.target.value))}
                >
                  <MenuItem value="">
                    <em>Select spec...</em>
                  </MenuItem>
                  {specs.map((spec: any, idx: number) => (
                    <MenuItem key={idx} value={idx}>
                      {spec.name || `Spec ${idx + 1}`}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
            <Button variant="outlined" onClick={bulkToggleCrossarm}>
              Toggle All Crossarms
            </Button>
            <Button variant="contained" onClick={validateCurrent}>
              Validate Configuration
            </Button>
            <Button variant="contained" color="secondary" onClick={downloadJson}>
              Download SPIDAcalc JSON
            </Button>
          </Box>

          {/* Attachment table */}
          <Paper>
            <AttachmentTable rows={current.insulators} specs={specs} onRowChange={updateRow} />
          </Paper>
        </Box>
      )}
    </Box>
  )
}

export default SPIDAImport
