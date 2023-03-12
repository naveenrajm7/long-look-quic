# Setup Details

## Building Chromium on Ubuntu 

To make sure of available space for chromium setup
Change HOME dir to /proj/FEC, path which has sufficient space

```bash
sudo apt install gperf
sudo apt install libnss3-dev libgdk-pixbuf2.0-dev libgtk-3-dev libxss-dev
```

Follow 
https://chromium.googlesource.com/chromium/src/+/main/docs/linux/build_instructions.md

chrome --version

## Get chrome driver 

https://chromedriver.chromium.org/getting-started
https://chromedriver.chromium.org/downloads/version-selection

## Building QUIC 

```bash
gn gen out/Debug
```

Follow
https://www.chromium.org/quic/playing-with-quic/

```bash
# server
out/Debug/quic_server --quic_response_cache_dir=/proj/FEC-HTTP/long-quic/quic-data/www.example.org   --certificate_file=net/tools/quic/certs/out/leaf_cert.pem --key_file=net/tools/quic/certs/out/leaf_cert.pkcs8

# client
out/Debug/quic_client --host=10.10.1.1 --port=6121 --disable_certificate_verification --allow_unknown_root_cert https://www.example.org/
```