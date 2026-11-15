#!/usr/bin/env python3
import sys
from pathlib import Path

# Add services/search/src/rag to path or import directly
sys.path.insert(0, str(Path(__file__).resolve().parent / "services" / "search" / "src" / "rag"))

from nasa_rag import main

if __name__ == "__main__":
    main()
