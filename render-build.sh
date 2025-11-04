#!/bin/bash
# Update en installeer ffmpeg
apt-get update && apt-get install -y ffmpeg
# Installeer Python dependencies
pip install -r requirements.txt
