import base64
import logging
import socket
from urllib.parse import urlparse, urlunparse

import requests
# Import pysnmp with fallback for different versions
try:
    # Try modern pysnmp v7+ (get_cmd)
    from pysnmp.hlapi.v1arch.asyncio import get_cmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
    getCmd = get_cmd  # Alias for compatibility
    HAS_PYSNMP = True
except ImportError:
    try:
        # Try legacy pysnmp (getCmd)
        from pysnmp.hlapi import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
        HAS_PYSNMP = True
    except ImportError:
        try:
            from pysnmp.hlapi.v1arch.asyncio import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
            HAS_PYSNMP = True
        except ImportError:
            HAS_PYSNMP = False
            logging.warning("pysnmp not available, TCP transport status will be limited")
from PIL import Image

from pt750.models import PrinterStatus, tapes


class LabelPrinter:
    def __init__(self, uri):
        self.uri = uri
        parts = urlparse(self.uri)
        if parts.scheme == "tcp":
            self.transport = TCPTransport(self.uri)
        elif parts.scheme == "file":
            self.transport = USBTransport(self.uri)
        elif parts.scheme in ["http", "https"]:
            self.transport = HTTPTransport(self.uri)
        else:
            raise RuntimeError("cannot find transport")

    def print(self, img: Image):
        raise NotImplementedError

    def status(self):
        raise NotImplementedError


class PT750W(LabelPrinter):
    def print(self, img: Image, tape: str = "24mm"):
        img = img.transpose(Image.Transpose.ROTATE_90)
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        image_data = bytearray(img.tobytes())

        for idx in range(len(image_data)):
            image_data[idx] = image_data[idx] ^ 0xFF

        data = b"\x00" * 100  # Invalidate - reset stream
        data += b"\x1B\x40"  # ESC @ Initialize
        data += b"\x1B\x69\x61\x01"  # ESC i a Switch to raster mode (REQUIRED!)
        data += self._get_print_info_command(img, tape)  # ESC i z Print information command
        data += b"\x1B\x69\x4D\x40"  # ESC i M Various mode settings - auto tape cut
        data += b"\x1B\x69\x4B\x08"  # ESC i K Advanced mode settings - no chain printing
        data += b"\x1B\x69\x64\x0E\x00"  # ESC i d Specify margin amount (2mm = 14 dots)
        data += b"\x4d\x02"  # M Select compression mode - TIFF

        label_width = img.width
        label_height = img.height

        assert label_width == 128

        for line in range(label_height):
            bytes_per_line = label_width // 8
            byte_ofs = bytes_per_line * line
            row_bytes = image_data[byte_ofs : byte_ofs + bytes_per_line]  # noqa: E203

            # Check if line is all zeros (can use Z command)
            if all(b == 0 for b in row_bytes):
                data += b"\x5A"  # Z Zero raster graphics
            else:
                # G Raster graphics transfer with TIFF compression
                compressed_data = self._compress_tiff(row_bytes)
                data_len = len(compressed_data)
                data += b"\x47"  # G command
                data += bytes([data_len & 0xFF, (data_len >> 8) & 0xFF])  # length as little-endian
                data += compressed_data

        data += b"\x1a"  # Control-Z Print command with feeding

        self.transport.send_bytes(data)

    def status(self) -> PrinterStatus:
        return self.transport.get_status()

    def _get_print_info_command(self, img: Image, tape: str) -> bytes:
        """Generate ESC i z Print information command according to Brother spec."""
        # ESC i z {n1} {n2} {n3} {n4} {n5} {n6} {n7} {n8} {n9} {n10}
        n1 = 0x8E  # Valid flags: PI_KIND | PI_WIDTH | PI_LENGTH | PI_RECOVER
        n2 = 0x01  # Media type: Laminated tape
        
        # Dynamic media width based on tape parameter
        tape_widths = {"6mm": 6, "9mm": 9, "12mm": 12, "24mm": 24}
        n3 = tape_widths.get(tape, 24)  # Default to 24mm if unknown
        
        n4 = 0x00  # Media length: 0 (continuous tape)
        
        # Raster number (n5-n8): total number of raster lines
        raster_lines = img.height
        n5 = raster_lines & 0xFF
        n6 = (raster_lines >> 8) & 0xFF
        n7 = (raster_lines >> 16) & 0xFF
        n8 = (raster_lines >> 24) & 0xFF
        
        n9 = 0x00  # Starting page: 0
        n10 = 0x00  # Fixed at 0
        
        return bytes([0x1B, 0x69, 0x7A, n1, n2, n3, n4, n5, n6, n7, n8, n9, n10])

    def _compress_tiff(self, data: bytes) -> bytes:
        """TIFF/PackBits compression according to Brother specification."""
        if not data:
            return b''
            
        result = bytearray()
        i = 0
        
        while i < len(data):
            # Look for runs of identical bytes
            run_length = 1
            while (i + run_length < len(data) and 
                   data[i] == data[i + run_length] and 
                   run_length < 128):
                run_length += 1
            
            if run_length >= 2:
                # Encode run: (257 - run_length) followed by the byte
                result.append(257 - run_length)
                result.append(data[i])
                i += run_length
            else:
                # Look for literal sequence
                literal_start = i
                while (i < len(data) and 
                       (i + 1 >= len(data) or data[i] != data[i + 1]) and
                       i - literal_start < 127):
                    i += 1
                
                literal_length = i - literal_start
                # Encode literal: length-1 followed by the bytes
                result.append(literal_length - 1)
                result.extend(data[literal_start:i])
        
        # If compression makes it larger, return uncompressed with literal encoding
        if len(result) > 16:
            # Return as single literal block (max 16 bytes for Brother)
            if len(data) <= 16:
                return bytes([len(data) - 1]) + data
            else:
                return bytes([15]) + data[:16]
        
        return bytes(result)


