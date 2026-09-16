#!/bin/zsh
# Prints the xAI key from the macOS Keychain. Never store the value in a file or repo.
security find-generic-password -s xai-api-key -w 2>/dev/null
