"""
Unit Tests for File Validation Utilities
"""

import unittest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from apps.applications.utils.file_validation import (
    validate_resume_file,
    validate_magic_bytes,
    MIN_FILE_SIZE,
    MAX_FILE_SIZE
)


class FileValidationTest(TestCase):
    """Unit tests for file validation utilities"""
    
    def test_validate_pdf_magic_bytes(self):
        """Test PDF magic bytes validation"""
        pdf_content = b'%PDF-1.4\nTest PDF content'
        result = validate_magic_bytes(pdf_content, 'pdf')
        self.assertTrue(result)
    
    def test_validate_docx_magic_bytes(self):
        """Test Docx magic bytes validation"""
        # Docx files start with PK (ZIP signature)
        docx_content = b'PK\x03\x04Test DOCX content'
        result = validate_magic_bytes(docx_content, 'docx')
        self.assertTrue(result)
    
    def test_validate_invalid_magic_bytes(self):
        """Test invalid magic bytes detection"""
        # Text file content with .pdf extension
        invalid_content = b'This is just text, not a PDF'
        result = validate_magic_bytes(invalid_content, 'pdf')
        self.assertFalse(result)
    
    def test_validate_file_too_small(self):
        """Test rejection of files below minimum size"""
        small_file = SimpleUploadedFile(
            'test.pdf',
            b'%PDF-1.4\n' + (b'A' * 100),  # Less than 50KB
            content_type='application/pdf'
        )
        
        with self.assertRaises(ValidationError) as context:
            validate_resume_file(small_file)
        
        self.assertIn('below minimum', str(context.exception))
    
    def test_validate_file_too_large(self):
        """Test rejection of files above maximum size"""
        # Create file larger than 10MB
        large_content = b'%PDF-1.4\n' + (b'A' * (11 * 1024 * 1024))
        large_file = SimpleUploadedFile(
            'test.pdf',
            large_content,
            content_type='application/pdf'
        )
        
        with self.assertRaises(ValidationError) as context:
            validate_resume_file(large_file)
        
        self.assertIn('exceeds maximum', str(context.exception))
    
    def test_validate_invalid_extension(self):
        """Test rejection of unsupported file extensions"""
        txt_file = SimpleUploadedFile(
            'test.txt',
            b'Test content ' + (b'A' * MIN_FILE_SIZE),
            content_type='text/plain'
        )
        
        with self.assertRaises(ValidationError) as context:
            validate_resume_file(txt_file)
        
        self.assertIn('Unsupported file format', str(context.exception))
    
    def test_validate_valid_pdf(self):
        """Test acceptance of valid PDF file"""
        pdf_content = b'%PDF-1.4\n' + (b'A' * MIN_FILE_SIZE)
        pdf_file = SimpleUploadedFile(
            'resume.pdf',
            pdf_content,
            content_type='application/pdf'
        )
        
        result = validate_resume_file(pdf_file)
        self.assertEqual(result.name, 'resume.pdf')
    
    def test_validate_valid_docx(self):
        """Test acceptance of valid Docx file"""
        docx_content = b'PK\x03\x04' + (b'A' * MIN_FILE_SIZE)
        docx_file = SimpleUploadedFile(
            'resume.docx',
            docx_content,
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
        result = validate_resume_file(docx_file)
        self.assertEqual(result.name, 'resume.docx')


class FormatFileSizeTest(TestCase):
    """Tests for file size formatting utility"""
    
    def test_format_bytes(self):
        """Test formatting bytes"""
        from apps.applications.utils.file_validation import format_file_size
        self.assertEqual(format_file_size(500), '500B')
    
    def test_format_kilobytes(self):
        """Test formatting kilobytes"""
        from apps.applications.utils.file_validation import format_file_size
        self.assertEqual(format_file_size(1024), '1.0KB')
        self.assertEqual(format_file_size(51200), '50.0KB')
    
    def test_format_megabytes(self):
        """Test formatting megabytes"""
        from apps.applications.utils.file_validation import format_file_size
        self.assertEqual(format_file_size(1048576), '1.0MB')
        self.assertEqual(format_file_size(10485760), '10.0MB')


if __name__ == '__main__':
    unittest.main()
