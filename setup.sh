#!/bin/bash
# Setup script for Agent-Lock development environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Agent-Lock Setup Script"
echo "=========================="

# Create backend venv
echo "Setting up backend..."
cd backend
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cd ..

# Create frontend node_modules
echo "Setting up frontend..."
cd frontend
npm install
cd ..

# Initialize database
echo "Initializing database..."
cd backend
python -c "from database import init_db; init_db(); print('Database initialized')"
cd ..

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Backend: cd backend; source venv/bin/activate; python app.py"
echo "2. Frontend: cd frontend; npm run dev"
echo "3. Open http://localhost:3000"
echo ""
echo "Demo login: Use any email and password from test_usage.txt"
