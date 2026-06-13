#!/usr/bin/env bash

cd /home/mayltonf/Documentos/turing-smart-screen-python-main || exit 1

pkill -f "python3 main.py"
pkill -f "main.py"
pkill -f "video_native_test.py"
pkill -f "video_overlay_test.py"

sleep 7

source venv/bin/activate
python3 main.py
