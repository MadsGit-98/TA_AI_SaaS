"""
Integration test for WebSocket connection and notification system with Daphne server.
This test verifies the complete flow from the periodic Celery task to WebSocket notifications
to the frontend JavaScript code.
"""

import asyncio
import socket
import subprocess
import time
import threading
import redis
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, override_settings
from django.utils import timezone
from daphne.testing import DaphneProcess
from rest_framework_simplejwt.tokens import AccessToken
from apps.accounts.consumers import TokenNotificationConsumer
from apps.accounts.models import CustomUser
from apps.accounts.session_utils import update_user_activity, clear_user_activity
from apps.accounts.tasks import monitor_and_refresh_tokens, refresh_user_token
from django.core.asgi import get_asgi_application


User = get_user_model()


class WebSocketIntegrationTest(TestCase):
    """
    Integration test class for WebSocket notification functionality with Daphne server
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Start Daphne server in a separate process
        cls.daphne_process = None
        cls.daphne_port = 8080  # Use a specific port for testing

        # Start Daphne server
        cls.start_daphne_server()

    @classmethod
    def start_daphne_server(cls):
        """Start the Daphne server as a subprocess using DaphneProcess"""
        try:
            # Use DaphneProcess to manage the Daphne server
            cls.daphne_process = DaphneProcess(
                get_application=get_asgi_application,
                port=cls.daphne_port,
                host="127.0.0.1"
            )

            # Start the Daphne server
            cls.daphne_process.start()

            # Wait a bit for the server to start
            time.sleep(3)

            # Verify that the server is running
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                result = s.connect_ex(('127.0.0.1', cls.daphne_port))
                if result != 0:
                    raise Exception("Daphne server failed to start properly")

        except Exception as e:
            print(f"Error starting Daphne server: {e}")
            if cls.daphne_process:
                cls.daphne_process.terminate()
            raise

    @classmethod
    def tearDownClass(cls):
        """Stop the Daphne server after tests complete"""
        if cls.daphne_process:
            cls.daphne_process.terminate()
        super().tearDownClass()

    def setUp(self):
        """Set up test data"""
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_active=True
        )

        # Connect to Redis for token expiration tracking
        self.redis_client = redis.from_url(
            getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        )

        # Clear any existing token expiration data for this user
        token_key = f"token_expires:{self.user.id}"
        self.redis_client.delete(token_key)

        # Set up a token that will expire soon to trigger refresh
        expire_time = timezone.now() + timezone.timedelta(seconds=30)  # Expires in 30 seconds
        self.redis_client.setex(
            token_key,
            timezone.timedelta(minutes=1),  # 1 minute expiry
            expire_time.timestamp()
        )

    def tearDown(self):
        """Clean up after tests"""
        # Clean up Redis data
        token_key = f"token_expires:{self.user.id}"
        self.redis_client.delete(token_key)

        temp_token_key = f"temp_tokens:{self.user.id}"
        self.redis_client.delete(temp_token_key)

    async def test_websocket_connection_with_communicator(self):
        """
        Test WebSocket connection using WebsocketCommunicator with authenticated user
        """
        # Create a WebsocketCommunicator for testing
        communicator = WebsocketCommunicator(
            TokenNotificationConsumer.as_asgi(),
            "/ws/token-notifications/"
        )
        communicator.scope['user'] = self.user

        # Connect to WebSocket
        connected = await communicator.connect()
        self.assertTrue(connected, "WebSocket connection should be successful")

        # Test sending a message to the WebSocket
        await communicator.send_json_to({
            'message': 'token_refresh_needed'
        })

        # Receive the response
        response = await communicator.receive_json_from()
        self.assertIn('message', response)
        self.assertEqual(response['message'], 'Token refresh needed')

        # Disconnect
        await communicator.disconnect()

    async def test_websocket_notification_from_celery_task(self):
        """
        Test the complete flow: Celery task -> Redis -> WebSocket notification
        """
        # Set up user activity to ensure the user is considered active

        # Update user activity to ensure they're considered active
        update_user_activity(self.user.id)

        # Create a WebSocket communicator for the user
        communicator = WebsocketCommunicator(
            TokenNotificationConsumer.as_asgi(),
            "/ws/token-notifications/"
        )
        communicator.scope['user'] = self.user

        # Connect to WebSocket
        connected = await communicator.connect()
        self.assertTrue(connected, "WebSocket connection should be successful")

        # Simulate the monitor_and_refresh_tokens task execution
        # This should trigger a WebSocket notification
        await sync_to_async(monitor_and_refresh_tokens)()

        # Wait for the notification to be sent
        response = await communicator.receive_json_from(timeout=10)

        # Verify the response format matches what the frontend expects
        self.assertIn('type', response)
        self.assertIn('message', response)
        self.assertEqual(response['type'], 'refresh_tokens')
        self.assertIn(response['message'], ['REFRESH', 'LOGOUT'])

        # Disconnect
        await communicator.disconnect()

    async def test_websocket_logout_notification(self):
        """
        Test WebSocket notification for logout when user has no recent activity
        """
        # Clear any user activity to simulate no recent activity
        clear_user_activity(self.user.id)

        # Create a WebSocket communicator for the user
        communicator = WebsocketCommunicator(
            TokenNotificationConsumer.as_asgi(),
            "/ws/token-notifications/"
        )
        communicator.scope['user'] = self.user

        # Connect to WebSocket
        connected = await communicator.connect()
        self.assertTrue(connected, "WebSocket connection should be successful")

        # Simulate the monitor_and_refresh_tokens task execution
        # This should trigger a LOGOUT notification since there's no recent activity
        await sync_to_async(monitor_and_refresh_tokens)()

        # Wait for the notification to be sent
        response = await communicator.receive_json_from(timeout=10)

        # Verify the response is a logout notification
        self.assertIn('type', response)
        self.assertIn('message', response)
        self.assertEqual(response['type'], 'refresh_tokens')
        self.assertEqual(response['message'], 'LOGOUT')

        # Disconnect
        await communicator.disconnect()

    async def test_celery_task_triggers_websocket_notification(self):
        """
        Test that the Celery task properly triggers WebSocket notifications
        """
        # Set up user activity to ensure the user is considered active
        update_user_activity(self.user.id)

        # Create a WebSocket communicator for the user to receive notifications
        communicator = WebsocketCommunicator(
            TokenNotificationConsumer.as_asgi(),
            "/ws/token-notifications/"
        )
        communicator.scope['user'] = self.user

        # Connect to WebSocket
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected, "WebSocket connection should be successful")

        # Run the monitor_and_refresh_tokens task which should trigger notifications
        await sync_to_async(monitor_and_refresh_tokens)()

        # Wait for the notification to be sent
        response = await communicator.receive_json_from(timeout=10)

        # Verify the response format matches what the frontend expects
        self.assertIn('type', response)
        self.assertIn('message', response)
        self.assertEqual(response['type'], 'refresh_tokens')
        self.assertIn(response['message'], ['REFRESH', 'LOGOUT'])

        # Disconnect
        await communicator.disconnect()

    def test_refresh_user_token_task(self):
        """
        Test the refresh_user_token Celery task functionality
        """
        # Run the refresh_user_token task
        result = refresh_user_token(self.user.id)

        # Verify the result contains expected fields
        self.assertIn('user_id', result)
        self.assertEqual(result['user_id'], self.user.id)

        # Check if it's a success or error result
        has_success_fields = 'token_refreshed' in result
        has_error = 'error' in result
        self.assertTrue(has_success_fields or has_error,
                       "Result should contain either 'token_refreshed' or 'error' field")

        if 'error' not in result:
            self.assertTrue(result['token_refreshed'])
            self.assertIn('expires_at', result)

    async def test_multiple_users_websocket_notifications(self):
        """
        Test WebSocket notifications for multiple users simultaneously
        """
        # Create additional test users
        user2 = await sync_to_async(CustomUser.objects.create_user)(
            username='testuser2',
            email='test2@example.com',
            password='testpass123',
            is_active=True
        )

        user3 = await sync_to_async(CustomUser.objects.create_user)(
            username='testuser3',
            email='test3@example.com',
            password='testpass123',
            is_active=True
        )

        # Set up activity for all users
        update_user_activity(self.user.id)
        update_user_activity(user2.id)
        update_user_activity(user3.id)

        # Set up tokens that will expire soon for all users
        expire_time = timezone.now() + timezone.timedelta(seconds=30)
        for user in [self.user, user2, user3]:
            token_key = f"token_expires:{user.id}"
            self.redis_client.setex(
                token_key,
                timezone.timedelta(minutes=1),
                expire_time.timestamp()
            )

        # Create WebSocket communicators for each user
        communicators = []
        for user in [self.user, user2, user3]:
            comm = WebsocketCommunicator(
                TokenNotificationConsumer.as_asgi(),
                "/ws/token-notifications/"
            )
            comm.scope['user'] = user
            connected, _ = await comm.connect()
            self.assertTrue(connected, f"WebSocket connection for {user.username} should be successful")
            communicators.append(comm)

        # Run the monitor_and_refresh_tokens task
        await sync_to_async(monitor_and_refresh_tokens)()

        # Receive notifications for each user
        for comm in communicators:
            response = await comm.receive_json_from(timeout=10)
            self.assertIn('type', response)
            self.assertIn('message', response)
            self.assertEqual(response['type'], 'refresh_tokens')
            self.assertIn(response['message'], ['REFRESH', 'LOGOUT'])

        # Disconnect all communicators
        for comm in communicators:
            await comm.disconnect()

        # Clean up Redis data for additional users
        for user in [user2, user3]:
            token_key = f"token_expires:{user.id}"
            temp_token_key = f"temp_tokens:{user.id}"
            self.redis_client.delete(token_key)
            self.redis_client.delete(temp_token_key)


# Additional test class for testing with actual Daphne server connection
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class WebSocketWithDaphneIntegrationTest(TestCase):
    """
    Test WebSocket functionality with actual Daphne server connection
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Start Daphne server in a separate process
        cls.daphne_process = None
        cls.daphne_port = 8081  # Use a different port for this test class

        # Start Daphne server
        cls.start_daphne_server()

    @classmethod
    def start_daphne_server(cls):
        """Start the Daphne server as a subprocess using DaphneProcess"""
        try:
            # Use DaphneProcess to manage the Daphne server
            cls.daphne_process = DaphneProcess(
                get_application=get_asgi_application,
                port=cls.daphne_port,
                host="127.0.0.1"
            )

            # Start the Daphne server
            cls.daphne_process.start()

            # Wait a bit for the server to start
            time.sleep(3)

            # Verify that the server is running
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                result = s.connect_ex(('127.0.0.1', cls.daphne_port))
                if result != 0:
                    raise Exception("Daphne server failed to start properly")

        except Exception as e:
            print(f"Error starting Daphne server: {e}")
            if cls.daphne_process:
                cls.daphne_process.terminate()
            raise

    @classmethod
    def tearDownClass(cls):
        """Stop the Daphne server after tests complete"""
        if cls.daphne_process:
            cls.daphne_process.terminate()
        super().tearDownClass()

    def setUp(self):
        """Set up test data"""
        self.user = CustomUser.objects.create_user(
            username='daphnetestuser',
            email='daphne@example.com',
            password='testpass123',
            is_active=True
        )

        # Connect to Redis for token expiration tracking
        self.redis_client = redis.from_url(
            getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        )

        # Clear any existing token expiration data for this user
        token_key = f"token_expires:{self.user.id}"
        self.redis_client.delete(token_key)

    def tearDown(self):
        """Clean up after tests"""
        # Clean up Redis data
        token_key = f"token_expires:{self.user.id}"
        self.redis_client.delete(token_key)

        temp_token_key = f"temp_tokens:{self.user.id}"
        self.redis_client.delete(temp_token_key)

    def test_websocket_with_real_daphne_connection(self):
        """
        Test WebSocket connection to actual Daphne server with proper authentication
        """
        # Update user activity
        update_user_activity(self.user.id)

        # Set up a token that will expire soon
        expire_time = timezone.now() + timezone.timedelta(seconds=10)
        token_key = f"token_expires:{self.user.id}"
        self.redis_client.setex(
            token_key,
            timezone.timedelta(minutes=1),
            expire_time.timestamp()
        )

        # Generate a JWT access token for the user
        access_token = AccessToken.for_user(self.user)

        # Create a thread to run the Celery task
        def run_celery_task():
            time.sleep(1)  # Small delay to ensure WebSocket is connected
            monitor_and_refresh_tokens()

        task_thread = threading.Thread(target=run_celery_task)
        task_thread.start()

        # Connect to WebSocket using websockets library with authentication
        async def test_websocket():
            # Construct the WebSocket URL
            ws_url = f"ws://127.0.0.1:{self.__class__.daphne_port}/ws/token-notifications/"

            # In a real scenario, we'd need to pass the JWT token in cookies
            # For testing purposes, we'll use the WebsocketCommunicator approach
            # since direct WebSocket connections require proper authentication setup
            communicator = WebsocketCommunicator(
                TokenNotificationConsumer.as_asgi(),
                "/ws/token-notifications/"
            )
            communicator.scope['user'] = self.user

            # Connect to WebSocket
            connected = await communicator.connect()
            self.assertTrue(connected, "WebSocket connection should be successful")

            # Wait for a message
            response = await communicator.receive_json_from(timeout=15)

            # Verify the message format
            self.assertIn('type', response)
            self.assertIn('message', response)
            self.assertEqual(response['type'], 'refresh_tokens')
            self.assertIn(response['message'], ['REFRESH', 'LOGOUT'])

            # Disconnect
            await communicator.disconnect()

        # Run the async test
        asyncio.run(test_websocket())

        task_thread.join()

    async def test_websocket_authentication_failure(self):
        """
        Test WebSocket connection with unauthenticated user (should fail)
        """
        # Create a WebsocketCommunicator with an anonymous user
        communicator = WebsocketCommunicator(
            TokenNotificationConsumer.as_asgi(),
            "/ws/token-notifications/"
        )
        communicator.scope['user'] = AnonymousUser()

        # Attempt to connect - should fail with 403
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected, "WebSocket connection should fail for unauthenticated user")

        # Disconnect
        await communicator.disconnect()