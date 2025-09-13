#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the project root
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Start backend server (using system Python)
echo -e "${GREEN}Starting backend server...${NC}"
cd backend
python3 main.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Start frontend
echo -e "${GREEN}Starting frontend...${NC}"
cd ../frontend

# Install frontend dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Stopping servers...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    
    echo -e "${GREEN}Servers stopped successfully${NC}"
    exit
}

# Set up trap to cleanup on Ctrl+C
trap cleanup INT

echo -e "\n${GREEN}Development servers running:${NC}"
echo -e "- Backend:  ${GREEN}http://localhost:8000${NC}"
echo -e "- Frontend: ${GREEN}http://localhost:3000${NC}"
echo -e "- API Docs: ${GREEN}http://localhost:8000/docs${NC}"
echo -e "\n${YELLOW}Press Ctrl+C to stop both servers${NC}\n"

# Wait for both processes
wait
