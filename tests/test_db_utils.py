# tests/test_db_utils.py
"""
Tests for database utility functions.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import pandas as pd
from sqlalchemy.exc import DatabaseError
from src.db_utils import (
    validate_query_file,
    query_to_df,
    get_db_connection,
    check_db_connection
)


class TestValidateQueryFile:
    """Tests for validate_query_file function."""
    
    def test_validate_query_file_success(self, tmp_path):
        """Test that valid SQL file is loaded correctly."""
        query_file = tmp_path / "test_query.sql"
        query_content = "SELECT * FROM users WHERE id = 1;"
        query_file.write_text(query_content)
        
        result = validate_query_file(query_file)
        
        assert result == query_content
    
    def test_validate_query_file_multiline(self, tmp_path):
        """Test that multiline SQL file is loaded correctly."""
        query_file = tmp_path / "multiline.sql"
        query_content = """
        SELECT 
            id,
            name,
            email
        FROM users
        WHERE active = true;
        """
        query_file.write_text(query_content)
        
        result = validate_query_file(query_file)
        
        assert result == query_content
    
    def test_validate_query_file_not_found(self, tmp_path):
        """Test that FileNotFoundError is raised for missing file."""
        missing_file = tmp_path / "nonexistent.sql"
        
        with pytest.raises(FileNotFoundError, match="Query file not found"):
            validate_query_file(missing_file)
    
    def test_validate_query_file_wrong_extension(self, tmp_path):
        """Test that ValueError is raised for non-SQL file."""
        wrong_file = tmp_path / "query.txt"
        wrong_file.write_text("SELECT * FROM users;")
        
        with pytest.raises(ValueError, match="Only .sql files are allowed"):
            validate_query_file(wrong_file)
    
    def test_validate_query_file_no_extension(self, tmp_path):
        """Test that ValueError is raised for file without extension."""
        no_ext_file = tmp_path / "query"
        no_ext_file.write_text("SELECT * FROM users;")
        
        with pytest.raises(ValueError, match="Only .sql files are allowed"):
            validate_query_file(no_ext_file)
    
    def test_validate_query_file_case_sensitive(self, tmp_path):
        """Test that .SQL extension (uppercase) is rejected."""
        upper_file = tmp_path / "query.SQL"
        upper_file.write_text("SELECT * FROM users;")
        
        with pytest.raises(ValueError, match="Only .sql files are allowed"):
            validate_query_file(upper_file)
    
    def test_validate_query_file_empty(self, tmp_path):
        """Test that empty SQL file is loaded (returns empty string)."""
        empty_file = tmp_path / "empty.sql"
        empty_file.write_text("")
        
        result = validate_query_file(empty_file)
        
        assert result == ""
    
    def test_validate_query_file_utf8_encoding(self, tmp_path):
        """Test that UTF-8 encoded file is loaded correctly."""
        utf8_file = tmp_path / "utf8.sql"
        query_content = "SELECT * FROM users WHERE name = 'Παναγιώτης';"
        utf8_file.write_text(query_content, encoding='utf-8')
        
        result = validate_query_file(utf8_file)
        
        assert result == query_content


class TestQueryToDF:
    """Tests for query_to_df function."""
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.pd.read_sql')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_query_to_df_direct_connection(self, mock_read_sql, mock_create_engine):
        """Test query execution with direct database connection."""
        # Mock DataFrame result
        expected_df = pd.DataFrame({'id': [1, 2], 'name': ['Alice', 'Bob']})
        mock_read_sql.return_value = expected_df
        
        result = query_to_df("SELECT * FROM users")
        
        assert result.equals(expected_df)
        mock_create_engine.assert_called_once()
        mock_read_sql.assert_called_once()
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.pd.read_sql')
    @patch('src.db_utils.SSHTunnelForwarder')
    @patch('src.db_utils.USE_SSH_TUNNEL', True)
    @patch('src.db_utils.SSH_HOST', 'ssh.example.com')
    @patch('src.db_utils.SSH_KEY_PATH', '/home/user/.ssh/id_rsa')
    @patch('os.path.exists', return_value=True)
    def test_query_to_df_with_ssh_tunnel(
        self, mock_exists, mock_tunnel, mock_read_sql, mock_create_engine
    ):
        """Test query execution with SSH tunnel."""
        # Mock tunnel
        mock_tunnel_instance = MagicMock()
        mock_tunnel_instance.local_bind_port = 5555
        mock_tunnel.return_value.__enter__.return_value = mock_tunnel_instance
        
        # Mock DataFrame result
        expected_df = pd.DataFrame({'id': [1], 'name': ['Alice']})
        mock_read_sql.return_value = expected_df
        
        result = query_to_df("SELECT * FROM users")
        
        assert result.equals(expected_df)
        mock_tunnel.assert_called_once()
        mock_create_engine.assert_called_once()
    
    @patch('src.db_utils.USE_SSH_TUNNEL', True)
    @patch('src.db_utils.SSH_HOST', 'ssh.example.com')
    @patch('src.db_utils.SSH_KEY_PATH', '/nonexistent/key')
    @patch('os.path.exists', return_value=False)
    def test_query_to_df_ssh_key_not_found(self, mock_exists):
        """Test that FileNotFoundError is raised when SSH key is missing."""
        with pytest.raises(FileNotFoundError, match="SSH key not found"):
            query_to_df("SELECT * FROM users")
    
    @patch('duckdb.query')
    def test_query_to_df_local_duckdb(self, mock_duckdb_query):
        """Test query execution with local DuckDB."""
        # Mock DuckDB result
        mock_result = MagicMock()
        expected_df = pd.DataFrame({'id': [1, 2, 3], 'value': [10, 20, 30]})
        mock_result.to_df.return_value = expected_df
        mock_duckdb_query.return_value = mock_result
        
        result = query_to_df("SELECT * FROM 'data.parquet'", local=True)
        
        assert result.equals(expected_df)
        mock_duckdb_query.assert_called_once_with("SELECT * FROM 'data.parquet'")
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.pd.read_sql')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_query_to_df_display_all_true(self, mock_read_sql, mock_create_engine):
        """Test that display_all=True sets pandas display options."""
        expected_df = pd.DataFrame({'id': [1]})
        mock_read_sql.return_value = expected_df
        
        with patch('src.db_utils.pd.set_option') as mock_set_option:
            query_to_df("SELECT * FROM users", display_all=True)
            
            # Verify display options were set
            assert mock_set_option.call_count == 4
            mock_set_option.assert_any_call('display.max_rows', None)
            mock_set_option.assert_any_call('display.max_columns', None)
            mock_set_option.assert_any_call('display.width', None)
            mock_set_option.assert_any_call('display.max_colwidth', None)
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.pd.read_sql')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_query_to_df_display_all_false(self, mock_read_sql, mock_create_engine):
        """Test that display_all=False resets pandas display options."""
        expected_df = pd.DataFrame({'id': [1]})
        mock_read_sql.return_value = expected_df
        
        with patch('src.db_utils.pd.reset_option') as mock_reset_option:
            query_to_df("SELECT * FROM users", display_all=False)
            
            # Verify display options were reset
            assert mock_reset_option.call_count == 4
            mock_reset_option.assert_any_call('display.max_rows')
            mock_reset_option.assert_any_call('display.max_columns')
            mock_reset_option.assert_any_call('display.width')
            mock_reset_option.assert_any_call('display.max_colwidth')
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.pd.read_sql')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_query_to_df_database_error(self, mock_read_sql, mock_create_engine):
        """Test that database errors are propagated."""
        mock_read_sql.side_effect = DatabaseError("Connection failed", None, None)
        
        with pytest.raises(DatabaseError):
            query_to_df("SELECT * FROM users")


class TestGetDBConnection:
    """Tests for get_db_connection context manager."""
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_get_db_connection_direct(self, mock_create_engine):
        """Test direct database connection without SSH tunnel."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_create_engine.return_value = mock_engine
        
        with get_db_connection() as conn:
            assert conn == mock_conn
        
        mock_conn.close.assert_called_once()
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.SSHTunnelForwarder')
    @patch('src.db_utils.USE_SSH_TUNNEL', True)
    @patch('src.db_utils.SSH_HOST', 'ssh.example.com')
    @patch('src.db_utils.SSH_KEY_PATH', '/home/user/.ssh/id_rsa')
    @patch('os.path.exists', return_value=True)
    def test_get_db_connection_with_ssh_tunnel(
        self, mock_exists, mock_tunnel, mock_create_engine
    ):
        """Test database connection with SSH tunnel."""
        # Mock tunnel
        mock_tunnel_instance = MagicMock()
        mock_tunnel_instance.local_bind_port = 5555
        mock_tunnel.return_value.__enter__.return_value = mock_tunnel_instance
        
        # Mock engine and connection
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_create_engine.return_value = mock_engine
        
        with get_db_connection() as conn:
            assert conn == mock_conn
        
        mock_tunnel.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('src.db_utils.USE_SSH_TUNNEL', True)
    @patch('src.db_utils.SSH_HOST', 'ssh.example.com')
    @patch('src.db_utils.SSH_KEY_PATH', '/nonexistent/key')
    @patch('os.path.exists', return_value=False)
    def test_get_db_connection_ssh_key_not_found(self, mock_exists):
        """Test that FileNotFoundError is raised when SSH key is missing."""
        with pytest.raises(FileNotFoundError, match="SSH key not found"):
            with get_db_connection() as conn:
                pass
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_get_db_connection_closes_on_exception(self, mock_create_engine):
        """Test that connection is closed even when exception occurs."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_create_engine.return_value = mock_engine
        
        with pytest.raises(RuntimeError):
            with get_db_connection() as conn:
                raise RuntimeError("Test error")
        
        # Connection should still be closed despite exception
        mock_conn.close.assert_called_once()
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_get_db_connection_execute_query(self, mock_create_engine):
        """Test executing a query through the connection."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value = mock_conn
        mock_create_engine.return_value = mock_engine
        
        with get_db_connection() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            count = result.scalar()
        
        assert count == 42
        mock_conn.execute.assert_called_once()
        mock_conn.close.assert_called_once()


