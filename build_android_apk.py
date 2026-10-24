import os
import sys
import json
import zipfile
import hashlib
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

def generate_key_and_cert():
    print("[*] Generating RSA-2048 key pair and self-signed Android Debug certificate...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Android"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Android Debug"),
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
        now - datetime.timedelta(days=1)
    ).not_valid_after(
        now + datetime.timedelta(days=3650)
    ).sign(private_key, hashes.SHA256())
    
    cert_der = cert.public_bytes(Encoding.DER)
    pubkey_der = cert.public_key().public_bytes(
        Encoding.DER,
        format=PublicFormat.SubjectPublicKeyInfo
    )
    return private_key, cert_der, pubkey_der

def prepare_offline_index_html():
    print("[*] Preparing 100% offline self-contained index.html for Android app...")
    with open('index.html', 'r', encoding='utf-8') as f:
        html = f.read()

    with open('statement_data.json', 'r', encoding='utf-8') as f:
        stmt_data = json.load(f)

    # In Android WebView, window.SalaryWiseAndroid may be exposed
    # Replace CDN SheetJS with inlined SheetJS
    with open('xlsx.full.min.js', 'r', encoding='utf-8') as f:
        xlsx_code = f.read()

    cdn_tag = '<script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>'
    inlined_sheetjs = f'<script>\n/* SheetJS Inlined for 100% Offline Android App */\n{xlsx_code}\n</script>'
    
    if cdn_tag in html:
        html = html.replace(cdn_tag, inlined_sheetjs, 1)
    else:
        # Fallback: prepend inside head
        html = html.replace('</head>', f'{inlined_sheetjs}\n</head>', 1)

    # Embed default statement data
    embed_script = f'''
<script>
window.EMBEDDED_STATEMENT_DATA = {json.dumps(stmt_data, separators=(',', ':'))};
</script>
'''
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

