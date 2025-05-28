import axios from 'axios';

// --- Backend API Base URL ---
// During development, Vite's proxy handles /api requests.
// In production, the web server serving the frontend should proxy /api to the backend.
const API_BASE_URL = '/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- TypeScript Interfaces for Backend Schemas ---

// SPIDAcalc Import / Validation
export interface InsulatorSpecsResponse extends Array<{ [key: string]: any }> {} // Matches List[Dict[str, Any]] in Python

export interface SpidaProjectPayload {
  [key: string]: any; // Matches Dict[str, Any] in Python
}

export interface SpidaValidationResponse {
  valid: boolean;
  errors: string[];
}

export interface SpidaImportStructureSummary {
  structureId: string;
  poleNumber?: string;
  lat?: number;
  lon?: number;
  insulators: { [key: string]: any }[]; // List[Dict[str, Any]]
}

export interface SpidaImportJobSummary {
  id: string;
  name: string;
}

export interface SpidaImportResponse {
  success: boolean;
  download_available: boolean;
  filename: string;
  download_url: string;
  structures: SpidaImportStructureSummary[];
  job: SpidaImportJobSummary;
  error?: string; // Added for potential error messages from backend
}

// --- API Service Functions ---

export const spidaApi = {
  getInsulatorSpecs: async (): Promise<InsulatorSpecsResponse> => {
    const response = await apiClient.get<InsulatorSpecsResponse>('/insulator-specs');
    return response.data;
  },

  validateSpidaProject: async (project: SpidaProjectPayload): Promise<SpidaValidationResponse> => {
    const response = await apiClient.post<SpidaValidationResponse>('/validate', project);
    return response.data;
  },

  uploadSpidaImport: async (file: File, jobName: string = 'Untitled Job'): Promise<SpidaImportResponse> => {
    const formData = new FormData();
    formData.append('katapult_file', file);
    formData.append('job_name', jobName);

    const response = await apiClient.post<SpidaImportResponse>('/spida-import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data', // Axios handles this automatically for FormData, but explicit is fine
      },
    });
    return response.data;
  },

  downloadFile: (filename: string): string => {
    // For downloads, we return the URL directly so the browser can handle the download
    // This avoids issues with Axios trying to parse binary data as JSON.
    return `${API_BASE_URL}/download/${filename}`;
  },
};

// You can add other API groups here, e.g., poleComparisonApi, coverSheetApi etc.
// For example:
/*
export const poleComparisonApi = {
  getPoleComparisonResults: async (payload: PoleComparisonRequest): Promise<PoleComparisonResponse> => {
    const response = await apiClient.post<PoleComparisonResponse>('/pole-comparison', payload);
    return response.data;
  },
};
*/