class TestCheckDBConnection:
    """Tests for check_db_connection function."""
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_check_db_connection_success_direct(self, mock_create_engine):
        """Test successful connection check without SSH tunnel."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_create_engine.return_value = mock_engine
        
        result = check_db_connection()
        
        assert result is True
        mock_conn.execute.assert_called_once()
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.SSHTunnelForwarder')
    @patch('src.db_utils.USE_SSH_TUNNEL', True)
    @patch('src.db_utils.SSH_HOST', 'ssh.example.com')
    @patch('src.db_utils.SSH_KEY_PATH', '/home/user/.ssh/id_rsa')
    @patch('os.path.exists', return_value=True)
    def test_check_db_connection_success_with_tunnel(
        self, mock_exists, mock_tunnel, mock_create_engine
    ):
        """Test successful connection check with SSH tunnel."""
        # Mock tunnel
        mock_tunnel_instance = MagicMock()
        mock_tunnel_instance.local_bind_port = 5555
        mock_tunnel.return_value.__enter__.return_value = mock_tunnel_instance
        
        # Mock engine and connection
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_create_engine.return_value = mock_engine
        
        result = check_db_connection()
        
        assert result is True
        mock_tunnel.assert_called_once()
        mock_conn.execute.assert_called_once()
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_check_db_connection_failure_direct(self, mock_create_engine):
        """Test connection check failure without SSH tunnel."""
        mock_create_engine.side_effect = DatabaseError("Connection failed", None, None)
        
        result = check_db_connection()
        
        assert result is False
    
    @patch('src.db_utils.SSHTunnelForwarder')
    @patch('src.db_utils.USE_SSH_TUNNEL', True)
    @patch('src.db_utils.SSH_HOST', 'ssh.example.com')
    @patch('src.db_utils.SSH_KEY_PATH', '/home/user/.ssh/id_rsa')
    @patch('os.path.exists', return_value=True)
    def test_check_db_connection_tunnel_failure(self, mock_exists, mock_tunnel):
        """Test connection check failure when SSH tunnel fails."""
        mock_tunnel.side_effect = Exception("SSH tunnel failed")
        
        result = check_db_connection()
        
        assert result is False
    
    @patch('src.db_utils.USE_SSH_TUNNEL', True)
    @patch('src.db_utils.SSH_HOST', 'ssh.example.com')
    @patch('src.db_utils.SSH_KEY_PATH', '/nonexistent/key')
    @patch('os.path.exists', return_value=False)
    def test_check_db_connection_ssh_key_not_found(self, mock_exists):
        """Test connection check failure when SSH key is missing."""
        result = check_db_connection()
        
        assert result is False
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_check_db_connection_execute_failure(self, mock_create_engine):
        """Test connection check failure when execute fails."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = DatabaseError("Query failed", None, None)
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_create_engine.return_value = mock_engine
        
        result = check_db_connection()
        
        assert result is False
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_check_db_connection_prints_error(self, mock_create_engine, capsys):
        """Test that connection errors are printed to stdout."""
        mock_create_engine.side_effect = Exception("Connection timeout")
        
        result = check_db_connection()
        
        assert result is False
        captured = capsys.readouterr()
        assert "Connection failed" in captured.out
        assert "Connection timeout" in captured.out


