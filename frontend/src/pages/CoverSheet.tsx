import React, { useState, useMemo } from 'react'
import axios from 'axios'
import {
  Box,
  Typography,
  Button,
  Paper,
  CircularProgress,
  Card,
  CardContent,
  TableContainer,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Tooltip,
  IconButton,
  InputAdornment,
  TextField,
} from '@mui/material'
import { useNotifier } from '../components/Notifier'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import DownloadIcon from '@mui/icons-material/Download'
import SearchIcon from '@mui/icons-material/Search'

const CoverSheet: React.FC = () => {
  const [spidaFile, setSpidaFile] = useState<File | null>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const notify = useNotifier()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!spidaFile) {
      setError('SPIDAcalc JSON file is required')
      return
    }

    const formData = new FormData()
    formData.append('spida_file', spidaFile)

    try {
      setLoading(true)
      const { data } = await axios.post('/api/cover-sheet', formData)
      setResult(data)
      setError(null)
      notify({ message: 'Cover sheet generated', severity: 'success' })
    } catch (err: any) {
      const msg = err.response?.data?.error || err.message
      setError(msg)
      notify({ message: msg, severity: 'error' })
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Cover Sheet Generator
      </Typography>

      {error && (
        <Typography variant="body2" color="error">
          {error}
        </Typography>
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

          <Button type="submit" variant="contained" disabled={loading || !spidaFile}>
            {loading ? 'Generating...' : 'Generate'}
          </Button>
        </Box>
      </Paper>

      {loading && (
        <Box display="flex" justifyContent="center" my={4}>
          <CircularProgress />
        </Box>
      )}

      {result && (
        <Box>
          {/* ---------- Action Bar ---------- */}
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2, gap: 1 }}>
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              Generated Cover Sheet
            </Typography>
            <Tooltip title="Copy to clipboard">
              <IconButton onClick={() => copyCoverSheet(result)}>
                <ContentCopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Download as text">
              <IconButton onClick={() => downloadCoverSheet(result)}>
                <DownloadIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>

          {/* ---------- Project Info Cards ---------- */}
          <Box
            sx={{
              display: 'grid',
              gap: 2,
              mb: 3,
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, 1fr)',
                md: 'repeat(3, 1fr)',
              },
            }}
          >
            {['Job Number', 'Client', 'Date', 'Location', 'City', 'Engineer', 'Comments'].map((key) => (
              <Card variant="outlined" key={key} sx={{ position: 'relative' }}>
                <IconButton
                  size="small"
                  sx={{ position: 'absolute', top: 4, right: 4 }}
                  onClick={() => navigator.clipboard.writeText(String(result[key] ?? ''))}
                >
                  <ContentCopyIcon fontSize="inherit" />
                </IconButton>
                <CardContent>
                  <Typography variant="subtitle2" color="text.secondary">
                    {key}
                  </Typography>
                  <Typography variant="body1">{result[key] || '—'}</Typography>
                </CardContent>
              </Card>
            ))}
          </Box>

          {/* ---------- Poles Table ---------- */}
          <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
            <TextField
              size="small"
              placeholder="Search poles..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
              sx={{ width: 250 }}
            />
          </Box>

          <PolesTable rows={result.Poles || []} search={search} />
        </Box>
      )}
    </Box>
  )
}

export default CoverSheet

// ---------------- Helper Components & utils ----------------

interface PoleRow {
  SCID: number
  'Station ID': string
  'Existing Loading %': number | null
  'Final Loading %': number | null
  Notes: string
}

const PolesTable: React.FC<{ rows: PoleRow[]; search: string }> = ({ rows, search }) => {
  const filtered = useMemo(() => {
    if (!search) return rows
    const q = search.toLowerCase()
    return rows.filter((r) =>
      [r['Station ID'], r.SCID].some((v) => String(v).toLowerCase().includes(q))
    )
  }, [rows, search])

  const fmtLoad = (val: number | null) => (val !== null && val !== undefined ? `${val.toFixed(2)}%` : '')
  const fmtStation = (s: string) => (s && s.includes('-') ? s.split('-').slice(1).join('-') : s)

  return (
    <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            <TableCell>SCID</TableCell>
            <TableCell>Station ID</TableCell>
            <TableCell align="center">Existing Loading %</TableCell>
            <TableCell align="center">Final Loading %</TableCell>
            <TableCell>Notes</TableCell>
            <TableCell align="center">Copy</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {filtered.map((row) => (
            <TableRow key={row.SCID} hover>
              <TableCell>{row.SCID}</TableCell>
              <TableCell>{fmtStation(row['Station ID'])}</TableCell>
              <TableCell align="center">{fmtLoad(row['Existing Loading %'])}</TableCell>
              <TableCell align="center">{fmtLoad(row['Final Loading %'])}</TableCell>
              <TableCell>{row.Notes}</TableCell>
              <TableCell align="center">
                <Tooltip title="Copy row">
                  <IconButton size="small" onClick={() => copyPoleRow(row)}>
                    <ContentCopyIcon fontSize="inherit" />
                  </IconButton>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}

function coverSheetToText(data: any): string {
  let txt = ''
  const field = (k: string) => (txt += `${k}: ${data[k] || ''}\n`)
  ;['Job Number', 'Client', 'Date', 'Location', 'City', 'Engineer', 'Comments'].forEach(field)
  txt += '\nPole Data Summary\n'
  txt += 'Station ID\tExisting Loading %\tFinal Loading %\tNotes\n'
  const fmtStation = (s: string) => (s && s.includes('-') ? s.split('-').slice(1).join('-') : s)
  ;(data.Poles || []).forEach((p: any) => {
    txt += `${fmtStation(p['Station ID'] || '')}\t${p['Existing Loading %']?.toFixed?.(1) || ''}\t${p['Final Loading %']?.toFixed?.(1) || ''}\t${p.Notes || ''}\n`
  })
  return txt
}

function copyCoverSheet(data: any) {
  const txt = coverSheetToText(data)
  navigator.clipboard.writeText(txt)
}

function downloadCoverSheet(data: any) {
  const txt = coverSheetToText(data)
  const blob = new Blob([txt], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `cover_sheet_${data['Job Number'] || 'data'}.txt`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function copyPoleRow(row: PoleRow) {
  const fmtStation = (s: string) => (s && s.includes('-') ? s.split('-').slice(1).join('-') : s)
  const fmtLoad = (v: number | null) => (v !== null && v !== undefined ? v.toFixed(1) : '')
  const txt = [
    row.SCID,
    fmtStation(row['Station ID']),
    fmtLoad(row['Existing Loading %']),
    fmtLoad(row['Final Loading %']),
    row.Notes || '',
  ].join('\t')
  navigator.clipboard.writeText(txt)
} 