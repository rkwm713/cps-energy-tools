/* eslint-disable */
/* @ts-nocheck */
import React, { useState, useEffect } from 'react'
import axios from 'axios'
import {
  Box,
  Typography,
  Button,
  Paper,
  Stepper,
  Step,
  StepButton,
} from '@mui/material'
import { useNotifier } from '../components/Notifier'
import AttachmentTable, { type InsulatorRow } from '../components/AttachmentTable'

const InsulatorConfig: React.FC = () => {
  const [specs, setSpecs] = useState<any[]>([])
  const [structures, setStructures] = useState<any[]>([])
  const [job, setJob] = useState<any>(null)
  const [katapultFile, setKatapultFile] = useState<File | null>(null)
  const [activeStep, setActiveStep] = useState<number>(0)
  const [error, setError] = useState<string | null>(null)
  const notify = useNotifier()

  // Fetch specs once
  useEffect(() => {
    axios.get('/api/insulator-specs').then(({ data }) => setSpecs(data))
  }, [])

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!katapultFile) {
      setError('Katapult JSON required')
      return
    }
    const fd = new FormData()
    fd.append('katapult_file', katapultFile)
    fd.append('job_name', katapultFile.name.replace(/\.json$/i, ''))
    try {
      const { data } = await axios.post('/api/spida-import', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      if (data.error) throw new Error(data.error)
      setStructures(data.structures)
      setJob(data.job)
      setActiveStep(0)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message)
      notify({ message: err.message, severity: 'error' })
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
          ? {
              ...s,
              insulators: s.insulators.map((r: any) => ({ ...r, specIndex })),
            }
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
              insulators: s.insulators.map((r: any) => ({
                ...r,
                onCrossarm: !r.onCrossarm,
              })),
            }
          : s
      )
    )
  }

  const validateCurrent = async () => {
    try {
      const payload = { ...job, structures }
      const { data } = await axios.post('/api/validate', payload)
      if (data.valid) notify({ message: 'Valid!', severity: 'success' })
      else notify({ message: data.errors.join('\n'), severity: 'error' })
    } catch (err: any) {
      notify({ message: err.message, severity: 'error' })
    }
  }

  const downloadJson = async () => {
    try {
      const payload = {
        job_name: job?.name || 'Job',
        structures,
      }
      const { data } = await axios.post('/api/spida-import', payload, {
        headers: { 'Content-Type': 'application/json' },
      })
      if (data.download_url) {
        window.open(data.download_url, '_blank')
      } else {
        notify({ message: 'Download URL missing from response', severity: 'warning' })
      }
    } catch (err: any) {
      notify({ message: err.response?.data?.detail || err.message, severity: 'error' })
    }
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        SPIDAcalc Insulator Configuration
      </Typography>

      {/* Upload */}
      {structures.length === 0 && (
        <Paper sx={{ p: 3, mb: 4 }} component="form" onSubmit={handleUpload}>
          <Box display="flex" flexDirection="column" gap={2}>
            <Button variant="outlined" component="label">
              Select Katapult JSON
              <input
                hidden
                type="file"
                accept=".json"
                onChange={(e) => setKatapultFile(e.target.files?.[0] || null)}
              />
            </Button>
            {katapultFile && <Typography>{katapultFile.name}</Typography>}
            <Button type="submit" variant="contained">
              Upload & Transform
            </Button>
            {error && (
              <Typography color="error" variant="body2">
                {error}
              </Typography>
            )}
          </Box>
        </Paper>
      )}

      {/* Editor */}
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
            <Button variant="outlined" onClick={() => bulkSetType(0)}>
              Set All Types to First Spec
            </Button>
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
            <AttachmentTable
              rows={current.insulators}
              specs={specs}
              onRowChange={updateRow}
            />
          </Paper>
        </Box>
      )}
    </Box>
  )
}

export default InsulatorConfig 