import React, { useState } from 'react'
import axios from 'axios'
import {
  Box,
  Typography,
  Button,
  Paper,
} from '@mui/material'
import { useNotifier } from '../components/Notifier'

const QCChecker: React.FC = () => {
  const [spidaFile, setSpidaFile] = useState<File | null>(null)
  const [katapultFile, setKatapultFile] = useState<File | null>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const notify = useNotifier()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!spidaFile) {
      setError('SPIDAcalc JSON file is required')
      return
    }

    const formData = new FormData()
    formData.append('spida_file', spidaFile)
    if (katapultFile) formData.append('katapult_file', katapultFile)

    try {
      const { data } = await axios.post('/api/spidacalc-qc', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(data)
      setError(null)
      notify({ message: 'QC run completed', severity: 'success' })
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
        SPIDAcalc QC Checker
      </Typography>

      {error && (
        <Paper sx={{ p: 2, mb: 4 }}>
          <Typography variant="body2" color="error">
            {error}
          </Typography>
        </Paper>
      )}

      <Paper sx={{ p: 3, mb: 4 }} component="form" onSubmit={handleSubmit}>
        <Box display="flex" flexDirection="column" gap={2}>
          <Button variant="outlined" component="label">
            Select SPIDAcalc JSON
            <input
              type="file"
              hidden
              accept=".json"
              onChange={(e) => setSpidaFile(e.target.files?.[0] || null)}
            />
          </Button>
          {spidaFile && (
            <Typography variant="body2">Selected: {spidaFile.name}</Typography>
          )}

          <Button variant="outlined" component="label">
            Select Katapult JSON (optional)
            <input
              type="file"
              hidden
              accept=".json"
              onChange={(e) => setKatapultFile(e.target.files?.[0] || null)}
            />
          </Button>
          {katapultFile && (
            <Typography variant="body2">Selected: {katapultFile.name}</Typography>
          )}

          <Button type="submit" variant="contained">
            Run QC
          </Button>
        </Box>
      </Paper>

      {result && (
        <Paper sx={{ p: 2, whiteSpace: 'pre-wrap' }}>
          <Typography variant="h6" gutterBottom>
            QC Results
          </Typography>
          {JSON.stringify(result, null, 2)}
        </Paper>
      )}
    </Box>
  )
}

export default QCChecker 