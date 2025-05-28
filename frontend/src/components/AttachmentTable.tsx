import React from 'react'
import {
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Select,
  MenuItem,
  Checkbox,
  FormControl,
  Chip,
} from '@mui/material'

export interface InsulatorRow {
  specIndex: number | null
  distanceToTop: { unit: string; value: number | null }
  onCrossarm: boolean
}

interface Props {
  rows: InsulatorRow[]
  specs: any[]
  onRowChange: (rowIndex: number, updates: Partial<InsulatorRow>) => void
}

/**
 * AttachmentTable – renders a list of insulator attachment rows and allows editing
 * of the `specIndex` and `onCrossarm` fields.
 */
const AttachmentTable: React.FC<Props> = ({ rows, specs, onRowChange }) => {
  // Helper to get human-readable status for a row
  const getStatusLabel = (row: InsulatorRow) => {
    if (row.specIndex === null || row.specIndex === undefined) return 'Missing type'
    return 'Complete'
  }

  const getStatusColor = (row: InsulatorRow) => {
    return row.specIndex === null || row.specIndex === undefined ? 'warning' : 'success'
  }

  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>#</TableCell>
          <TableCell>Height (m)</TableCell>
          <TableCell>Insulator Type</TableCell>
          <TableCell align="center">On Crossarm</TableCell>
          <TableCell>Status</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row, idx) => (
          <TableRow key={idx} hover>
            <TableCell>{idx + 1}</TableCell>
            <TableCell>
              {row.distanceToTop?.value !== null && row.distanceToTop?.value !== undefined
                ? row.distanceToTop.value.toFixed(2)
                : '—'}
            </TableCell>
            <TableCell>
              <FormControl size="small" fullWidth>
                <Select
                  value={row.specIndex ?? ''}
                  displayEmpty
                  onChange={(e) =>
                    onRowChange(idx, { specIndex: e.target.value as number | null })
                  }
                >
                  <MenuItem value="">
                    <em>None</em>
                  </MenuItem>
                  {specs.map((spec: any, sIdx: number) => (
                    <MenuItem key={sIdx} value={sIdx}>
                      {spec.name || `Spec ${sIdx + 1}`}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </TableCell>
            <TableCell align="center">
              <Checkbox
                checked={row.onCrossarm}
                onChange={(e) => onRowChange(idx, { onCrossarm: e.target.checked })}
              />
            </TableCell>
            <TableCell>
              <Chip label={getStatusLabel(row)} color={getStatusColor(row) as any} size="small" />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export default AttachmentTable 