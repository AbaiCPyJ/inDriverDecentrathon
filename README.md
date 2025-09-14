# InDrive Geotracks Dashboard


## Quick Start

### Prerequisites
- Node.js 16+ and npm/pnpm
- Python 3.8-3.11 (Python 3.13 not supported yet due to pandas compatibility)
- Modern web browser

### Option 1: Run with Virtual Environment (Recommended)

```bash
# From project root
./run-dev.sh
```

This script will:
- Create a Python virtual environment
- Install all dependencies
- Start both frontend and backend servers

### Option 2: Run with System Python

```bash
# From project root
./run-dev-simple.sh
```

This uses your system Python installation without creating a virtual environment.

### Option 3: Manual Setup with Virtual Environment

#### Backend with venv
```bash
cd backend

# Create virtual environment with Python 3.10 or 3.11
python3.10 -m venv venv  # or python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run the server
python main.py
```

#### Frontend
```bash
cd frontend
npm install  # or pnpm install
npm run dev  # or pnpm dev
```

### Option 4: Run Services with System Python

#### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```

#### Frontend
```bash
cd frontend
npm install  # or pnpm install
npm run dev  # or pnpm dev
```

## Usage

1. Open http://localhost:3000 in your browser
2. Upload a CSV file using the sidebar
3. Select the type of analysis (Popular Routes, Endpoints, Speed, etc.)
4. Click "Run Analysis" to process the data
5. View the generated heatmap visualization

## CSV File Format

The CSV file must contain the following columns:
- `randomized_id` - Unique identifier for each vehicle
- `lat` - Latitude
- `lng` - Longitude  
- `alt` - Altitude
- `spd` - Speed in m/s (automatically converted to km/h)
- `azm` - Azimuth/bearing

