import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { AppBar, Toolbar, Typography, Button, Container, CssBaseline, IconButton } from '@mui/material'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import Home from './pages/Home'
import PoleComparison from './pages/PoleComparison'
import CoverSheet from './pages/CoverSheet'
import MRRTool from './pages/MRRTool'
import HowToGuide from './pages/HowToGuide'
import QCChecker from './pages/QCChecker'
import SPIDAImport from './pages/SPIDAImport'
import { AnimatePresence, motion } from 'framer-motion'
import Brightness4Icon from '@mui/icons-material/Brightness4'
import Brightness7Icon from '@mui/icons-material/Brightness7'
import React, { useState, useMemo } from 'react'
import { NotifierProvider } from './components/Notifier'

// ---------- Page transition helper ----------
const pageVariants = {
  initial: { opacity: 0, y: 30 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
}

const PageWrapper: React.FC<{ children: React.ReactElement }> = ({ children }) => (
  <motion.div
    variants={pageVariants}
    initial="initial"
    animate="animate"
    exit="exit"
    transition={{ duration: 0.35, ease: 'easeInOut' }}
    style={{ height: '100%' }}
  >
    {children}
  </motion.div>
)

// Separate component that sits inside BrowserRouter so hooks like useLocation are safe
interface AppRoutesProps {
  mode: 'light' | 'dark'
  onToggleMode: () => void
}

const AppRoutes: React.FC<AppRoutesProps> = ({ mode, onToggleMode }) => {
  const location = useLocation()
  return (
    <>
      <AppBar position="static" color="primary" enableColorOnDark>
        <Toolbar>
          <img 
            src="/cps-tools-logo.svg" 
            alt="CPS Energy Tools Logo" 
            style={{ height: '40px', marginRight: '16px' }}
          />
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            CPS Energy Tools
          </Typography>
          <IconButton color="inherit" onClick={onToggleMode} sx={{ mr: 1 }}>
            {mode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
          </IconButton>
          <Button color="inherit" component={Link} to="/">
            Home
          </Button>
          <Button color="inherit" component={Link} to="/pole-comparison">
            Pole Comparison
          </Button>
          <Button color="inherit" component={Link} to="/cover-sheet">
            Cover Sheet
          </Button>
          <Button color="inherit" component={Link} to="/mrr-tool">
            MRR Tool
          </Button>
          <Button color="inherit" component={Link} to="/how-to-guide">
            How-To
          </Button>
          <Button color="inherit" component={Link} to="/spidacalc-qc">
            QC Checker
          </Button>
          <Button color="inherit" component={Link} to="/spidacalc-import">
            SPIDAcalc Import
          </Button>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: 4 }}>
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={<PageWrapper><Home /></PageWrapper>} />
            <Route path="/pole-comparison" element={<PageWrapper><PoleComparison /></PageWrapper>} />
            <Route path="/cover-sheet" element={<PageWrapper><CoverSheet /></PageWrapper>} />
            <Route path="/mrr-tool" element={<PageWrapper><MRRTool /></PageWrapper>} />
            <Route path="/how-to-guide" element={<PageWrapper><HowToGuide /></PageWrapper>} />
            <Route path="/spidacalc-qc" element={<PageWrapper><QCChecker /></PageWrapper>} />
            <Route path="/spidacalc-import" element={<PageWrapper><SPIDAImport /></PageWrapper>} />
          </Routes>
        </AnimatePresence>
      </Container>
    </>
  )
}

function App() {
  const [mode, setMode] = useState<'light' | 'dark'>('light')
  const theme = useMemo(() => getTheme(mode), [mode])

  const toggleMode = () => {
    setMode((prev) => (prev === 'light' ? 'dark' : 'light'))
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <NotifierProvider>
        <BrowserRouter>
          <AppRoutes mode={mode} onToggleMode={toggleMode} />
        </BrowserRouter>
      </NotifierProvider>
    </ThemeProvider>
  )
}

// Factory to build theme based on palette mode
const getTheme = (mode: 'light' | 'dark') =>
  createTheme({
    palette: {
      mode,
      primary: {
        main: '#0061a8',
      },
      secondary: {
        main: '#00897b',
      },
      background: {
        default: mode === 'light' ? '#f7f7f7' : '#121212',
      },
    },
  })

export default App
