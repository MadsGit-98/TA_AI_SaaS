"""
Integration test for the WebSocket notification system functionality.
This test verifies the token refresh notification system.
"""

from channels.testing import WebsocketCommunicator
from django.test import TestCase
from apps.accounts.consumers import TokenNotificationConsumer
from apps.accounts.models import CustomUser
from channels.layers import get_channel_layer


class WebSocketNotificationIntegrationTest(TestCase):
    """
    Integration test class for WebSocket notification functionality
    """
    
    async def test_websocket_connection_authenticated(self):
        """
        Verify that an authenticated user can establish a WebSocket connection and receive a channel-layer `refresh_tokens` notification.
        
        This test creates an active test user, injects it into the communicator scope, asserts the WebSocket connection is accepted, sends a `refresh_tokens` group message to the user's notification group, and asserts the consumer forwards the message as JSON with the expected payload.
        """
        # Create a test user
        user = await CustomUser.objects.acreate_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_active=True
        )
        
        # Create a WebsocketCommunicator instance
        communicator = WebsocketCommunicator(
            TokenNotificationConsumer.as_asgi(),
            "/ws/notifications/"
        )
        
        # Set the user in the scope for authentication
        communicator.scope['user'] = user
        
        # Test connection
        connected = await communicator.connect()
        self.assertTrue(connected)
        
        # Test receiving a refresh_tokens message
        # Send a message to the channel layer to simulate a Celery task notification
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"token_notifications_{user.id}",
            {
                'type': 'refresh_tokens',
                'message': 'REFRESH'
            }
        )
        
        # Receive the message from WebSocket
        response = await communicator.receive_json_from()
        expected_response = {
            'type': 'refresh_tokens',
            'message': 'REFRESH'
        }
        self.assertEqual(response, expected_response)
        
        # Close the connection
        await communicator.disconnect()

    async def test_websocket_connection_unauthenticated(self):
        """
        Test the WebSocket connection with an unauthenticated user (should fail)
        """
        # Create a WebsocketCommunicator instance without authentication
        communicator = WebsocketCommunicator(
            TokenNotificationConsumer.as_asgi(),
            "/ws/notifications/"
        )
        
        # Set an anonymous user in the scope
        from django.contrib.auth.models import AnonymousUser
        communicator.scope['user'] = AnonymousUser()
        
        # Test connection - should fail with 403
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
        
        # Close the connection
        await communicator.disconnect()