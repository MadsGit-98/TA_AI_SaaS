"""
WebSocket consumers for bulk upload progress tracking

Provides real-time progress updates during bulk resume upload operations.
Uses Django Channels with Redis channel layer.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

from apps.applications.models import UploadBatch

logger = logging.getLogger(__name__)


class BulkUploadConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for bulk upload progress updates.

    Clients connect to /ws/bulk-upload/<batch_id>/ to receive real-time
    progress updates for a specific upload batch.
    """

    async def connect(self):
        """Accept WebSocket connection and join the batch group."""
        # Authentication check
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            logger.warning(f'WebSocket connection denied: unauthenticated user')
            await self.close()
            return

        self.batch_id = self.scope['url_route']['kwargs']['batch_id']

        # Authorization check: verify user owns or has permission to this batch
        batch = await self._get_batch_or_none(self.batch_id)
        if batch is None:
            logger.warning(f'WebSocket connection denied: batch {self.batch_id} not found')
            await self.close()
            return

        # Compare user IDs (not objects) to avoid sync database access
        if batch.uploaded_by_id != user.id:
            logger.warning(f'WebSocket connection denied: user {user.id} not authorized for batch {self.batch_id}')
            await self.close()
            return

        self.room_group_name = f'bulk_upload_{self.batch_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        logger.debug(f'WebSocket connected for batch {self.batch_id}')

    async def _get_batch_or_none(self, batch_id):
        """Fetch UploadBatch by ID, return None if not found."""
        try:
            return await sync_to_async(UploadBatch.objects.get)(id=batch_id)
        except UploadBatch.DoesNotExist:
            return None
    
    async def disconnect(self, close_code):
        """Leave the batch group on disconnect."""
        # Leave room group (only if attributes were set)
        if hasattr(self, 'room_group_name') and hasattr(self, 'channel_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

        # Log disconnect with batch_id if available
        if hasattr(self, 'batch_id'):
            logger.debug(f'WebSocket disconnected for batch {self.batch_id} (code: {close_code})')
        else:
            logger.debug(f'WebSocket disconnected (code: {close_code})')
    
    async def receive(self, text_data):
        """
        Receive message from WebSocket.
        Currently we only send progress updates, but this can be extended
        to receive commands from the client.
        """
        try:
            data = json.loads(text_data)
            logger.debug(f'Received message for batch {self.batch_id}: {data}')
        except json.JSONDecodeError:
            logger.warning(f'Invalid JSON received: {text_data}')
    
    async def upload_progress(self, event):
        """
        Handle file upload progress messages.
        
        Event format:
        {
            'type': 'upload_progress',
            'file_id': str,
            'filename': str,
            'status': str,
            'progress_percent': int (optional)
        }
        """
        await self.send(text_data=json.dumps({
            'type': 'file_progress',
            'file_id': event.get('file_id'),
            'filename': event.get('filename'),
            'status': event.get('status'),
            'progress_percent': event.get('progress_percent', 100)
        }))
    
    async def batch_progress(self, event):
        """
        Handle batch-level progress messages.
        
        Event format:
        {
            'type': 'batch_progress',
            'files_uploaded': int,
            'files_total': int,
            'files_validated': int,
            'files_with_errors': int,
            'status': str
        }
        """
        await self.send(text_data=json.dumps({
            'type': 'batch_progress',
            'files_uploaded': event.get('files_uploaded', 0),
            'files_total': event.get('files_total', 0),
            'files_validated': event.get('files_validated', 0),
            'files_with_errors': event.get('files_with_errors', 0),
            'status': event.get('status', 'unknown')
        }))
    
    async def validation_complete(self, event):
        """
        Handle validation complete messages.
        
        Event format:
        {
            'type': 'validation_complete',
            'total_files': int,
            'valid_files': int,
            'duplicates': int,
            'failed_files': int,
            'ready_for_review': bool
        }
        """
        await self.send(text_data=json.dumps({
            'type': 'validation_complete',
            'total_files': event.get('total_files', 0),
            'valid_files': event.get('valid_files', 0),
            'duplicates': event.get('duplicates', 0),
            'failed_files': event.get('failed_files', 0),
            'ready_for_review': event.get('ready_for_review', False)
        }))
    
    async def upload_error(self, event):
        """
        Handle error messages.

        Event format:
        {
            'type': 'upload_error',
            'file_id': str (optional),
            'error': str,
            'message': str
        }
        """
        await self.send(text_data=json.dumps({
            'type': 'error',
            'file_id': event.get('file_id'),
            'error': event.get('error', 'unknown_error'),
            'message': event.get('message', 'An error occurred')
        }))

    async def processing_started(self, event):
        """
        Handle processing started messages.

        Event format:
        {
            'type': 'processing_started',
            'batch_id': str,
            'total_files': int
        }
        """
        await self.send(text_data=json.dumps({
            'type': 'processing_started',
            'batch_id': event.get('batch_id'),
            'total_files': event.get('total_files', 0)
        }))

    async def file_success(self, event):
        """
        Handle successful file processing messages.

        Event format:
        {
            'type': 'file_success',
            'file_id': str,
            'filename': str,
            'applicant_id': str,
            'extracted_data': {
                'first_name': str,
                'last_name': str,
                'email': str,
                'phone': str
            }
        }
        """
        await self.send(text_data=json.dumps({
            'type': 'file_success',
            'file_id': event.get('file_id'),
            'filename': event.get('filename'),
            'applicant_id': event.get('applicant_id'),
            'extracted_data': event.get('extracted_data', {})
        }))

    async def file_error(self, event):
        """
        Handle file processing error messages.

        Event format:
        {
            'type': 'file_error',
            'file_id': str,
            'filename': str,
            'error_code': str,
            'message': str
        }
        """
        await self.send(text_data=json.dumps({
            'type': 'file_error',
            'file_id': event.get('file_id'),
            'filename': event.get('filename'),
            'error_code': event.get('error_code', 'processing_failed'),
            'message': event.get('message', 'An error occurred while processing the file')
        }))

    async def processing_complete(self, event):
        """
        Handle processing complete messages.

        Event format:
        {
            'type': 'processing_complete',
            'batch_id': str,
            'summary': {
                'applicants_created': int,
                'files_failed': int,
                'total': int
            }
        }
        """
        await self.send(text_data=json.dumps({
            'type': 'processing_complete',
            'batch_id': event.get('batch_id'),
            'summary': event.get('summary', {})
        }))

    async def processing_failed(self, event):
        """
        Handle processing failure messages.

        Event format:
        {
            'type': 'processing_failed',
            'batch_id': str,
            'error': str,
            'failed_count': int
        }
        """
        await self.send(text_data=json.dumps({
            'type': 'processing_failed',
            'batch_id': event.get('batch_id'),
            'error': event.get('error', 'Processing failed'),
            'failed_count': event.get('failed_count', 0)
        }))
