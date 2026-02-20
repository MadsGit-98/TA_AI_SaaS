"""
File utilities for Applications app
"""

import hashlib
from typing import Optional


def calculate_file_hash(file_content: bytes) -> str:
    """
    Calculate SHA-256 hash of file content.
    
    Args:
        file_content: Raw file bytes
        
    Returns:
        Hexadecimal hash string (64 characters)
    """
    return hashlib.sha256(file_content).hexdigest()
