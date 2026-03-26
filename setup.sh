#!/bin/bash
# Setup and Run script for Olympus

set -e

echo "🚀 Setting up Olympus..."

# 1. Start Docker services (PostgreSQL + Redis)
echo "📦 Starting Docker services..."
docker-compose up -d

# 2. Setup Python Backend
echo "🐍 Setting up Python Backend..."
cd backend

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate venv (works in git bash / wsl / standard bash)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    # Windows native bash (Git Bash)
    source venv/Scripts/activate
else
    # Linux/Mac/WSL
    source venv/bin/activate
fi

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# 3. Setup Frontend (User already ran npm install for renderer, but ensuring main app is installed)
echo "⚛️ Setting up Electron Frontend..."
cd ..
npm install

echo "✅ Setup complete!"
echo ""
echo "To run the application, open two separate terminals:"
echo ""
echo "Terminal 1 (Backend):"
echo "  cd backend"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo "  source venv/Scripts/activate"
else
    echo "  source venv/bin/activate"
fi
echo "  uvicorn main:app --host 0.0.0.0 --port 8000"
echo ""
echo "Terminal 2 (Frontend):"
echo "  cd ."
echo "  npm run dev"
echo ""
