#!/bin/bash

# Setup script for Reddit Comment Exporter
# This script creates a virtual environment and installs the required dependencies

# Go to the script directory
cd "$(dirname "$0")"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Setup complete. To use the Reddit Comment Exporter:"
echo "1. Activate the virtual environment with: source venv/bin/activate"
echo "2. Run the script with: ./reddit_comment_exporter.py"
echo ""
echo "When finished, you can deactivate the virtual environment with: deactivate"
