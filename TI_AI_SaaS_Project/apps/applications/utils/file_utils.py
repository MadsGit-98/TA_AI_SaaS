"""
File utilities for Applications app
"""

import hashlib
from typing import Optional


def calculate_file_hash(file_content: bytes) -> str:
    """
    Calculate the SHA-256 hash of the given file bytes.
    
    Parameters:
        file_content (bytes): Raw file bytes to be hashed.
    
    Returns:
        str: 64-character lowercase hexadecimal SHA-256 digest of the input bytes.
    """
    return hashlib.sha256(file_content).hexdigest()
