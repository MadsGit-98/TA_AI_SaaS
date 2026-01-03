import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

User = get_user_model()

logger = logging.getLogger(__name__)
class TokenNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Check if user is authenticated before accepting the connection
        if self.scope["user"].is_authenticated:
            # Set user_id and add to group before accepting
            self.user_id = self.scope["user"].id
            await self.channel_layer.group_add(
                f"token_notifications_{self.user_id}",
                self.channel_name
            )
            # Accept the WebSocket connection only if authenticated
            await self.accept()
        else:
            # Close the connection with a 403-equivalent for unauthenticated users
            await self.close(code=403)

    async def disconnect(self, close_code):
        # Remove user from group when disconnecting
        if hasattr(self, 'user_id') and self.user_id is not None:
            await self.channel_layer.group_discard(
                f"token_notifications_{self.user_id}",
                self.channel_name
            )

    # Receive message from WebSocket
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json.get('message')
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))
            return

        if message == 'token_refresh_needed':
            # Only send refresh notification if user is authenticated (user_id is not None)
            if self.user_id is not None:
                # Send refresh notification to the group
                await self.channel_layer.group_send(
                    f"token_notifications_{self.user_id}",
                    {
                        'type': 'token_refresh_notification',
                        'message': 'Token refresh needed'
                    }
                )
            else:
                # If user is not authenticated, send an error message
                await self.send(text_data=json.dumps({
                    'error': 'Authentication required for this action'
                }))

    # Receive message from room group
    async def token_refresh_notification(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message']
        }))

    # Receive refresh_tokens message for new format compatibility
    async def refresh_tokens(self, event):
        # Send message to WebSocket in the new format
        await self.send(text_data=json.dumps({
            'type': 'refresh_tokens',
            'message': event['message']
        }))

    # Method to notify a specific user
    @classmethod
    def notify_user(cls, user_id, message="REFRESH"):
        """
        Notify a specific user that their token needs to be refreshed
        """
        channel_layer = get_channel_layer()

        # Early return if channel layer is not available
        if channel_layer is None:
            logger.warning("Channel layer is not available, cannot send notification")
            return

        try:
            async_to_sync(channel_layer.group_send)(
                f"token_notifications_{user_id}",
                {
                    'type': 'refresh_tokens',
                    'message': message
                }
            )
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {str(e)}")