import os, logging
from typing import List

FILTERED_FILENAME = "data/filtered_coins.txt"

def load_filtered_symbols_from_file(filename: str = FILTERED_FILENAME) -> List[str]:
    """Load previously filtered symbols from file (if exists)."""
    try:
        with open(filename, "r") as f:
            lines = f.read().splitlines()
            symbols = [line.strip() for line in lines if line.strip()]
            if symbols:
                logging.info(f"Loaded {len(symbols)} symbols from {filename}")
            return symbols
    except FileNotFoundError:
        return []
    except Exception as e:
        logging.error(f"Error loading symbols from {filename}: {e}")
        return []

def save_filtered_symbols_to_file(symbols: List[str], filename: str = FILTERED_FILENAME):
    """Save filtered symbols to file and update global ANALYSIS_SYMBOLS."""
    global ANALYSIS_SYMBOLS
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as f:
            for sym in symbols:
                f.write(sym + "\n")
        ANALYSIS_SYMBOLS = symbols  # Update in-memory list
        logging.info(f"Saved {len(symbols)} filtered symbols to {filename}")
    except Exception as e:
        logging.error(f"Error saving symbols to {filename}: {e}")

# Initialize the global list on startup
ANALYSIS_SYMBOLS: List[str] = load_filtered_symbols_from_file()
