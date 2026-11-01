"""
pytest configuration: add the lambda/bedrock_integration directory to sys.path
so that handler.py can be imported directly without the 'lambda' package prefix
(which conflicts with the Python keyword).
"""
import sys
from pathlib import Path

_COMMON_LAYER = Path(__file__).parents[3] / "layers" / "common"

# Add the bedrock_integration directory itself to sys.path so tests can
# do: import handler  (instead of: from lambda.bedrock_integration import handler)
if str(_COMMON_LAYER) not in sys.path:
    sys.path.insert(0, str(_COMMON_LAYER))

sys.path.insert(0, str(Path(__file__).parent.parent))
