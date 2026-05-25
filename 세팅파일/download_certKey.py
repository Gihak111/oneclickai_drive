#!/usr/bin/env python3
import urllib.request
from pathlib import Path
import tempfile
import shutil
import os
import pwd
import grp
import subprocess

BASE_URL = "https://images.oneclickai.work"
PREFIX = "keyCert"

CERT_URL = f"{BASE_URL}/{PREFIX}/cert.pem"
KEY_URL  = f"{BASE_URL}/{PREFIX}/key.pem"

DEST_CERT = Path("/etc/caddy/certs/auto.oneclickai.work/cert.pem")
DEST_KEY  = Path("/etc/caddy/certs/auto.oneclickai.work/key.pem")

def download(url: str, out_path: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "cert-downloader/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        if getattr(r, "status", 200) != 200:
            raise RuntimeError(f"Download failed: {url}")
        out_path.write_bytes(r.read())

# 1) 폴더 생성
DEST_CERT.parent.mkdir(parents=True, exist_ok=True)

# 2) 임시로 다운로드 후 원자적으로 교체
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    tmp_cert = td / "cert.pem"
    tmp_key  = td / "key.pem"

    print("Downloading:", CERT_URL)
    download(CERT_URL, tmp_cert)

    print("Downloading:", KEY_URL)
    download(KEY_URL, tmp_key)

    shutil.move(str(tmp_cert), str(DEST_CERT))
    shutil.move(str(tmp_key),  str(DEST_KEY))

# 3) 권한 설정 (root:caddy, 640)
uid = pwd.getpwnam("root").pw_uid
gid = grp.getgrnam("caddy").gr_gid

os.chown(DEST_CERT, uid, gid)
os.chown(DEST_KEY,  uid, gid)
os.chmod(DEST_CERT, 0o640)
os.chmod(DEST_KEY,  0o640)

# 4) Caddy reload
# print("Reloading caddy...")
# subprocess.run(["systemctl", "reload", "caddy"], check=True)

print("Done.")