def sign_apk_v2(unsigned_zip_bytes, private_key, cert_der, pubkey_der):
    print("[*] Computing Android APK Signature Scheme v2 (RFC/AOSP Spec)...")
    # 1. Locate Central Directory & EOCD in unsigned ZIP
    eocd_pos = unsigned_zip_bytes.rfind(b'PK\x05\x06')
    if eocd_pos == -1:
        raise ValueError("Invalid ZIP file, EOCD record not found")
    
    cd_offset = int.from_bytes(unsigned_zip_bytes[eocd_pos+16:eocd_pos+20], 'little')
    cd_size = int.from_bytes(unsigned_zip_bytes[eocd_pos+12:eocd_pos+16], 'little')
    
    # 2. Split into 3 sections for hashing
    sec1 = unsigned_zip_bytes[:cd_offset]
    sec2 = unsigned_zip_bytes[cd_offset:cd_offset+cd_size]
    # For hashing section 3 (EOCD), replace cd_offset with the eventual start of APK Signing Block
    # The APK Signing Block will be placed at exactly cd_offset!
    # So block_start is at cd_offset in unsigned_zip_bytes!
    block_start = cd_offset
    sec3 = (
        unsigned_zip_bytes[eocd_pos:eocd_pos+16] +
        block_start.to_bytes(4, 'little') +
        unsigned_zip_bytes[eocd_pos+20:]
    )
    
    # 3. 1MB chunk hashing
    chunk_digests = []
    for sec in [sec1, sec2, sec3]:
        for i in range(0, len(sec), 1048576):
            chunk = sec[i:i+1048576]
            h = hashlib.sha256(b'\xa5' + len(chunk).to_bytes(4, 'little') + chunk).digest()
            chunk_digests.append(h)
            
    # 4. Top-level content digest
    top_digest = hashlib.sha256(
        b'\x5a' + len(chunk_digests).to_bytes(4, 'little') + b''.join(chunk_digests)
    ).digest()
    print(f"[+] Top-level content digest computed: {top_digest.hex()}")
    
    # 5. Build signed_data block:
    # digests sequence
    # 0x0103 = RSASSA-PKCS1-v1_5 with SHA-256
    digest_entry = (
        (0x0103).to_bytes(4, 'little') +
        len(top_digest).to_bytes(4, 'little') +
        top_digest
    )
    digest_entry_with_len = len(digest_entry).to_bytes(4, 'little') + digest_entry
    digests_seq = len(digest_entry_with_len).to_bytes(4, 'little') + digest_entry_with_len
    
    # certificates sequence
    cert_entry_with_len = len(cert_der).to_bytes(4, 'little') + cert_der
    certs_seq = len(cert_entry_with_len).to_bytes(4, 'little') + cert_entry_with_len
    
    # additional attributes sequence (empty)
    attrs_seq = (0).to_bytes(4, 'little')
    
    signed_data = digests_seq + certs_seq + attrs_seq
    signed_data_with_len = len(signed_data).to_bytes(4, 'little') + signed_data
    
    # 6. Sign signed_data with RSA-2048 private key
    signature = private_key.sign(
        signed_data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    print(f"[+] RSA signature generated ({len(signature)} bytes)")
    
    sig_entry = (
        (0x0103).to_bytes(4, 'little') +
        len(signature).to_bytes(4, 'little') +
        signature
    )
    sig_entry_with_len = len(sig_entry).to_bytes(4, 'little') + sig_entry
    sigs_seq = len(sig_entry_with_len).to_bytes(4, 'little') + sig_entry_with_len
    
    pubkey_with_len = len(pubkey_der).to_bytes(4, 'little') + pubkey_der
    
    # 7. Assemble Signer block
    signer_data = signed_data_with_len + sigs_seq + pubkey_with_len
    signer_with_len = len(signer_data).to_bytes(4, 'little') + signer_data
    signers_seq = len(signer_with_len).to_bytes(4, 'little') + signer_with_len
    
    # 8. Assemble ID-value pair (0x7109871a = APK v2)
    v2_pair = (
        (len(signers_seq) + 4).to_bytes(8, 'little') +
        (0x7109871a).to_bytes(4, 'little') +
        signers_seq
    )
    
    # 9. Calculate padding to align the block and Central Directory to 4096 bytes
    # Current block size without padding:
    # 8 (block_size_start) + len(v2_pair) + padding + 8 (block_size_end) + 16 (magic)
    # Total added before CD = 8 + len(v2_pair) + padding + 24
    fixed_overhead = 8 + len(v2_pair) + 24
    remainder = (cd_offset + fixed_overhead) % 4096
    pad_needed = (4096 - remainder) % 4096
    
    padding_pair = b''
    if pad_needed > 0:
        # A padding pair has 8 bytes len + 4 bytes ID (0x42726577) + (pad_needed - 12) zeros
        if pad_needed < 12:
            pad_needed += 4096
        pad_val_len = pad_needed - 12
        padding_pair = (
            (pad_val_len + 4).to_bytes(8, 'little') +
            (0x42726577).to_bytes(4, 'little') +
            b'\x00' * pad_val_len
        )
    
    signing_pairs = v2_pair + padding_pair
    # Total block size: 8 + len(signing_pairs) + 24 - 8 = len(signing_pairs) + 24
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
    print(f"[+] Signed APK assembled: {len(signed_apk):,} bytes (CD aligned to 4096: {new_cd_offset % 4096 == 0})")
    return signed_apk

def verify_signed_apk(signed_apk_bytes, cert_der):
    print("[*] Verifying generated APK v2 signature...")
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
    
    # Locate v2 block in APK
    pos = block_start + 8
    v2 = None
    while pos < cd_offset - 24:
        plen = int.from_bytes(signed_apk_bytes[pos:pos+8], 'little')
        pid = int.from_bytes(signed_apk_bytes[pos+8:pos+12], 'little')
        if pid == 0x7109871a:
            v2 = signed_apk_bytes[pos+12:pos+8+plen]
        pos += 8 + plen
        
    assert v2 is not None, "Missing v2 block in verification"
    
    signer = v2[8:8+int.from_bytes(v2[4:8], 'little')]
    signed_data = signer[4:4+int.from_bytes(signer[0:4], 'little')]
    digests = signed_data[4:4+int.from_bytes(signed_data[0:4], 'little')]
    recorded_digest = digests[12:44]
    
    assert top_digest == recorded_digest, "Digest mismatch!"
    
    # Verify RSA signature
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
    print("[+] APK v2 verification PASSED 100%! Ready for Android installation.")

def main():
    print("="*60)
    print("SalaryWise Android APK Packager & Signer (AOSP v2)")
    print("="*60)
    
    # 1. Prepare offline HTML asset
    offline_html_bytes = prepare_offline_index_html()
    
    # 2. Extract base binaries from template SalaryWise-v1.0.apk
    print("[*] Extracting base APK binaries (dex, manifest, resources)...")
    with zipfile.ZipFile('SalaryWise-v1.0.apk', 'r') as z:
        manifest_bytes = z.read('AndroidManifest.xml')
        classes_dex = z.read('classes.dex')
        classes2_dex = z.read('classes2.dex')
        resources_arsc = z.read('resources.arsc')
        app_meta = z.read('META-INF/com/android/build/gradle/app-metadata.properties')
        
    # 3. Create fresh aligned unsigned ZIP archive in memory
    import io
    zip_buffer = io.BytesIO()
    
    # Use deterministic timestamp (1981-01-01 01:01:02)
    dt = (1981, 1, 1, 1, 1, 2)
    
    with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        # app-metadata
        zi = zipfile.ZipInfo('META-INF/com/android/build/gradle/app-metadata.properties', dt)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zout.writestr(zi, app_meta)
        
        # classes.dex
        zi = zipfile.ZipInfo('classes.dex', dt)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zout.writestr(zi, classes_dex)
        
        # classes2.dex
        zi = zipfile.ZipInfo('classes2.dex', dt)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zout.writestr(zi, classes2_dex)
        
        # assets/index.html (NEW updated self-contained offline version!)
        zi = zipfile.ZipInfo('assets/index.html', dt)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zout.writestr(zi, offline_html_bytes)
        
        # AndroidManifest.xml
        zi = zipfile.ZipInfo('AndroidManifest.xml', dt)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zout.writestr(zi, manifest_bytes)
        
        # resources.arsc MUST NOT BE COMPRESSED (ZIP_STORED) for Android runtime!
        zi = zipfile.ZipInfo('resources.arsc', dt)
        zi.compress_type = zipfile.ZIP_STORED
        zout.writestr(zi, resources_arsc)
        
    unsigned_zip = zip_buffer.getvalue()
    print(f"[+] Unsigned APK ZIP constructed ({len(unsigned_zip):,} bytes)")
    
    # 4. Generate key & cert
    priv_key, cert_der, pubkey_der = generate_key_and_cert()
    
    # 5. Sign APK with APK Signature Scheme v2
    signed_apk = sign_apk_v2(unsigned_zip, priv_key, cert_der, pubkey_der)
    
    # 6. Verify signed APK
    verify_signed_apk(signed_apk, cert_der)
    
    # 7. Write outputs
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
        
    print(f"\n[SUCCESS] Generated new APKs:")
    print(f"  1. {os.path.abspath(out_v2)} ({os.path.getsize(out_v2):,} bytes)")
    print(f"  2. {os.path.abspath(out_v1)} ({os.path.getsize(out_v1):,} bytes)")
    print(f"  3. {os.path.abspath(out_studio)} ({os.path.getsize(out_studio):,} bytes)")
    print("="*60)

if __name__ == '__main__':
    main()
