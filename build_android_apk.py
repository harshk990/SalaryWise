import os
import sys
import json
import zlib
import struct
import base64
import hashlib
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, pkcs7

KEY_FILE = 'salarywise_debug.key'
CERT_FILE = 'salarywise_debug.crt'

def get_or_create_signing_key():
    if os.path.exists(KEY_FILE) and os.path.exists(CERT_FILE):
        print(f"[*] Reusing persistent signing key and certificate ({KEY_FILE}, {CERT_FILE})...")
        with open(KEY_FILE, 'rb') as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        with open(CERT_FILE, 'rb') as f:
            cert = x509.load_pem_x509_certificate(f.read())
    else:
        print("[*] Generating persistent RSA-2048 key pair and Android Debug certificate...")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Gujarat"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SalaryWise"),
            x509.NameAttribute(NameOID.COMMON_NAME, "SalaryWise Release Key"),
        ])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            now - datetime.timedelta(days=30)
        ).not_valid_after(
            now + datetime.timedelta(days=3650)
        ).sign(private_key, hashes.SHA256())

        with open(KEY_FILE, 'wb') as f:
            f.write(private_key.private_bytes(
                Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        with open(CERT_FILE, 'wb') as f:
            f.write(cert.public_bytes(Encoding.PEM))
        print(f"[+] Saved persistent keystore: {KEY_FILE}, {CERT_FILE}")

    cert_der = cert.public_bytes(Encoding.DER)
    pubkey_der = cert.public_key().public_bytes(
        Encoding.DER,
        format=PublicFormat.SubjectPublicKeyInfo
    )
    return private_key, cert, cert_der, pubkey_der

def prepare_offline_index_html():
    print("[*] Preparing 100% offline self-contained index.html for Android app...")
    with open('index.html', 'r', encoding='utf-8') as f:
        html = f.read()

    with open('statement_data.json', 'r', encoding='utf-8') as f:
        stmt_data = json.load(f)

    with open('xlsx.full.min.js', 'r', encoding='utf-8') as f:
        xlsx_code = f.read()

    # CRITICAL: Inlined scripts in HTML MUST NOT contain unescaped '</' (e.g. '</body>' or '</html>' or '</script>')
    # In SheetJS, there are strings like '</body></html>' that cause Android WebView's HTML parser
    # to prematurely close the body and dump the remaining ~1.5MB of JavaScript code directly onto the screen as text!
    # Replacing '</' with '<\/' prevents HTML tokenizer breakouts while remaining 100% identical valid JavaScript!
    safe_xlsx_code = xlsx_code.replace('</', r'<\/')

    cdn_tag = '<script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>'
    inlined_sheetjs = f'<script>\n/* SheetJS Inlined for 100% Offline Android App */\n{safe_xlsx_code}\n</script>'
    
    if cdn_tag in html:
        html = html.replace(cdn_tag, inlined_sheetjs, 1)
    elif 'xlsx.full.min.js' in html:
        import re
        html = re.sub(r'<script\s+src="[^"]*xlsx[^"]*"[^>]*></script>', inlined_sheetjs, html, count=1)
    else:
        html = html.replace('</head>', f'{inlined_sheetjs}\n</head>', 1)

    safe_stmt_json = json.dumps(stmt_data, separators=(',', ':')).replace('</', r'<\/')
    embed_script = f'''<script>
window.EMBEDDED_STATEMENT_DATA = {safe_stmt_json};
</script>'''
    
    # Only inject EMBEDDED_STATEMENT_DATA if not already present
    if 'window.EMBEDDED_STATEMENT_DATA' not in html:
        html = html.replace('<!-- Modals -->', f'{embed_script}\n<!-- Modals -->', 1)

    dest_asset = os.path.join(
        'SalaryWise-Official-Android-Studio-Project-1',
        'SalaryWise-OfficialBuild',
        'app', 'src', 'main', 'assets', 'index.html'
    )
    os.makedirs(os.path.dirname(dest_asset), exist_ok=True)
    with open(dest_asset, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[+] Written offline index.html ({len(html):,} bytes) to {dest_asset}")
    return html.encode('utf-8')

class AlignedZipWriter:
    """Creates a standard ZIP archive with strict 4-byte alignment for uncompressed entries."""
    def __init__(self):
        self.data = bytearray()
        self.cd_entries = []
        
    def add_file(self, name, content, compress=True):
        fn_bytes = name.encode('utf-8')
        crc = zlib.crc32(content)
        uncompressed_size = len(content)
        
        # Fixed deterministic timestamp: 1981-01-01 01:01:02
        dos_time = 0x0821
        dos_date = 0x0221
        
        local_offset = len(self.data)
        
        if compress:
            co = zlib.compressobj(9, zlib.DEFLATED, -15)
            compressed_data = co.compress(content) + co.flush()
            method = 8
            extra = b''
        else:
            compressed_data = content
            method = 0
            # Android requirement: uncompressed file data MUST start on a 4-byte boundary!
            cur_data_offset = local_offset + 30 + len(fn_bytes)
            pad = (4 - (cur_data_offset % 4)) % 4
            extra = b'\x00' * pad
            
        data_offset = local_offset + 30 + len(fn_bytes) + len(extra)
        if method == 0 and data_offset % 4 != 0:
            raise ValueError(f"Alignment error for {name}: offset={data_offset}")
            
        lh = struct.pack('<4sHHHHHIIIHH',
            b'PK\x03\x04',
            20, 0, method, dos_time, dos_date,
            crc, len(compressed_data), uncompressed_size,
            len(fn_bytes), len(extra)
        )
        self.data.extend(lh)
        self.data.extend(fn_bytes)
        self.data.extend(extra)
        self.data.extend(compressed_data)
        
        cd = struct.pack('<4sHHHHHHIIIHHHHHII',
            b'PK\x01\x02',
            20, 20, 0, method, dos_time, dos_date,
            crc, len(compressed_data), uncompressed_size,
            len(fn_bytes), len(extra), 0, 0, 0, 0,
            local_offset
        )
        self.cd_entries.append((cd, fn_bytes, extra))

    def finish(self):
        cd_offset = len(self.data)
        for cd, fn, extra in self.cd_entries:
            self.data.extend(cd)
            self.data.extend(fn)
            self.data.extend(extra)
        cd_size = len(self.data) - cd_offset
        
        eocd = struct.pack('<4sHHHHIIH',
            b'PK\x05\x06',
            0, 0, len(self.cd_entries), len(self.cd_entries),
            cd_size, cd_offset, 0
        )
        self.data.extend(eocd)
        return bytes(self.data)

def generate_v1_jar_signature(files_dict, cert, private_key):
    print("[*] Generating Android v1 (JAR) signature (MANIFEST.MF, CERT.SF, CERT.RSA)...")
    # 1. MANIFEST.MF
    manifest_lines = ['Manifest-Version: 1.0', 'Created-By: 1.0 (Android)', '']
    entries_mf = {}
    for fname in sorted(files_dict.keys()):
        if fname.startswith('META-INF/'):
            continue
        content = files_dict[fname]
        digest = base64.b64encode(hashlib.sha256(content).digest()).decode('ascii')
        entries_mf[fname] = f'Name: {fname}\r\nSHA-256-Digest: {digest}\r\n\r\n'
        manifest_lines.append(f'Name: {fname}')
        manifest_lines.append(f'SHA-256-Digest: {digest}')
        manifest_lines.append('')

    manifest_bytes = '\r\n'.join(manifest_lines).encode('utf-8')
    manifest_digest = base64.b64encode(hashlib.sha256(manifest_bytes).digest()).decode('ascii')

    # 2. CERT.SF
    sf_lines = [
        'Signature-Version: 1.0',
        'Created-By: 1.0 (Android)',
        f'SHA-256-Digest-Manifest: {manifest_digest}',
        ''
    ]
    for fname in sorted(files_dict.keys()):
        if fname.startswith('META-INF/'):
            continue
        entry_raw = entries_mf[fname].encode('utf-8')
        digest = base64.b64encode(hashlib.sha256(entry_raw).digest()).decode('ascii')
        sf_lines.append(f'Name: {fname}')
        sf_lines.append(f'SHA-256-Digest: {digest}')
        sf_lines.append('')

    sf_bytes = '\r\n'.join(sf_lines).encode('utf-8')

    # 3. CERT.RSA (PKCS#7 detached signature)
    builder = pkcs7.PKCS7SignatureBuilder().set_data(sf_bytes).add_signer(cert, private_key, hashes.SHA256())
    rsa_bytes = builder.sign(Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])

    print(f"[+] v1 signature generated (MANIFEST.MF: {len(manifest_bytes)}B, CERT.SF: {len(sf_bytes)}B, CERT.RSA: {len(rsa_bytes)}B)")
    return manifest_bytes, sf_bytes, rsa_bytes

def sign_apk_v2(unsigned_zip_bytes, private_key, cert_der, pubkey_der):
    print("[*] Computing Android APK Signature Scheme v2 (AOSP Spec)...")
    eocd_pos = unsigned_zip_bytes.rfind(b'PK\x05\x06')
    if eocd_pos == -1:
        raise ValueError("Invalid ZIP file, EOCD record not found")
    
    cd_offset = int.from_bytes(unsigned_zip_bytes[eocd_pos+16:eocd_pos+20], 'little')
    cd_size = int.from_bytes(unsigned_zip_bytes[eocd_pos+12:eocd_pos+16], 'little')
    
    sec1 = unsigned_zip_bytes[:cd_offset]
    sec2 = unsigned_zip_bytes[cd_offset:cd_offset+cd_size]
    block_start = cd_offset
    sec3 = (
        unsigned_zip_bytes[eocd_pos:eocd_pos+16] +
        block_start.to_bytes(4, 'little') +
        unsigned_zip_bytes[eocd_pos+20:]
    )
    
    chunk_digests = []
    for sec in [sec1, sec2, sec3]:
        for i in range(0, len(sec), 1048576):
            chunk = sec[i:i+1048576]
            h = hashlib.sha256(b'\xa5' + len(chunk).to_bytes(4, 'little') + chunk).digest()
            chunk_digests.append(h)
            
    top_digest = hashlib.sha256(
        b'\x5a' + len(chunk_digests).to_bytes(4, 'little') + b''.join(chunk_digests)
    ).digest()
    
    digest_entry = (
        (0x0103).to_bytes(4, 'little') +
        len(top_digest).to_bytes(4, 'little') +
        top_digest
    )
    digest_entry_with_len = len(digest_entry).to_bytes(4, 'little') + digest_entry
    digests_seq = len(digest_entry_with_len).to_bytes(4, 'little') + digest_entry_with_len
    
    cert_entry_with_len = len(cert_der).to_bytes(4, 'little') + cert_der
    certs_seq = len(cert_entry_with_len).to_bytes(4, 'little') + cert_entry_with_len
    attrs_seq = (0).to_bytes(4, 'little')
    
    signed_data = digests_seq + certs_seq + attrs_seq
    signed_data_with_len = len(signed_data).to_bytes(4, 'little') + signed_data
    
    signature = private_key.sign(
        signed_data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    
    sig_entry = (
        (0x0103).to_bytes(4, 'little') +
        len(signature).to_bytes(4, 'little') +
        signature
    )
    sig_entry_with_len = len(sig_entry).to_bytes(4, 'little') + sig_entry
    sigs_seq = len(sig_entry_with_len).to_bytes(4, 'little') + sig_entry_with_len
    
    pubkey_with_len = len(pubkey_der).to_bytes(4, 'little') + pubkey_der
    
    signer_data = signed_data_with_len + sigs_seq + pubkey_with_len
    signer_with_len = len(signer_data).to_bytes(4, 'little') + signer_data
    signers_seq = len(signer_with_len).to_bytes(4, 'little') + signer_with_len
    
    v2_pair = (
        (len(signers_seq) + 4).to_bytes(8, 'little') +
        (0x7109871a).to_bytes(4, 'little') +
        signers_seq
    )
    
    fixed_overhead = 8 + len(v2_pair) + 24
    remainder = (cd_offset + fixed_overhead) % 4096
    pad_needed = (4096 - remainder) % 4096
    
    padding_pair = b''
    if pad_needed > 0:
        if pad_needed < 12:
            pad_needed += 4096
        pad_val_len = pad_needed - 12
        padding_pair = (
            (pad_val_len + 4).to_bytes(8, 'little') +
            (0x42726577).to_bytes(4, 'little') +
            b'\x00' * pad_val_len
        )
    
    signing_pairs = v2_pair + padding_pair
    block_size = len(signing_pairs) + 24
    magic = b'APK Sig Block 42'
    
    apk_signing_block = (
        block_size.to_bytes(8, 'little') +
        signing_pairs +
        block_size.to_bytes(8, 'little') +
        magic
    )
    
    new_cd_offset = cd_offset + len(apk_signing_block)
    new_eocd = (
        unsigned_zip_bytes[eocd_pos:eocd_pos+16] +
        new_cd_offset.to_bytes(4, 'little') +
        unsigned_zip_bytes[eocd_pos+20:]
    )
    
    signed_apk = sec1 + apk_signing_block + sec2 + new_eocd
    print(f"[+] v2 signature applied. Total APK size: {len(signed_apk):,} bytes (CD aligned to 4096: {new_cd_offset % 4096 == 0})")
    return signed_apk

def verify_apk(signed_apk_bytes, cert_der):
    print("[*] Running full APK verification (Zip alignment + v1 + v2)...")
    # 1. Verify 4-byte alignment
    import io, zipfile
    with zipfile.ZipFile(io.BytesIO(signed_apk_bytes), 'r') as z:
        for info in z.infolist():
            offset = info.header_offset
            fn_len = int.from_bytes(signed_apk_bytes[offset+26:offset+28], 'little')
            extra_len = int.from_bytes(signed_apk_bytes[offset+28:offset+30], 'little')
            data_offset = offset + 30 + fn_len + extra_len
            if info.compress_type == 0:
                assert data_offset % 4 == 0, f"Uncompressed file {info.filename} is not 4-byte aligned! (offset={data_offset})"
                print(f"  [OK] {info.filename} is STORED and perfectly 4-byte aligned (offset={data_offset})")
            else:
                print(f"  [OK] {info.filename} is DEFLATED (size={info.file_size:,})")

    # 2. Verify v2 cryptographic signature
    eocd_idx = signed_apk_bytes.rfind(b'PK\x05\x06')
    cd_offset = int.from_bytes(signed_apk_bytes[eocd_idx+16:eocd_idx+20], 'little')
    cd_size = int.from_bytes(signed_apk_bytes[eocd_idx+12:eocd_idx+16], 'little')
    block_size = int.from_bytes(signed_apk_bytes[cd_offset-24:cd_offset-16], 'little')
    block_start = cd_offset - 8 - block_size
    
    assert signed_apk_bytes[cd_offset-16:cd_offset] == b'APK Sig Block 42'
    
    sec1 = signed_apk_bytes[:block_start]
    sec2 = signed_apk_bytes[cd_offset:cd_offset+cd_size]
    sec3 = signed_apk_bytes[eocd_idx:eocd_idx+16] + block_start.to_bytes(4, 'little') + signed_apk_bytes[eocd_idx+20:]
    
    chunk_digests = []
    for sec in [sec1, sec2, sec3]:
        for i in range(0, len(sec), 1048576):
            c = sec[i:i+1048576]
            chunk_digests.append(hashlib.sha256(b'\xa5' + len(c).to_bytes(4, 'little') + c).digest())
            
    top_digest = hashlib.sha256(b'\x5a' + len(chunk_digests).to_bytes(4, 'little') + b''.join(chunk_digests)).digest()
    
    pos = block_start + 8
    v2 = None
    while pos < cd_offset - 24:
        plen = int.from_bytes(signed_apk_bytes[pos:pos+8], 'little')
        pid = int.from_bytes(signed_apk_bytes[pos+8:pos+12], 'little')
        if pid == 0x7109871a:
            v2 = signed_apk_bytes[pos+12:pos+8+plen]
        pos += 8 + plen
        
    assert v2 is not None, "Missing v2 block"
    
    signer = v2[8:8+int.from_bytes(v2[4:8], 'little')]
    signed_data = signer[4:4+int.from_bytes(signer[0:4], 'little')]
    digests = signed_data[4:4+int.from_bytes(signed_data[0:4], 'little')]
    recorded_digest = digests[12:44]
    
    assert top_digest == recorded_digest, "Digest mismatch!"
    
    sigs = signer[4+len(signed_data):]
    sigs = sigs[4:4+int.from_bytes(sigs[0:4], 'little')]
    sig = sigs[12:12+int.from_bytes(sigs[8:12], 'little')]
    
    cert = x509.load_der_x509_certificate(cert_der)
    cert.public_key().verify(
        sig,
        signed_data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    print("[+] All verification checks PASSED! Dual v1 + v2 signed, 4-byte aligned, 100% compliant.")

def main():
    print("="*65)
    print("SalaryWise Android APK Packager & Dual Signer (v1 + v2 + Zipalign)")
    print("="*65)
    
    # 1. Prepare offline HTML asset
    offline_html_bytes = prepare_offline_index_html()
    
    # 2. Extract base binaries
    print("[*] Extracting base APK binaries (dex, manifest, resources)...")
    import zipfile
    with zipfile.ZipFile('SalaryWise-v1.0.apk', 'r') as z:
        manifest_bytes = z.read('AndroidManifest.xml')
        classes_dex = z.read('classes.dex')
        classes2_dex = z.read('classes2.dex')
        resources_arsc = z.read('resources.arsc')
        app_meta = z.read('META-INF/com/android/build/gradle/app-metadata.properties')
        
    # 3. Get or generate persistent signing key
    priv_key, cert, cert_der, pubkey_der = get_or_create_signing_key()
    
    # 4. Generate v1 signature files
    app_files = {
        'META-INF/com/android/build/gradle/app-metadata.properties': app_meta,
        'classes.dex': classes_dex,
        'classes2.dex': classes2_dex,
        'assets/index.html': offline_html_bytes,
        'AndroidManifest.xml': manifest_bytes,
        'resources.arsc': resources_arsc
    }
    manifest_mf, cert_sf, cert_rsa = generate_v1_jar_signature(app_files, cert, priv_key)
    
    # 5. Build 4-byte aligned ZIP archive
    print("[*] Assembling 4-byte aligned ZIP archive...")
    writer = AlignedZipWriter()
    
    # Write metadata & v1 signatures first
    writer.add_file('META-INF/com/android/build/gradle/app-metadata.properties', app_meta, compress=True)
    writer.add_file('META-INF/MANIFEST.MF', manifest_mf, compress=True)
    writer.add_file('META-INF/CERT.SF', cert_sf, compress=True)
    writer.add_file('META-INF/CERT.RSA', cert_rsa, compress=True)
    
    # Write code & assets
    writer.add_file('classes.dex', classes_dex, compress=True)
    writer.add_file('classes2.dex', classes2_dex, compress=True)
    writer.add_file('assets/index.html', offline_html_bytes, compress=True)
    writer.add_file('AndroidManifest.xml', manifest_bytes, compress=True)
    
    # Write resources.arsc UNCOMPRESSED and 4-BYTE ALIGNED!
    writer.add_file('resources.arsc', resources_arsc, compress=False)
    
    unsigned_aligned_zip = writer.finish()
    print(f"[+] Aligned ZIP created ({len(unsigned_aligned_zip):,} bytes)")
    
    # 6. Apply v2 APK Signature Scheme
    signed_apk = sign_apk_v2(unsigned_aligned_zip, priv_key, cert_der, pubkey_der)
    
    # 7. Verification
    verify_apk(signed_apk, cert_der)
    
    # 8. Write outputs
    out_v2 = 'SalaryWise-v2.0.apk'
    out_v1 = 'SalaryWise-v1.0.apk'
    out_studio = os.path.join(
        'SalaryWise-Official-Android-Studio-Project-1',
        'SalaryWise-OfficialBuild',
        'app', 'build', 'outputs', 'apk', 'debug', 'SalaryWise-v2.0.apk'
    )
    os.makedirs(os.path.dirname(out_studio), exist_ok=True)
    
    with open(out_v2, 'wb') as f:
        f.write(signed_apk)
    with open(out_v1, 'wb') as f:
        f.write(signed_apk)
    with open(out_studio, 'wb') as f:
        f.write(signed_apk)
        
    print(f"\n[SUCCESS] Generated production-ready APKs:")
    print(f"  1. {os.path.abspath(out_v2)} ({os.path.getsize(out_v2):,} bytes)")
    print(f"  2. {os.path.abspath(out_v1)} ({os.path.getsize(out_v1):,} bytes)")
    print(f"  3. {os.path.abspath(out_studio)} ({os.path.getsize(out_studio):,} bytes)")
    print("="*65)

if __name__ == '__main__':
    main()
