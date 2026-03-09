"""Tests for dlq_consumer management command."""

import json
from unittest.mock import Mock, patch, MagicMock

import pytest
from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from apps.telemetry.management.commands.dlq_consumer import Command


class TestDLQConsumerCommand(TestCase):
    """Test cases for DLQ Consumer management command."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = Command()
        self.stdout = StringIO()
        self.command.stdout = self.stdout
        self.command.style = Mock()
        self.command.style.SUCCESS = lambda x: x

    @patch("apps.telemetry.management.commands.dlq_consumer.Consumer")
    @patch("apps.telemetry.management.commands.dlq_consumer.record_telemetry_dlq")
    def test_process_valid_dlq_message(self, mock_record_dlq, mock_consumer_class):
        """Test processing a valid DLQ message."""
        # Setup mock consumer
        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer

        # Create valid message
        message_data = {
            "error_reason": "payload_validation_failed",
            "original_topic": "telemetry.raw",
        }
        message_value = json.dumps(message_data).encode("utf-8")

        # Mock message
        mock_message = Mock()
        mock_message.value.return_value = message_value
        mock_message.error.return_value = None

        # Poll returns message once, then None to stop loop
        mock_consumer.poll.side_effect = [mock_message, None]

        # Mock KeyboardInterrupt to stop the loop
        mock_consumer.poll.side_effect = [mock_message, KeyboardInterrupt()]

        try:
            self.command.handle(
                group_id="test-group",
                topic="telemetry.dlq",
                bootstrap_servers="localhost:9092",
                metrics_port=9104,
            )
        except KeyboardInterrupt:
            pass

        # Verify metric was recorded
        mock_record_dlq.assert_called()
        call_args = mock_record_dlq.call_args
        assert call_args[1]["topic"] == "telemetry.raw"
        assert call_args[1]["reason"] == "payload_validation_failed"

    @patch("apps.telemetry.management.commands.dlq_consumer.Consumer")
    @patch("apps.telemetry.management.commands.dlq_consumer.record_telemetry_dlq")
    def test_handle_missing_error_reason(self, mock_record_dlq, mock_consumer_class):
        """Test handling message with missing error_reason."""
        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer

        # Message without error_reason
        message_data = {"original_topic": "telemetry.raw"}
        message_value = json.dumps(message_data).encode("utf-8")

        mock_message = Mock()
        mock_message.value.return_value = message_value
        mock_message.error.return_value = None

        mock_consumer.poll.side_effect = [mock_message, KeyboardInterrupt()]

        try:
            self.command.handle(
                group_id="test-group",
                topic="telemetry.dlq",
                bootstrap_servers="localhost:9092",
                metrics_port=9104,
            )
        except KeyboardInterrupt:
            pass

        # Should default to "unknown"
        mock_record_dlq.assert_called()
        call_args = mock_record_dlq.call_args
        assert call_args[1]["reason"] == "unknown"

    @patch("apps.telemetry.management.commands.dlq_consumer.Consumer")
    @patch("apps.telemetry.management.commands.dlq_consumer.record_telemetry_dlq")
    def test_handle_missing_original_topic(self, mock_record_dlq, mock_consumer_class):
        """Test handling message with missing original_topic."""
        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer

        # Message without original_topic
        message_data = {"error_reason": "Invalid schema"}
        message_value = json.dumps(message_data).encode("utf-8")

        mock_message = Mock()
        mock_message.value.return_value = message_value
        mock_message.error.return_value = None

        mock_consumer.poll.side_effect = [mock_message, KeyboardInterrupt()]

        try:
            self.command.handle(
                group_id="test-group",
                topic="telemetry.dlq",
                bootstrap_servers="localhost:9092",
                metrics_port=9104,
            )
        except KeyboardInterrupt:
            pass

        # Should default to "telemetry.raw"
        mock_record_dlq.assert_called()
        call_args = mock_record_dlq.call_args
        assert call_args[1]["topic"] == "telemetry.raw"

    @patch("apps.telemetry.management.commands.dlq_consumer.Consumer")
    @patch("apps.telemetry.management.commands.dlq_consumer.logger")
    def test_handle_json_decode_error(self, mock_logger, mock_consumer_class):
        """Test handling invalid JSON in message."""
        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer

        # Invalid JSON
        message_value = b"not valid json"

        mock_message = Mock()
        mock_message.value.return_value = message_value
        mock_message.error.return_value = None

        mock_consumer.poll.side_effect = [mock_message, KeyboardInterrupt()]

        try:
            self.command.handle(
                group_id="test-group",
                topic="telemetry.dlq",
                bootstrap_servers="localhost:9092",
                metrics_port=9104,
            )
        except KeyboardInterrupt:
            pass

        # Should log error
        mock_logger.error.assert_called()
        assert "Failed to parse message JSON" in str(mock_logger.error.call_args)

    @patch("apps.telemetry.management.commands.dlq_consumer.Consumer")
    @patch("apps.telemetry.management.commands.dlq_consumer.logger")
    def test_handle_none_message_value(self, mock_logger, mock_consumer_class):
        """Test handling message with None value."""
        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer

        mock_message = Mock()
        mock_message.value.return_value = None
        mock_message.error.return_value = None

        mock_consumer.poll.side_effect = [mock_message, KeyboardInterrupt()]

        try:
            self.command.handle(
                group_id="test-group",
                topic="telemetry.dlq",
                bootstrap_servers="localhost:9092",
                metrics_port=9104,
            )
        except KeyboardInterrupt:
            pass

        # Should continue without error
        mock_logger.error.assert_not_called()

    @patch("apps.telemetry.management.commands.dlq_consumer.Consumer")
    def test_handle_kafka_error(self, mock_consumer_class):
        """Test handling Kafka connection error."""
        mock_consumer_class.side_effect = Exception("Connection refused")

        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            self.command.handle(
                group_id="test-group",
                topic="telemetry.dlq",
                bootstrap_servers="invalid:9092",
                metrics_port=9104,
            )

    @patch("apps.telemetry.management.commands.dlq_consumer.Consumer")
    def test_handle_metrics_port_error(self, mock_consumer_class):
        """Test handling metrics port startup error."""
        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer

        with patch(
            "apps.telemetry.management.commands.dlq_consumer.start_http_server",
            side_effect=OSError("Port already in use"),
        ):
            # Should not raise, just log warning
            try:
                self.command.handle(
                    group_id="test-group",
                    topic="telemetry.dlq",
                    bootstrap_servers="localhost:9092",
                    metrics_port=9104,
                )
            except KeyboardInterrupt:
                pass

    @patch("apps.telemetry.management.commands.dlq_consumer.Consumer")
    @patch("apps.telemetry.management.commands.dlq_consumer.record_telemetry_dlq")
    def test_handle_multiple_messages(self, mock_record_dlq, mock_consumer_class):
        """Test processing multiple DLQ messages."""
        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer

        # Create multiple messages
        messages = []
        for i in range(3):
            message_data = {
                "error_reason": f"error_{i}",
                "original_topic": "telemetry.raw",
            }
            message_value = json.dumps(message_data).encode("utf-8")
            mock_msg = Mock()
            mock_msg.value.return_value = message_value
            mock_msg.error.return_value = None
            messages.append(mock_msg)

        # Add KeyboardInterrupt to stop loop
        messages.append(KeyboardInterrupt())

        mock_consumer.poll.side_effect = messages

        try:
            self.command.handle(
                group_id="test-group",
                topic="telemetry.dlq",
                bootstrap_servers="localhost:9092",
                metrics_port=9104,
            )
        except KeyboardInterrupt:
            pass

        # Should process all 3 messages
        assert mock_record_dlq.call_count == 3

    @patch("apps.telemetry.management.commands.dlq_consumer.Consumer")
    def test_handle_none_poll_message(self, mock_consumer_class):
        """Test handling None from poll (timeout)."""
        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer

        # None means timeout, should continue
        mock_consumer.poll.side_effect = [None, None, KeyboardInterrupt()]

        try:
            self.command.handle(
                group_id="test-group",
                topic="telemetry.dlq",
                bootstrap_servers="localhost:9092",
                metrics_port=9104,
            )
        except KeyboardInterrupt:
            pass

        # Should not crash
        assert True
