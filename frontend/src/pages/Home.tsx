import React from 'react'
import {
  Box,
  Typography,
  Card,
  CardContent,
  CardActions,
  Button,
} from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'

// Icons
import CompareArrowsIcon from '@mui/icons-material/CompareArrows'
import DescriptionIcon from '@mui/icons-material/Description'
import BuildIcon from '@mui/icons-material/Build'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'

// Animation library
import { motion } from 'framer-motion'

// Create animated versions of MUI components
const MotionBox = motion(Box)
const MotionCard = motion(Card)

interface Tool {
  title: string
  description: string
  route: string
  Icon: React.ElementType
}

const tools: Tool[] = [
  {
    title: 'Pole Comparison',
    description: 'Compare Katapult & SPIDAcalc structures and spot discrepancies in seconds.',
    route: '/pole-comparison',
    Icon: CompareArrowsIcon,
  },
  {
    title: 'Cover Sheet',
    description: 'Generate a polished cover sheet directly from your SPIDAcalc JSON.',
    route: '/cover-sheet',
    Icon: DescriptionIcon,
  },
  {
    title: 'MRR Tool',
    description: 'Run MRR processing jobs and get a concise summary of the results.',
    route: '/mrr-tool',
    Icon: BuildIcon,
  },
  {
    title: 'How-To Guide',
    description: 'Step-by-step instructions and best practices for every tool.',
    route: '/how-to-guide',
    Icon: MenuBookIcon,
  },
  {
    title: 'QC Checker',
    description: 'Validate SPIDAcalc jobs against custom CPS Energy QC rules.',
    route: '/spidacalc-qc',
    Icon: CheckCircleIcon,
  },
]

// Animation variants
const containerVariants = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.1,
    },
  },
}

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
}

const Home: React.FC = () => {
  return (
    <Box>
      {/* Hero Section */}
      <MotionBox
        sx={{
          bgcolor: 'primary.main',
          color: 'primary.contrastText',
          py: { xs: 6, md: 8 },
          textAlign: 'center',
          borderRadius: 2,
          mb: 6,
        }}
        initial={{ opacity: 0, y: -30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <Typography variant="h3" component="h1" gutterBottom>
          CPS Energy Tools
        </Typography>
        <Typography variant="h6" sx={{ maxWidth: 680, mx: 'auto' }}>
          Your one-stop dashboard to validate, process, and streamline pole-attachment data.
        </Typography>
      </MotionBox>

      {/* Dashboard Cards */}
      <MotionBox
        sx={{
          display: 'grid',
          gap: 4,
          gridTemplateColumns: {
            xs: 'repeat(1, 1fr)',
            sm: 'repeat(2, 1fr)',
            md: 'repeat(3, 1fr)',
          },
        }}
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        {tools.map(({ title, description, route, Icon }) => (
          <Box key={title} component={RouterLink} to={route} sx={{ textDecoration: 'none' }}>
            <MotionCard
              variants={cardVariants}
              whileHover={{ translateY: -6, boxShadow: '0 8px 20px rgba(0,0,0,0.15)' }}
              transition={{ type: 'spring', stiffness: 120, damping: 12 }}
              sx={{ height: '100%', display: 'flex', flexDirection: 'column', cursor: 'pointer' }}
            >
              <Box sx={{ pt: 4, textAlign: 'center' }}>
                <Icon sx={{ fontSize: 48, color: 'primary.main' }} />
              </Box>
              <CardContent sx={{ flexGrow: 1 }}>
                <Typography gutterBottom variant="h5" component="h2">
                  {title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {description}
                </Typography>
              </CardContent>
              <CardActions sx={{ justifyContent: 'flex-end', px: 2, pb: 2 }}>
                <Button size="small" variant="contained">
                  Open
                </Button>
              </CardActions>
            </MotionCard>
          </Box>
        ))}
      </MotionBox>
    </Box>
  )
}

export default Home
