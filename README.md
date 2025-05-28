# CPS Energy Tools

This repository contains a suite of tools developed for CPS Energy, including a FastAPI backend, a React frontend, and various Python scripts for data processing and quality control.

## Project Structure

The project is organized into the following main directories:

*   `backend/`: Contains the FastAPI application and its API routers.
*   `frontend/`: Contains the React/TypeScript frontend application.
*   `cps_tools/`: A Python package containing core business logic and utility modules, shared between the backend and standalone scripts.
    *   `cps_tools/core/`: Modularized core logic for various tools (e.g., MRR, Cover Sheet, Katapult).
    *   `cps_tools/legacy/`: Contains wrappers or older code that is being phased out but maintained for compatibility.
    *   `cps_tools/settings.py`: Application-wide settings managed via Pydantic.
*   `scripts/`: Standalone Python scripts and utilities.
*   `data/`: JSON schema definitions and other static data files.
*   `uploads/`: Directory for uploaded files and generated reports (configured via `CPS_UPLOAD_DIR`).
*   `docs/`: Documentation for various tools.

## Setup and Installation

This project uses Poetry for Python dependency management and npm/Yarn for Node.js dependencies.

### Prerequisites

*   Python 3.9+
*   Node.js (LTS recommended)
*   Poetry (install with `pip install poetry`)

### Backend Setup

1.  **Install Python Dependencies:**
    ```bash
    poetry install
    ```
2.  **Activate Poetry Shell (optional, but recommended):**
    ```bash
    poetry shell
    ```
    (You will need to run subsequent Python commands from within this shell, or prefix them with `poetry run`.)

### Frontend Setup

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```
2.  **Install Node.js Dependencies:**
    ```bash
    npm install
    # or yarn install
    ```
3.  **Return to the project root:**
    ```bash
    cd ..
    ```

## Running the Applications

### Running the FastAPI Backend

The FastAPI application is now centralized in `backend/main.py`.

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
This will start the backend server, typically accessible at `http://localhost:8000`.

### Running the React Frontend

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```
2.  **Start the development server:**
    ```bash
    npm run dev
    # or yarn dev
    ```
    This will usually open the frontend in your browser at `http://localhost:5173` (or another available port).
3.  **Return to the project root:**
    ```bash
    cd ..
    ```

## Key Tools and Functionality

### MRR Tool (Material Reconciliation Report)

*   **GUI Version:** Located at `scripts/MattsMRR.py`. This is a standalone Tkinter application for generating MRR reports.
    ```bash
    python scripts/MattsMRR.py
    ```
*   **API Version:** Exposed via the FastAPI backend at `/api/mrr-process`. This endpoint uses the same core logic as the GUI version but provides a programmatic interface for file uploads and report generation.

### SPIDA QC Checker

*   **CLI Tool:** Located at `scripts/spidaqc.py`. This script performs quality control checks on SPIDAcalc and Katapult JSON files.
    ```bash
    python scripts/spidaqc.py <path_to_spida_json> [path_to_kata_json]
    ```

### Other Scripts

The `scripts/` directory contains other utilities like `cover_sheet_tool.py`, `pole_comparison_tool.py`, etc. Refer to their individual docstrings or comments for specific usage.

## Configuration

Application settings are managed via `cps_tools/settings.py` using Pydantic. You can override default settings using environment variables prefixed with `CPS_` (e.g., `CPS_UPLOAD_DIR`) or by creating a `.env` file in the project root.

Example `.env` file:
```
CPS_DEBUG=True
CPS_UPLOAD_DIR=./my_custom_uploads
CPS_CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173"]
```

## Development Notes

*   **Code Style:** (Consider adding details about Black, Flake8, ESLint, Prettier if used)
*   **Testing:** (Mention `pytest` for backend, Jest/React Testing Library for frontend, and how to run tests if applicable)
