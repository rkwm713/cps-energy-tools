import React, { createContext, useContext, useState } from 'react'
import { Snackbar, Alert } from '@mui/material'
import type { AlertColor } from '@mui/material'

interface NotifyOptions {
  message: string
  severity?: AlertColor
}

type NotifyFn = (options: NotifyOptions) => void

const NotifierContext = createContext<NotifyFn>(() => {})

export const useNotifier = () => useContext(NotifierContext)

export const NotifierProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [severity, setSeverity] = useState<AlertColor>('info')

  const notify: NotifyFn = ({ message, severity = 'info' }) => {
    setMessage(message)
    setSeverity(severity)
    setOpen(true)
  }

  const handleClose = (_: unknown, reason?: string) => {
    if (reason === 'clickaway') return
    setOpen(false)
  }

  return (
    <NotifierContext.Provider value={notify}>
      {children}
      <Snackbar
        open={open}
        autoHideDuration={4000}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleClose} severity={severity} sx={{ width: '100%' }}>
          {message}
        </Alert>
      </Snackbar>
    </NotifierContext.Provider>
  )
} 