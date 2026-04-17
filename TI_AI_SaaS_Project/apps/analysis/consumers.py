"""
WebSocket Consumers for AI Analysis Status Notifications

This module contains the AnalysisNotificationConsumer class for broadcasting
real-time analysis status updates to connected clients.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class AnalysisNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for broadcasting AI analysis status updates.
    
    Supports real-time notifications for:
    - Analysis progress updates (milestone checkpoints)
    - Analysis completion
    - Analysis cancellation
    - Analysis failure
    
    Group naming convention: analysis_{job_id}
    """
    
    async def connect(self):
        """
        Accept WebSocket connection if user is authenticated.
        User subscribes to specific jobs via receive() method.
        
        Note: Since only one analysis can run per user at a time,
        we don't auto-subscribe - client explicitly subscribes to the job being analyzed.
        """
        if self.scope["user"].is_authenticated:
            self.user_id = str(self.scope["user"].id)
            # Accept the connection
            await self.accept()
            logger.info(f"WebSocket connected for user {self.user_id}")
        else:
            # Close connection for unauthenticated users
            logger.warning("WebSocket connection rejected - unauthenticated user")
            await self.close(code=4003)
    
    async def disconnect(self, close_code):
        """
        Remove user from all analysis groups when disconnecting.
        """
        if hasattr(self, 'subscribed_groups'):
            for group_name in self.subscribed_groups:
                await self.channel_layer.group_discard(
                    group_name,
                    self.channel_name
                )
                logger.info(f"Removed from group: {group_name}")
        
        logger.info(f"WebSocket disconnected for user {getattr(self, 'user_id', 'unknown')}")
    
    async def subscribe_to_job(self, job_id):
        """
        Subscribe user to analysis updates for a specific job.

        Args:
            job_id: UUID string of the job listing

        Returns:
            bool: True on successful subscription, False on any error/failure
        """
        from apps.jobs.models import JobListing
        from django.core.exceptions import ObjectDoesNotExist

        # Authorization check: verify user has access to this job
        try:
            job = await JobListing.objects.aget(id=job_id)
            # Check if user is the owner or has staff privileges
            if str(job.created_by_id) != self.user_id and not self.scope["user"].is_staff:
                logger.warning(f"User {self.user_id} attempted to subscribe to unauthorized job {job_id}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error_code': 'PERMISSION_DENIED',
                    'error_message': 'You do not have permission to access this job'
                }))
                return False
        except ObjectDoesNotExist:
            logger.warning(f"Job {job_id} not found for subscription by user {self.user_id}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error_code': 'JOB_NOT_FOUND',
                'error_message': 'Job not found'
            }))
            return False
        except Exception as e:
            logger.error(f"Error checking job authorization: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error_code': 'INTERNAL_ERROR',
                'error_message': 'Failed to verify job access'
            }))
            return False

        if not hasattr(self, 'subscribed_groups'):
            self.subscribed_groups = set()

        group_name = f"analysis_{job_id}"

        if group_name not in self.subscribed_groups:
            await self.channel_layer.group_add(
                group_name,
                self.channel_name
            )
            self.subscribed_groups.add(group_name)
            logger.info(f"User {self.user_id} subscribed to job {job_id}")
        
        return True
    
    async def unsubscribe_from_job(self, job_id):
        """
        Unsubscribe user from analysis updates for a specific job.

        Args:
            job_id: UUID string of the job listing
        """
        group_name = f"analysis_{job_id}"

        if hasattr(self, 'subscribed_groups') and group_name in self.subscribed_groups:
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name
            )
            self.subscribed_groups.discard(group_name)
            logger.info(f"User {self.user_id} unsubscribed from job {job_id}")
    
    async def receive(self, text_data):
        """
        Receive message from WebSocket - handles subscription requests.

        Expected message format:
        {
            "type": "subscribe",
            "job_id": "uuid-string"
        }
        """
        try:
            data = json.loads(text_data)

            if data.get('type') == 'subscribe':
                job_id = data.get('job_id')
                if job_id:
                    # Subscribe and only send ack if successful
                    success = await self.subscribe_to_job(job_id)
                    if success:
                        # Send acknowledgment with job_id inside data object
                        await self.send(text_data=json.dumps({
                            'type': 'subscribed',
                            'data': {
                                'job_id': job_id
                            }
                        }))

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {text_data}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    # Message handlers - receive from channel layer, send to WebSocket
    
    async def analysis_progress(self, event):
        """
        Handle analysis progress notification.
        
        Event format:
        {
            'type': 'analysis_progress',
            'data': {
                'job_id': str,
                'status': 'processing',
                'progress_percentage': int,
                'processed_count': int,
                'total_count': int,
                'message': str (optional),
                'timestamp': str (ISO-8601)
            }
        }
        """
        await self.send(text_data=json.dumps(event))
    
    async def analysis_completed(self, event):
        """
        Handle analysis completion notification.
        
        Event format:
        {
            'type': 'analysis_completed',
            'data': {
                'job_id': str,
                'status': 'completed',
                'processed_count': int,
                'total_count': int,
                'analyzed_count': int,
                'unprocessed_count': int,
                'timestamp': str (ISO-8601)
            }
        }
        """
        await self.send(text_data=json.dumps(event))
    
    async def analysis_cancelled(self, event):
        """
        Handle analysis cancellation notification.
        
        Event format:
        {
            'type': 'analysis_cancelled',
            'data': {
                'job_id': str,
                'status': 'cancelled',
                'processed_count': int,
                'total_count': int,
                'preserved_count': int,
                'timestamp': str (ISO-8601)
            }
        }
        """
        await self.send(text_data=json.dumps(event))
    
    async def analysis_failed(self, event):
        """
        Handle analysis failure notification.
        
        Event format:
        {
            'type': 'analysis_failed',
            'data': {
                'job_id': str,
                'status': 'failed',
                'error_code': str,
                'error_message': str,
                'processed_count': int,
                'total_count': int,
                'timestamp': str (ISO-8601)
            }
        }
        """
        await self.send(text_data=json.dumps(event))
