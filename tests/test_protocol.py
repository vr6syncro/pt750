"""Test Brother protocol implementation."""

import pytest
from PIL import Image
from pt750.transports import PT750W, USBTransport
from pt750.models import PrinterStatus


class MockTransport:
    """Mock transport for testing."""
    
    def __init__(self):
        self.sent_bytes = b''
        self.status_response = None
    
    def send_bytes(self, data: bytes):
        self.sent_bytes = data
    
    def get_status(self):
        return self.status_response or PrinterStatus(media="24mm", ready=True)


@pytest.fixture
def mock_printer():
    """Create a PT750W printer with mock transport."""
    printer = PT750W("tcp://test:9100")
    printer.transport = MockTransport()
    return printer


@pytest.fixture
def test_image():
    """Create a test image."""
    return Image.new('1', (128, 100), color=0)  # Black image


def test_protocol_sequence(mock_printer, test_image):
    """Test that the protocol sequence is correct according to Brother spec."""
    mock_printer.print(test_image)
    
    data = mock_printer.transport.sent_bytes
    
    # Check invalidate sequence (100 bytes of 0x00)
    assert data[:100] == b'\x00' * 100
    
    # Check initialize command
    assert data[100:102] == b'\x1B\x40'  # ESC @
    
    # Check raster mode switch (CRITICAL FIX)
    assert data[102:105] == b'\x1B\x69\x61\x01'  # ESC i a 01
    
    # Check print information command exists
    print_info_start = 105
    assert data[print_info_start:print_info_start+3] == b'\x1B\x69\x7A'  # ESC i z
    
    # Check other commands
    assert b'\x1B\x69\x4D\x40' in data  # Various mode settings
    assert b'\x1B\x69\x4B\x08' in data  # Advanced mode settings
    assert b'\x1B\x69\x64\x0E\x00' in data  # Margin specification
    assert b'\x4D\x02' in data  # TIFF compression mode
    
    # Check ending with print+feed command
    assert data[-1:] == b'\x1A'  # Control-Z


def test_print_info_command(mock_printer, test_image):
    """Test print information command generation."""
    # Test with 100-line image
    print_info = mock_printer._get_print_info_command(test_image)
    
    expected = bytes([
        0x1B, 0x69, 0x7A,  # ESC i z
        0x8E,  # Valid flags: PI_KIND | PI_WIDTH | PI_LENGTH | PI_RECOVER
        0x01,  # Media type: Laminated tape
        0x18,  # Media width: 24mm
        0x00,  # Media length: 0 (continuous)
        100, 0x00, 0x00, 0x00,  # Raster lines: 100 (little-endian)
        0x00,  # Starting page
        0x00   # Fixed
    ])
    
    assert print_info == expected


def test_tiff_compression_run_length(mock_printer):
    """Test TIFF compression with run-length encoding."""
    # Test data with runs: 5 zeros, then 3 0xFF, then 2 0x55
    test_data = b'\x00\x00\x00\x00\x00\xFF\xFF\xFF\x55\x55'
    
    compressed = mock_printer._compress_tiff(test_data)
    
    # Expected: (257-5)=252, 0x00, (257-3)=254, 0xFF, (257-2)=255, 0x55
    expected = bytes([252, 0x00, 254, 0xFF, 255, 0x55])
    
    assert compressed == expected


def test_tiff_compression_literals(mock_printer):
    """Test TIFF compression with literal sequences."""
    # Test data with no runs
    test_data = b'\x01\x02\x03\x04'
    
    compressed = mock_printer._compress_tiff(test_data)
    
    # Expected: length-1 (3), then the 4 bytes
    expected = bytes([3, 0x01, 0x02, 0x03, 0x04])
    
    assert compressed == expected


def test_tiff_compression_fallback(mock_printer):
    """Test TIFF compression fallback for large data."""
    # Test data that compresses poorly (alternating pattern)
    test_data = bytes([i % 2 for i in range(20)])  # Too large for single literal
    
    compressed = mock_printer._compress_tiff(test_data)
    
    # Should fallback to literal encoding of first 16 bytes
    expected = bytes([15]) + test_data[:16]
    
    assert compressed == expected


def test_zero_raster_optimization(mock_printer):
    """Test that zero lines use Z command instead of G command."""
    # Create image with some zero lines
    test_image = Image.new('1', (128, 3), color=255)  # White (zero) image
    
    mock_printer.print(test_image)
    data = mock_printer.transport.sent_bytes
    
    # Should contain Z commands for zero lines
    assert b'\x5A' in data  # Z command should be present


def test_status_parsing():
    """Test Brother status parsing implementation."""
    # Create mock status response according to Brother spec
    status_data = bytearray(32)
    status_data[0] = 0x80  # Print head mark
    status_data[1] = 0x20  # Size
    status_data[2:4] = b'B0'  # Brother code + Series code
    status_data[4] = ord('h')  # Model code (PT-P750W)
    status_data[8] = 0x00  # Error info 1 (no errors)
    status_data[9] = 0x00  # Error info 2 (no errors)
    status_data[10] = 24   # Media width: 24mm
    status_data[11] = 0x01 # Media type: Laminated tape
    status_data[18] = 0x00 # Status type: Reply to status request
    status_data[19] = 0x00 # Phase type: Editing state
    
    transport = USBTransport("file:///dev/null")
    
    # Mock the file operations
    class MockFile:
        def __init__(self, data):
            self.data = data
            self.pos = 0
        
        def write(self, data):
            pass
        
        def read(self, size):
            result = self.data[self.pos:self.pos + size]
            self.pos += len(result)
            return result
        
        def __enter__(self):
            return self
        
        def __exit__(self, *args):
            pass
    
    # Monkey patch open for this test
    original_open = __builtins__['open']
    
    def mock_open(*args, **kwargs):
        return MockFile(bytes(status_data))
    
    __builtins__['open'] = mock_open
    
    try:
        status = transport.get_status()
        
        assert status is not None
        assert status.media == "24mm"
        assert status.ready is True
    finally:
        __builtins__['open'] = original_open


def test_status_parsing_with_errors():
    """Test status parsing with error conditions."""
    # Create status with errors
    status_data = bytearray(32)
    status_data[0] = 0x80  # Print head mark
    status_data[2:4] = b'B0'  # Brother codes
    status_data[8] = 0x01  # Error info 1: No media error
    status_data[9] = 0x00  # Error info 2: No errors
    status_data[10] = 0    # No media width
    status_data[18] = 0x02 # Status type: Error occurred
    
    transport = USBTransport("file:///dev/null")
    
    def mock_open(*args, **kwargs):
        class MockFile:
            def write(self, data): pass
            def read(self, size): return bytes(status_data)
            def __enter__(self): return self
            def __exit__(self, *args): pass
        return MockFile()
    
    original_open = __builtins__['open']
    __builtins__['open'] = mock_open
    
    try:
        status = transport.get_status()
        
        assert status is not None
        assert status.media is None
        assert status.ready is False
    finally:
        __builtins__['open'] = original_open