#!/bin/bash
# Quick Install Script for Persistent AI Memory System
# Works on Linux, macOS, and Windows (with Git Bash)

echo "🚀 Installing Persistent AI Memory System..."
echo "=" * 50

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "💡 Please install Python 3.8+ and try again."
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Found Python $python_version"

# Clone the repository
echo "📥 Cloning repository..."
git clone https://github.com/gabrielzaldivar06/persistent-ai-memory.git
cd persistent-ai-memory

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

# Install the package
echo "🔧 Installing Persistent AI Memory System..."
pip3 install -e .

# Run health check
echo "🏥 Running health check..."
python3 -c "
import asyncio
from ai_memory_core import PersistentAIMemorySystem

async def test():
    system = PersistentAIMemorySystem()
    health = await system.get_system_health()
    print(f'System status: {health[\"status\"]}')
    print('✅ Installation successful!')

asyncio.run(test())
"

echo ""
echo "🎉 Installation complete!"
echo ""
echo "📚 Quick Start:"
echo "   python3 examples/basic_usage.py"
echo ""
echo "🧪 Run tests:"
echo "   python3 tests/test_health_check.py"
echo ""
echo "📖 Documentation:"
echo "   See README.md for detailed usage instructions"