class TestConnectionStrings:
    """Tests for connection string construction."""
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.pd.read_sql')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    @patch('src.db_utils.DB_USER', 'testuser')
    @patch('src.db_utils.DB_PASS', 'testpass')
    @patch('src.db_utils.DB_HOST', 'localhost')
    @patch('src.db_utils.DB_PORT', 5432)
    @patch('src.db_utils.DB_NAME', 'testdb')
    def test_connection_string_format_direct(self, mock_read_sql, mock_create_engine):
        """Test that direct connection string is formatted correctly."""
        mock_read_sql.return_value = pd.DataFrame()
        
        query_to_df("SELECT 1")
        
        # Check that connection string was passed correctly
        call_args = mock_create_engine.call_args[0][0]
        assert call_args == "postgresql://testuser:testpass@localhost:5432/testdb"
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.pd.read_sql')
    @patch('src.db_utils.SSHTunnelForwarder')
    @patch('src.db_utils.USE_SSH_TUNNEL', True)
    @patch('src.db_utils.SSH_HOST', 'ssh.example.com')
    @patch('src.db_utils.SSH_KEY_PATH', '/home/user/.ssh/id_rsa')
    @patch('src.db_utils.DB_USER', 'sshuser')
    @patch('src.db_utils.DB_PASS', 'sshpass')
    @patch('src.db_utils.DB_NAME', 'sshdb')
    @patch('os.path.exists', return_value=True)
    def test_connection_string_format_tunnel(
        self, mock_exists, mock_tunnel, mock_read_sql, mock_create_engine
    ):
        """Test that SSH tunnel connection string is formatted correctly."""
        # Mock tunnel with specific port
        mock_tunnel_instance = MagicMock()
        mock_tunnel_instance.local_bind_port = 12345
        mock_tunnel.return_value.__enter__.return_value = mock_tunnel_instance
        
        mock_read_sql.return_value = pd.DataFrame()
        
        query_to_df("SELECT 1")
        
        # Check that connection string uses tunnel port
        call_args = mock_create_engine.call_args[0][0]
        assert call_args == "postgresql://sshuser:sshpass@localhost:12345/sshdb"


