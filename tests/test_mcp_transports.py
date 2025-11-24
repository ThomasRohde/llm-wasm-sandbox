"""Tests for MCP server transport implementations."""

from mcp_server.transports import (
    HTTPTransportConfig,
    StdioTransportConfig,
    TransportConfig,
    TransportType,
)


class TestTransportConfig:
    """Test base transport configuration."""

    def test_transport_config_creation(self):
        """Test creating transport config with type."""
        config = TransportConfig(TransportType.STDIO)
        assert config.transport_type == TransportType.STDIO

    def test_transport_config_enum_values(self):
        """Test transport type enum values."""
        assert TransportType.STDIO.value == "stdio"
        assert TransportType.HTTP.value == "http"


class TestStdioTransportConfig:
    """Test stdio transport configuration."""

    def test_stdio_config_creation(self):
        """Test creating stdio transport config."""
        config = StdioTransportConfig()
        assert config.transport_type == TransportType.STDIO

    def test_stdio_config_defaults(self):
        """Test stdio config has no additional defaults."""
        config = StdioTransportConfig()
        # Should only have transport_type
        assert hasattr(config, "transport_type")


class TestHTTPTransportConfig:
    """Test HTTP transport configuration."""

    def test_http_config_creation_defaults(self):
        """Test creating HTTP transport config with defaults."""
        config = HTTPTransportConfig()
        assert config.transport_type == TransportType.HTTP
        assert config.host == "127.0.0.1"
        assert config.port == 8080
        assert config.path == "/mcp"
        assert config.cors_origins == ["*"]
        assert config.auth_token is None
        assert config.rate_limit_requests == 100
        assert config.rate_limit_window_seconds == 60
        assert config.max_concurrent_requests == 10
        assert config.request_timeout_seconds == 30
        assert config.max_request_size_mb == 10

    def test_http_config_creation_custom(self):
        """Test creating HTTP transport config with custom values."""
        config = HTTPTransportConfig(
            host="0.0.0.0",
            port=9000,
            path="/api/mcp",
            cors_origins=["https://example.com"],
            auth_token="secret-token",
            rate_limit_requests=50,
            rate_limit_window_seconds=30,
            max_concurrent_requests=5,
            request_timeout_seconds=60,
            max_request_size_mb=5,
        )
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.path == "/api/mcp"
        assert config.cors_origins == ["https://example.com"]
        assert config.auth_token == "secret-token"
        assert config.rate_limit_requests == 50
        assert config.rate_limit_window_seconds == 30
        assert config.max_concurrent_requests == 5
        assert config.request_timeout_seconds == 60
        assert config.max_request_size_mb == 5

    def test_get_uvicorn_config(self):
        """Test getting uvicorn configuration."""
        config = HTTPTransportConfig(
            host="127.0.0.0",
            port=9000,
            rate_limit_requests=50,
            max_concurrent_requests=5,
            request_timeout_seconds=60,
        )
        uvicorn_config = config.get_uvicorn_config()

        expected = {
            "host": "127.0.0.0",
            "port": 9000,
            "access_log": True,
            "log_level": "info",
            "limit_concurrency": 5,
            "timeout_keep_alive": 60,
            "limit_max_requests": 50 * 10,  # Allow some burst
        }
        assert uvicorn_config == expected

    def test_get_cors_middleware_class(self):
        """Test getting CORS middleware class."""
        config = HTTPTransportConfig()
        middleware_class = config.get_cors_middleware_class()

        # Should return CORSMiddleware class
        from starlette.middleware.cors import CORSMiddleware

        assert middleware_class == CORSMiddleware

    def test_http_config_validation(self):
        """Test HTTP config accepts various parameter values."""
        # Test that config accepts various values (no validation currently implemented)
        config = HTTPTransportConfig(port=0)  # Should not raise
        assert config.port == 0

        config = HTTPTransportConfig(rate_limit_requests=0)  # Should not raise
        assert config.rate_limit_requests == 0

        config = HTTPTransportConfig(max_request_size_mb=0)  # Should not raise
        assert config.max_request_size_mb == 0
