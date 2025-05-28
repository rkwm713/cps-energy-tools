import React, { useState, useMemo } from 'react'
import axios from 'axios'
import {
  Box,
  Button,
  Typography,
  TextField,
  Paper,
  TableContainer,
  Table,
  TableRow,
  TableCell,
  TableBody,
  TableHead,
  Tabs,
  Tab,
  Chip,
  InputAdornment,
  IconButton,
} from '@mui/material'
import { useNotifier } from '../components/Notifier'
import SearchIcon from '@mui/icons-material/Search'

const PoleComparison: React.FC = () => {
  const [katapultFile, setKatapultFile] = useState<File | null>(null)
  const [spidaFile, setSpidaFile] = useState<File | null>(null)
  const [threshold, setThreshold] = useState<string>('5.0')
  const [result, setResult] = useState<any>(null)
  const [_error, setError] = useState<string | null>(null)
  const [tabIdx, setTabIdx] = useState(0)
  const [search, setSearch] = useState('')
  const notify = useNotifier()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!katapultFile || !spidaFile) {
      setError('Both files are required')
      return
    }

    const formData = new FormData()
    formData.append('katapult_file', katapultFile)
    formData.append('spida_file', spidaFile)
    formData.append('threshold', threshold)

    try {
      const { data } = await axios.post('/api/pole-comparison', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(data)
      setError(null)
      notify({ message: 'Comparison completed', severity: 'success' })
    } catch (err: any) {
      const msg = err.response?.data?.error || err.message
      setError(msg)
      setResult(null)
      notify({ message: msg, severity: 'error' })
    }
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Pole Comparison Tool
      </Typography>

      <Paper sx={{ p: 3, mb: 4 }} component="form" onSubmit={handleSubmit}>
        <Box display="flex" flexDirection="column" gap={2}>
          <Button variant="outlined" component="label">
            Select Katapult Excel
            <input
              type="file"
              hidden
              accept=".xlsx,.xls"
              onChange={(e) => setKatapultFile(e.target.files?.[0] || null)}
            />
          </Button>
          {katapultFile && (
            <Typography variant="body2">Selected: {katapultFile.name}</Typography>
          )}

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

          <TextField
            label="Threshold (%)"
            type="number"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            inputProps={{ step: 0.1 }}
          />

          <Button type="submit" variant="contained">
            Compare
          </Button>
        </Box>
      </Paper>

      {result && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Summary
          </Typography>
          <TableContainer component={Paper} sx={{ mb: 4 }}>
            <Table size="small">
              <TableBody>
                {Object.entries(result.summary).map(([k, v]) => (
                  <TableRow key={k}>
                    <TableCell sx={{ fontWeight: 600 }}>{k}</TableCell>
                    <TableCell>{String(v)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {/* ---------------- Results Tabs & Search ---------------- */}
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
            <Tabs value={tabIdx} onChange={(_, v) => setTabIdx(v)}>
              <Tab label={`All Poles (${result.results.length})`} />
              <Tab label={`Issues (${result.issues.length})`} />
              <Tab label={`Verification (${result.verification ? Object.values(result.verification).reduce((a: number, v: any) => a + (Array.isArray(v) ? v.length : 0), 0) : 0})`} />
            </Tabs>

            {/* Search (only applies to first two tabs) */}
            {tabIdx !== 2 && (
              <TextField
                size="small"
                placeholder="Search poles..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                sx={{ ml: 'auto', width: 250 }}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton size="small" disabled>
                        <SearchIcon fontSize="small" />
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
            )}
          </Box>

          {/* ---------------- Data Tables ---------------- */}
          {tabIdx === 0 && (
            <ResultsTable rows={result.results} threshold={parseFloat(threshold)} search={search} />
          )}
          {tabIdx === 1 && (
            <ResultsTable rows={result.issues} threshold={parseFloat(threshold)} search={search} />
          )}
          {tabIdx === 2 && (
            <VerificationPanel verification={result.verification} />
          )}
        </Box>
      )}
    </Box>
  )
}

export default PoleComparison

// ---------------- Helper Components ----------------

interface Row {
  scid_number: string | number
  spida_pole_number: string
  katapult_pole_number: string
  spida_pole_spec: string
  katapult_pole_spec: string
  spida_existing_loading: number
  katapult_existing_loading: number
  spida_final_loading: number
  katapult_final_loading: number
  existing_delta?: number
  final_delta?: number
  has_issue: boolean
}

interface ResultsTableProps {
  rows: Row[]
  threshold: number
  search: string
}

const ResultsTable: React.FC<ResultsTableProps> = ({ rows, threshold, search }) => {
  const filtered = useMemo(() => {
    if (!search) return rows
    const q = search.toLowerCase()
    return rows.filter((r) =>
      [r.scid_number, r.spida_pole_number, r.katapult_pole_number].some((val) =>
        String(val).toLowerCase().includes(q)
      )
    )
  }, [rows, search])

  return (
    <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            <TableCell>SCID #</TableCell>
            <TableCell>SPIDA Pole #</TableCell>
            <TableCell>Katapult Pole #</TableCell>
            <TableCell>SPIDA Pole Spec</TableCell>
            <TableCell>Katapult Pole Spec</TableCell>
            <TableCell align="center">SPIDA Existing %</TableCell>
            <TableCell align="center">Katapult Existing %</TableCell>
            <TableCell align="center">SPIDA Final %</TableCell>
            <TableCell align="center">Katapult Final %</TableCell>
            <TableCell>Status</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {filtered.map((row) => {
            const specMismatch = row.spida_pole_spec !== row.katapult_pole_spec
            const existingFlag = row.existing_delta !== undefined && row.existing_delta > threshold
            const finalFlag = row.final_delta !== undefined && row.final_delta > threshold

            const dangerBg = (flag: boolean) => (flag ? 'error.light' : undefined)

            return (
              <TableRow key={row.scid_number} hover>
                <TableCell>{row.scid_number}</TableCell>
                <TableCell>{row.spida_pole_number}</TableCell>
                <TableCell>{row.katapult_pole_number}</TableCell>
                <TableCell sx={{ bgcolor: dangerBg(specMismatch) }}>{row.spida_pole_spec}</TableCell>
                <TableCell sx={{ bgcolor: dangerBg(specMismatch) }}>{row.katapult_pole_spec}</TableCell>
                <TableCell align="center" sx={{ bgcolor: dangerBg(existingFlag) }}>
                  {row.spida_existing_loading.toFixed(2)}
                </TableCell>
                <TableCell align="center" sx={{ bgcolor: dangerBg(existingFlag) }}>
                  {row.katapult_existing_loading.toFixed(2)}
                </TableCell>
                <TableCell align="center" sx={{ bgcolor: dangerBg(finalFlag) }}>
                  {row.spida_final_loading.toFixed(2)}
                </TableCell>
                <TableCell align="center" sx={{ bgcolor: dangerBg(finalFlag) }}>
                  {row.katapult_final_loading.toFixed(2)}
                </TableCell>
                <TableCell>
                  <Chip
                    label={row.has_issue ? 'Issue' : 'OK'}
                    color={row.has_issue ? 'error' : 'success'}
                    size="small"
                  />
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </TableContainer>
  )
}

interface VerificationPanelProps {
  verification: any
}

const VerificationPanel: React.FC<VerificationPanelProps> = ({ verification }) => {
  if (!verification) return null

  const section = (title: string, items: any[]) => (
    <Box sx={{ mb: 2 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }} gutterBottom>
        {title} ({items.length})
      </Typography>
      {items.length ? (
        <Typography variant="body2">{items.join(', ')}</Typography>
      ) : (
        <Typography variant="body2" color="text.secondary">
          None
        </Typography>
      )}
    </Box>
  )

  return (
    <Paper sx={{ p: 3 }}>
      {section('Missing in SPIDA', verification.missing_in_spida || [])}
      {section('Missing in Katapult', verification.missing_in_katapult || [])}
      {section('Duplicates in SPIDA', verification.duplicates_in_spida || [])}
      {section('Duplicates in Katapult', verification.duplicates_in_katapult || [])}
      {section('Formatting Issues', (verification.formatting_issues || []).map((i: any) => `${i.poleId} – ${i.issue}`))}
    </Paper>
  )
}
