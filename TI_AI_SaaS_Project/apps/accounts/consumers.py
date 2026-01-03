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
        """
        Handle an incoming WebSocket connection by accepting authenticated users and registering their channel in a user-specific notification group.
        
        If the connection's scope contains an authenticated user, the consumer records the user's id and adds the connection to that user's "token_notifications_{user_id}" group, then accepts the WebSocket. If the user is not authenticated, the connection is closed with a 403-equivalent code.
        """
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
        """
        Disconnect handler that removes this connection from the user's token notification group if a user_id is set.
        
        Parameters:
            close_code (int): WebSocket close code provided by the connection; not used by this method.
        """
        if hasattr(self, 'user_id') and self.user_id is not None:
            await self.channel_layer.group_discard(
                f"token_notifications_{self.user_id}",
                self.channel_name
            )

    # Receive message from WebSocket
    async def receive(self, text_data):
        """
        Handle incoming WebSocket text messages for token refresh requests.
        
        Parses `text_data` as JSON and reacts to a `message` value of `"token_refresh_needed"`:
        - If the payload is invalid JSON, sends {"error": "Invalid JSON format"} back to the client.
        - If the message is `"token_refresh_needed"` and the consumer is authenticated (has `self.user_id`), sends a group message to "token_notifications_{user_id}" with type `"token_refresh_notification"` and message `"Token refresh needed"`.
        - If the message is `"token_refresh_needed"` but the consumer is not authenticated, sends {"error": "Authentication required for this action"}.
        
        Parameters:
            text_data (str): JSON-formatted text received over the WebSocket, expected to contain a top-level `message` key.
        """
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
        """
        Forward a token refresh notification payload from a channel layer event to the WebSocket client.
        
        Parameters:
            event (dict): Channel layer event containing a 'message' key whose value will be sent to the client as JSON under the 'message' field.
        """
        await self.send(text_data=json.dumps({
            'message': event['message']
        }))

    # Receive refresh_tokens message for new format compatibility
    async def refresh_tokens(self, event):
        # Send message to WebSocket in the new format
        """
        Forward a refresh_tokens event payload to the WebSocket using the 'refresh_tokens' message format.
        
        Parameters:
            event (dict): Event payload expected to contain a 'message' key whose value will be sent to the client.
        """
        await self.send(text_data=json.dumps({
            'type': 'refresh_tokens',
            'message': event['message']
        }))

    # Method to notify a specific user
    @classmethod
    def notify_user(cls, user_id, message="REFRESH"):
        """
        Notify a user that their tokens should be refreshed.
        
        Sends a group message to the user's token_notifications group using the channel layer. If the channel layer is unavailable the call logs a warning and returns without sending; any exception raised while sending is logged as an error.
        
        Parameters:
            user_id: Identifier of the target user; used to form the user's notification group name.
            message (str): Payload message to include with the notification; defaults to "REFRESH".
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