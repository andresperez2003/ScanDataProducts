import sys
from pathlib import Path

# Agregar src/ al path para que los imports funcionen
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
