from pathlib import Path
import requests
from collections import defaultdict

def handler():
    p = Path("x")
    x = requests.get("http://example.com")
    y = defaultdict(list)
    return p, x, y