"""
Resume Parsing Service

Per Constitution §4: Decoupled services located in project root services/ directory.

This service handles:
1. PDF text extraction using PyPDF2
2. Docx text extraction using python-docx
3. Confidential information filtering (PII redaction)
"""

import re
import hashlib
from typing import Optional
from pypdf import PdfReader
from docx import Document
from io import BytesIO
import phonenumbers


class ResumeParserService:
    """
    Service for extracting text from PDF and Docx resume files.
    """
    
    @staticmethod
    def extract_text_from_pdf(file_content: bytes) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            file_content: Raw bytes of the PDF file
            
        Returns:
            Extracted text content
        """
        reader = PdfReader(BytesIO(file_content))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    
    @staticmethod
    def extract_text_from_docx(file_content: bytes) -> str:
        """
        Extract text from a Docx file.
        
        Args:
            file_content: Raw bytes of the Docx file
            
        Returns:
            Extracted text content
        """
        doc = Document(BytesIO(file_content))
        text = ""
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text += paragraph.text + "\n"
        return text.strip()
    
    @staticmethod
    def calculate_file_hash(file_content: bytes) -> str:
        """
        Calculate SHA-256 hash of file content for duplication detection.
        
        Args:
            file_content: Raw bytes of the file
            
        Returns:
            Hexadecimal hash string (64 characters)
        """
        return hashlib.sha256(file_content).hexdigest()


class ConfidentialInfoFilter:
    """
    Filter to redact confidential personal information from parsed resume text.
    
    Per specification FR-016: Confidential info (phone, email, addresses) must not
    be stored in parsed text for AI analysis, but contact info is stored separately
    for communication purposes.
    """
    
    # Email pattern
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    # Phone pattern (simple, will be enhanced by phonenumbers library)
    PHONE_PATTERN = r'\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b'
    
    # SSN pattern
    SSN_PATTERN = r'\b\d{3}-\d{2}-\d{4}\b'
    
    # Date of birth pattern (MM/DD/YYYY or MM-DD-YYYY)
    DOB_PATTERN = r'\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/](19|20)\d{2}\b'
    
    # Street address pattern (simplified)
    ADDRESS_PATTERN = r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl)\b,?\s*[A-Za-z\s]+,?\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?\b'
    
    @classmethod
    def redact(cls, text: str) -> str:
        """
        Redact all confidential information from text.
        
        Args:
            text: Raw parsed text from resume
            
        Returns:
            Text with PII redacted
        """
        # Redact emails
        text = cls._redact_emails(text)
        
        # Redact phone numbers
        text = cls._redact_phones(text)
        
        # Redact SSNs
        text = cls._redact_ssn(text)
        
        # Redact dates of birth
        text = cls._redact_dates_of_birth(text)
        
        # Redact addresses
        text = cls._redact_addresses(text)
        
        return text
    
    @classmethod
    def _redact_emails(cls, text: str) -> str:
        """Redact email addresses."""
        return re.sub(cls.EMAIL_PATTERN, '[EMAIL_REDACTED]', text, flags=re.IGNORECASE)
    
    @classmethod
    def _redact_phones(cls, text: str) -> str:
        """
        Redact phone numbers using phonenumbers library for better accuracy.
        """
        def replace_phone(match):
            phone_str = match.group(0)
            try:
                # Try to parse the phone number
                parsed = phonenumbers.parse(phone_str, None)
                if phonenumbers.is_valid_number(parsed):
                    return '[PHONE_REDACTED]'
            except phonenumbers.NumberParseException:
                pass
            # If parsing fails, use regex match anyway
            return '[PHONE_REDACTED]'
        
        return re.sub(cls.PHONE_PATTERN, replace_phone, text)
    
    @classmethod
    def _redact_ssn(cls, text: str) -> str:
        """Redact Social Security Numbers."""
        return re.sub(cls.SSN_PATTERN, '[SSN_REDACTED]', text)
    
    @classmethod
    def _redact_dates_of_birth(cls, text: str) -> str:
        """Redact dates of birth."""
        return re.sub(cls.DOB_PATTERN, '[DOB_REDACTED]', text)
    
    @classmethod
    def _redact_addresses(cls, text: str) -> str:
        """Redact street addresses."""
        return re.sub(cls.ADDRESS_PATTERN, '[ADDRESS_REDACTED]', text, flags=re.IGNORECASE)
