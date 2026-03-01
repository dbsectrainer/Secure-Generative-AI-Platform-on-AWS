"""
pytest configuration: add the lambda/bedrock_integration directory to sys.path
so that handler.py can be imported directly without the 'lambda' package prefix
(which conflicts with the Python keyword).
"""
import sys
from pathlib import Path

# Add the bedrock_integration directory itself to sys.path so tests can
# do: import handler  (instead of: from lambda.bedrock_integration import handler)
sys.path.insert(0, str(Path(__file__).parent.parent))
