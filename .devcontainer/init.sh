#!/bin/bash
set -e

echo "Setting up Regulatory Intake Triage Agent Codespace..."

# Create .env from defaults or Codespace secrets
if [ ! -f ".env" ]; then
  echo "Creating .env file..."
  cat > .env << 'EOF'
# Gemini API key (from Codespace secret if set, else empty)
GEMINI_API_KEY=${GEMINI_API_KEY:-}

# Set to 'true' to enable Gemini for preflight/triage analysis
# Default: false (runs deterministically offline)
USE_GEMINI=false

# Optional: Gemini model name (defaults to gemini-flash-latest if not set)
GEMINI_MODEL=gemini-flash-latest
EOF

  # If GEMINI_API_KEY is set in the environment (from Codespace secret),
  # substitute it into .env
  if [ -n "${GEMINI_API_KEY}" ]; then
    sed -i "s/GEMINI_API_KEY=.*/GEMINI_API_KEY=${GEMINI_API_KEY}/" .env
    echo "✓ GEMINI_API_KEY loaded from Codespace secret"
  fi
fi

# Create venv and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "✓ Codespace setup complete!"
echo ""
echo "Quick start:"
echo "  source .venv/bin/activate"
echo "  python run.py preflight data/intake_records.json    # preflight only"
echo "  python run.py all data/intake_records.json          # preflight + triage"
echo "  python run.py serve                                 # serve artifacts/"
echo ""
echo "To enable Gemini:"
echo "  1. Add GEMINI_API_KEY as a Codespace secret (Settings → Secrets and variables → Codespaces)"
echo "  2. Recreate the Codespace or manually: sed -i 's/USE_GEMINI=.*/USE_GEMINI=true/' .env"
echo ""
