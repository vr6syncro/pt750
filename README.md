# Brother PT-P750W Web Interface

Modern web-based label printing interface for Brother PT-P750W/PT-E550W label printers using the Brother Raster Command protocol.

## Features

- **Web Interface**: Clean, responsive Bootstrap UI for label creation
- **Multiple Label Types**: Text, QR codes, ArUco markers, cable wraps, and flags
- **Font Management**: Upload and manage custom TTF/OTF fonts
- **Printer Status**: Real-time status monitoring with visual indicators
- **Tape Detection**: Automatic tape size detection from printer
- **Metric/Imperial**: Toggle between mm and inch measurements
- **Docker Ready**: Easy deployment with Docker Compose

## Quick Start

### Docker Compose (Recommended)

```bash
git clone https://github.com/vr6syncro/pt750.git -b v2
cd pt750
docker-compose up -d
```

Access the web interface at `http://localhost:8080`

### DockerHub (Pre-built Images)

For the latest v2.0.0 release:
```bash
# Create docker-compose.yml
services:
  pt750:
    image: vr6syncro/pt750:v2
    container_name: pt750-web
    environment:
      - L_PRINTERS=pt750=tcp://192.168.1.100:9100
      - L_FONT_DIRS=/app/custom_fonts
    ports:
      - "8080:5000"
    volumes:
      - font_cache:/app/custom_fonts
    restart: unless-stopped

volumes:
  font_cache:

# Run
docker-compose up -d
```

Or run directly:
```bash
docker run -d \
  --name pt750-web \
  -p 8080:5000 \
  -e L_PRINTERS=pt750=tcp://192.168.1.100:9100 \
  -v font_cache:/app/custom_fonts \
  vr6syncro/pt750:v2
```

### Manual Installation

```bash
# Install dependencies
poetry install

# Run web server
python -m pt750.web

# Run CLI tool
poetry run makelabel --printer tcp://192.168.1.100:9100 text "Hello World"
```

## Configuration

### Environment Variables

- `L_PRINTERS`: Printer configuration (e.g., `pt750=tcp://192.168.1.100:9100`)
- `L_FONT_DIRS`: Custom font directories (e.g., `/app/custom_fonts`)
- `L_FONT_MAP`: Font name mappings (e.g., `mono=DejaVuSansMono.ttf`)

### Supported Label Types

- **Text**: Plain text labels with alignment options
- **QR Code**: QR codes with optional text lines
- **ArUco**: Computer vision markers with customizable dictionaries
- **Wrap**: Vertical text for cable wrapping
- **Flag**: Horizontal text for cable flags

### Supported Tape Sizes

- 24mm (full width)
- 12mm (centered)
- 9mm (centered) 
- 6mm (centered)

## API Endpoints

- `GET /` - Web interface
- `GET /config` - Printer and font configuration
- `GET /status` - Printer status
- `PUT /print` - Print label
- `PUT /preview` - Generate label preview
- `POST /fonts/upload` - Upload font file
- `DELETE /fonts/{name}` - Remove font

## Technical Details

### Brother Raster Protocol

This implementation follows the Brother Raster Command Reference v1.02 for PT-P750W/PT-E550W printers. Key features:

- **Raster Graphics**: 180 DPI, 1-bit monochrome
- **Print Width**: 128 pixels (16 bytes per line)
- **Compression**: TIFF/PackBits run-length encoding
- **Status Monitoring**: SNMP-based printer status detection
- **Auto-cut Support**: Configurable cutting options

### Transport Layers

- **TCP/IP**: Network printing via port 9100 with SNMP status
- **USB**: Direct device file access (Linux/macOS)
- **HTTP**: Proxy through another PT750 instance

## Version History

### v2.0.0 (Current)
- Major Brother protocol fixes for 12mm tape compatibility
- Comprehensive font management system with upload/download
- Real-time printer status monitoring with visual indicators
- Automatic tape size detection from printer
- Metric/imperial unit conversion toggle
- Performance optimizations and UI improvements
- Enhanced Docker configuration with persistent font storage

### v0.2.1
- Fix QR code label types in Docker container

### v0.2.0  
- Add web interface

### v0.1.0
- Initial release

## Credits

This project is based on the original [pt750 project by rpedde](https://github.com/rpedde/pt750). Special thanks to **rpedde** for the foundational work on Brother printer communication and the initial implementation of the Raster Command protocol.

## Documentation

- [Brother Raster Command Reference](https://download.brother.com/welcome/docp100064/cv_pte550wp750wp710bt_eng_raster_102.pdf)
- [Brother PT-P750W Manual](https://support.brother.com/g/b/manuallist.aspx?c=us&lang=en&prod=p750weus)

## License

MIT License - See LICENSE file for details.