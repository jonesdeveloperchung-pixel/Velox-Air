# product_lines/Air/main.py
import sys
import os
import yaml
import asyncio
import ssl
import socket
import datetime
import tempfile
import atexit
import shutil
from pathlib import Path

# Standalone: Root is the directory of this script
root_path = os.path.dirname(os.path.abspath(__file__))

# PyInstaller path support
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    root_path = bundle_dir
    os.chdir(os.path.dirname(sys.executable))

if root_path not in sys.path:
    sys.path.insert(0, root_path)

from core.debug import Debug
from air_server_app import VeloxAirServerApp

def generate_self_signed_cert(hostname="localhost"):
    """Generates a temporary self-signed certificate for HTTPS support."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    # Generate private key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    
    # Generate certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Velox Air"),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        # Valid for 1 year
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(hostname)]),
        critical=False,
    ).sign(key, hashes.SHA256())

    # Write to temp files
    temp_dir = tempfile.mkdtemp()
    atexit.register(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
    
    cert_path = os.path.join(temp_dir, "cert.pem")
    key_path = os.path.join(temp_dir, "key.pem")
    
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
        
    return cert_path, key_path

def load_config():
    # If frozen, config is inside the bundle
    base_dir = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
    config_path = os.path.join(base_dir, "config", "air_settings.yaml")
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

async def main():
    debug = Debug("INFO")
    config = load_config()
    
    # SSL Setup
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    
    # Check for User Certs (Next to EXE)
    user_cert_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else root_path
    cert_file = os.path.join(user_cert_dir, "certs", "cert.pem")
    key_file = os.path.join(user_cert_dir, "certs", "key.pem")
    
    # Check for Bundled Certs (Inside Bundle)
    if not (os.path.exists(cert_file) and os.path.exists(key_file)):
        cert_file = os.path.join(root_path, "certs", "cert.pem")
        key_file = os.path.join(root_path, "certs", "key.pem")

    # Final Fallback: Auto-Generate
    if not (os.path.exists(cert_file) and os.path.exists(key_file)):
        try:
            debug.info("Server", "Generating temporary self-signed SSL certificates...")
            cert_file, key_file = generate_self_signed_cert()
        except Exception as e:
            debug.error("Server", f"Failed to generate SSL certs: {e}")
            cert_file, key_file = None, None

    if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
        ssl_context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        debug.info("Server", "SSL/TLS Enabled via Certificate.")
    else:
        debug.warning("Server", "CRITICAL: No SSL Certs available. Falling back to HTTP.")
        ssl_context = None

    server = VeloxAirServerApp(config, debug, ssl_context)
    
    # Print access URLs
    import socket
    hostname = socket.gethostname()
    local_ips = socket.gethostbyname_ex(hostname)[2]
    
    web_port = config['server']['web_port']
    protocol = "https" if ssl_context else "http"
    
    debug.info("VeloxAir", "--------------------------------------------------")
    debug.info("VeloxAir", "🚀 Velox Air is running!")
    debug.info("VeloxAir", f"Secure Client: {protocol}://localhost:{web_port}")
    
    if ssl_context:
        debug.info("VeloxAir", f"Legacy Client: http://localhost:{web_port + 1}")
    
    for ip in local_ips:
        if not ip.startswith("127."):
            debug.info("VeloxAir", f"Network Access: {protocol}://{ip}:{web_port}")
            if ssl_context:
                debug.info("VeloxAir", f"Legacy Access: http://{ip}:{web_port + 1}")
                
    debug.info("VeloxAir", f"Dashboard: {protocol}://localhost:{web_port}/dashboard")
    debug.info("VeloxAir", "--------------------------------------------------")

    server = VeloxAirServerApp(config, debug, ssl_context)
    await server.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass # Clean exit on Ctrl+C