class Transport:
    def __init__(self, uri):
        self.uri = uri

    def send_bytes(self, bytes: bytes):
        raise NotImplementedError

    def get_status(self) -> PrinterStatus:
        raise NotImplementedError


class USBTransport(Transport):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        parts = urlparse(self.uri)
        self.path = parts.path

    def send_bytes(self, bytes):
        with open(self.path, "wb") as f:
            f.write(bytes)

    def get_status(self) -> PrinterStatus:
        max_attempts = 3

        while max_attempts:
            with open(self.path, "w+b") as f:
                f.write(b"\x00" * 100)  # Invalidate
                f.write(b"\x1B\x69\x53")  # ESC i S Status information request
                raw_status = f.read(32)

                if len(raw_status) < 32:
                    max_attempts -= 1
                else:
                    break

        if not max_attempts:
            return PrinterStatus(media=None, ready=False)

        # Parse status according to Brother specification
        try:
            # Check header (bytes 0-7)
            if raw_status[0] != 0x80 or raw_status[2:4] != b'B0':
                logging.warning("Invalid status header")
                return PrinterStatus(media=None, ready=False)
            
            # Parse error information (bytes 8-9)
            error_info_1 = raw_status[8]
            error_info_2 = raw_status[9]
            
            # Check for errors
            has_errors = bool(error_info_1) or bool(error_info_2)
            
            # Parse media info (bytes 10-11)
            media_width = raw_status[10]
            media_type = raw_status[11]
            
            # Determine media string
            media = None
            if media_width > 0:
                media = f"{media_width}mm"
            
            # Parse status type (byte 18)
            status_type = raw_status[18]
            
            # Parse phase info (bytes 19-21)
            phase_type = raw_status[19]
            
            # Determine ready status
            ready = not has_errors and status_type in [0x00, 0x01] and phase_type == 0x00
            
            if not ready:
                logging.info(f"Printer not ready - Error1: {error_info_1:02x}, Error2: {error_info_2:02x}, "
                           f"Status: {status_type:02x}, Phase: {phase_type:02x}")
            
            return PrinterStatus(media=media, ready=ready)
            
        except Exception as e:
            logging.error(f"Error parsing printer status: {e}")
            return PrinterStatus(media=None, ready=False)


class TCPTransport(Transport):
    MEDIA_OID = ".1.3.6.1.2.1.43.8.2.1.12.1.1"
    STATUS_OID = ".1.3.6.1.2.1.43.8.2.1.11.1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        parts = urlparse(self.uri)
        self.host = parts.hostname
        self.port = parts.port if parts.port else 9100

        # Configure SNMP for Brother printer access
        self.community = "public"

    def send_bytes(self, bytes):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, self.port))
        s.sendall(bytes)
        s.close()

    def get_status(self) -> PrinterStatus:
        if not HAS_PYSNMP:
            # Simple fallback - assume printer is ready if we can connect
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                result = s.connect_ex((self.host, self.port))
                s.close()
                ready = result == 0
                return PrinterStatus(media="12mm" if ready else None, ready=ready)
            except:
                return PrinterStatus(media=None, ready=False)
        
        try:
            # Get media descriptor
            media_iter = getCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.host, 161)),
                ContextData(),
                ObjectType(ObjectIdentity(self.MEDIA_OID))
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(media_iter)
            
            if errorIndication or errorStatus:
                logging.warning(f"SNMP error getting media: {errorIndication or errorStatus}")
                return PrinterStatus(media=None, ready=False)
            
            media_descriptor = str(varBinds[0][1])
            
            # Get status
            status_iter = getCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.host, 161)),
                ContextData(),
                ObjectType(ObjectIdentity(self.STATUS_OID))
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(status_iter)
            
            if errorIndication or errorStatus:
                logging.warning(f"SNMP error getting status: {errorIndication or errorStatus}")
                return PrinterStatus(media=None, ready=False)
            
            status_value = int(varBinds[0][1])
            ready = status_value in [0, 2, 4, 6]

            media = None
            for tape in tapes:
                if media_descriptor.startswith(tape):
                    media = tape

            return PrinterStatus(media=media, ready=ready)
            
        except Exception as e:
            logging.error(f"Error getting printer status via SNMP: {e}")
            return PrinterStatus(media=None, ready=False)


class HTTPTransport(Transport):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        parts = urlparse(self.uri)
        self.printer = parts.path.rsplit("/", 1)[-1]
        parts = parts._replace(path=parts.path.rsplit("/", 1)[0])
        self.base_uri = urlunparse(parts)

    def get_status(self) -> PrinterStatus:
        rv = requests.get(f"{self.base_uri}/status")
        if not rv.ok:
            logging.error(f"Error getting status for {self.printer}: {rv.status_code}")
            return PrinterStatus(media="24mm", ready=False)

        body = rv.json()
        if self.printer not in body:
            logging.error(f"Remote does not have printer {self.printer}")
            return PrinterStatus(media="24mm", ready=False)

        return PrinterStatus(**body[self.printer])

    def send_bytes(self, bytes):
        request = {
            "count": 1,
            "label": {
                "label_type": "raw",
                "b64_bytes": base64.b64encode(bytes).decode(),
                "printer": self.printer,
                # these are no-op
                "tape": "6mm",
                "fontname": "mono",
            },
        }

        rv = requests.put(f"{self.base_uri}/print", json=request)
        rv.raise_for_status()
