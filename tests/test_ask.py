import sys
import unittest
from unittest.mock import MagicMock, patch
from cli import cmd_ask

class TestCmdAsk(unittest.TestCase):
    @patch("cli.get_client")
    @patch("cli.load_config")
    def test_cmd_ask_non_text_response(self, mock_load_config, mock_get_client):
        # Setup
        mock_load_config.return_value = {"assistant_id": "asst_123", "file_names": ["doc1"]}
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock thread and run
        mock_thread = MagicMock()
        mock_thread.id = "thread_123"
        mock_client.beta.threads.create.return_value = mock_thread
        
        mock_run = MagicMock()
        mock_run.status = "completed"
        mock_client.beta.threads.runs.create_and_poll.return_value = mock_run
        
        # Mock messages with non-text content
        mock_message_list = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "image_file" # Not "text"
        mock_message_list.data = [MagicMock(content=[mock_content])]
        
        mock_client.beta.threads.messages.list.return_value = mock_message_list
        
        # Args
        args = MagicMock()
        args.question = "test"
        
        # Expect sys.exit(1)
        with self.assertRaises(SystemExit) as cm:
            cmd_ask(args)
        
        self.assertEqual(cm.exception.code, 1)

    @patch("cli.get_client")
    @patch("cli.load_config")
    def test_cmd_ask_success(self, mock_load_config, mock_get_client):
         # Setup
        mock_load_config.return_value = {"assistant_id": "asst_123", "file_names": ["doc1"]}
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_thread = MagicMock()
        mock_thread.id = "thread_123"
        mock_client.beta.threads.create.return_value = mock_thread
        
        mock_run = MagicMock()
        mock_run.status = "completed"
        mock_client.beta.threads.runs.create_and_poll.return_value = mock_run
        
        # Mock messages with TEXT content
        mock_message_list = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "text" 
        mock_content.text.value = "The answer."
        mock_message_list.data = [MagicMock(content=[mock_content])]
        
        mock_client.beta.threads.messages.list.return_value = mock_message_list
        
        args = MagicMock()
        args.question = "test"
        
        # Capture stdout
        from io import StringIO
        saved_stdout = sys.stdout
        try:
            out = StringIO()
            sys.stdout = out
            cmd_ask(args)
            output = out.getvalue().strip()
            self.assertEqual(output, "The answer.")
        finally:
            sys.stdout = saved_stdout