class TestSSHTunnelConfiguration:
    """Tests for SSH tunnel configuration."""
    
    @patch('src.db_utils.SSHTunnelForwarder')
    @patch('src.db_utils.USE_SSH_TUNNEL', True)
    @patch('src.db_utils.SSH_HOST', 'ssh.example.com')
    @patch('src.db_utils.SSH_PORT', 2222)
    @patch('src.db_utils.SSH_USER', 'sshuser')
    @patch('src.db_utils.SSH_KEY_PATH', '/home/user/.ssh/custom_key')
    @patch('src.db_utils.DB_HOST', 'db.internal.com')
    @patch('src.db_utils.DB_PORT', 5432)
    @patch('os.path.exists', return_value=True)
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.pd.read_sql')
    def test_ssh_tunnel_parameters(
        self, mock_read_sql, mock_create_engine, mock_exists, mock_tunnel
    ):
        """Test that SSH tunnel is configured with correct parameters."""
        mock_tunnel_instance = MagicMock()
        mock_tunnel_instance.local_bind_port = 5555
        mock_tunnel.return_value.__enter__.return_value = mock_tunnel_instance
        mock_read_sql.return_value = pd.DataFrame()
        
        query_to_df("SELECT 1")
        
        # Verify SSH tunnel was created with correct parameters
        mock_tunnel.assert_called_once_with(
            ('ssh.example.com', 2222),
            ssh_username='sshuser',
            ssh_private_key='/home/user/.ssh/custom_key',
            remote_bind_address=('db.internal.com', 5432)
        )


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""
    
    @patch('src.db_utils.create_engine')
    @patch('src.db_utils.pd.read_sql')
    @patch('src.db_utils.USE_SSH_TUNNEL', False)
    def test_empty_query_result(self, mock_read_sql, mock_create_engine):
        """Test handling of queries that return no rows."""
        empty_df = pd.DataFrame(columns=['id', 'name'])
        mock_read_sql.return_value = empty_df
        
        result = query_to_df("SELECT * FROM users WHERE id = -1")
        
        assert len(result) == 0
        assert list(result.columns) == ['id', 'name']
    
    @patch('duckdb.query')
    def test_local_query_with_complex_sql(self, mock_duckdb_query):
        """Test local DuckDB execution with complex query."""
        mock_result = MagicMock()
        expected_df = pd.DataFrame({'total': [100]})
        mock_result.to_df.return_value = expected_df
        mock_duckdb_query.return_value = mock_result
        
        complex_query = """
        SELECT SUM(amount) as total
        FROM transactions
        WHERE date >= '2024-01-01'
        GROUP BY user_id
        """
        
        result = query_to_df(complex_query, local=True)
        
        assert result.equals(expected_df)
        mock_duckdb_query.assert_called_once_with(complex_query)
    
    def test_validate_query_file_with_comments(self, tmp_path):
        """Test that SQL file with comments is loaded correctly."""
        query_file = tmp_path / "commented.sql"
        query_content = """
        -- This is a comment
        SELECT * FROM users
        WHERE active = true  -- Only active users
        /* Multi-line
           comment */
        ORDER BY created_at DESC;
        """
        query_file.write_text(query_content)
        
        result = validate_query_file(query_file)
        
        assert result == query_content
        assert "-- This is a comment" in result
