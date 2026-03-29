"""
WebSocket consumers for bulk upload progress tracking

Provides real-time progress updates during bulk resume upload operations.
Uses Django Channels with Redis channel layer.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class BulkUploadConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for bulk upload progress updates.
    
    Clients connect to /ws/bulk-upload/<batch_id>/ to receive real-time
    progress updates for a specific upload batch.
    """
    
    async def connect(self):
        """Accept WebSocket connection and join the batch group."""
        self.batch_id = self.scope['url_route']['kwargs']['batch_id']
        self.room_group_name = f'bulk_upload_{self.batch_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.debug(f'WebSocket connected for batch {self.batch_id}')
    
    async def disconnect(self, close_code):
        """Leave the batch group on disconnect."""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.debug(f'WebSocket disconnected for batch {self.batch_id} (code: {close_code})')
    
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
