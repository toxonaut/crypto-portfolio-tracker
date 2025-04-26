#!/usr/bin/env python3
"""
This script generates Railway CLI commands to set the required environment variables
for Google OAuth authentication in the Crypto Portfolio Tracker application.
"""

import os
import secrets
import argparse

def generate_commands(client_id, client_secret):
    """Generate Railway CLI commands for setting environment variables."""
    # Generate a secure random secret key
    secret_key = secrets.token_hex(32)
    
    commands = [
        f"railway variables set GOOGLE_CLIENT_ID={client_id}",
        f"railway variables set GOOGLE_CLIENT_SECRET={client_secret}",
        f"railway variables set SECRET_KEY={secret_key}"
    ]
    
    return commands

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Railway CLI commands for environment variables")
    parser.add_argument("--client-id", required=True, help="Google OAuth Client ID")
    parser.add_argument("--client-secret", required=True, help="Google OAuth Client Secret")
    
    args = parser.parse_args()
    
    commands = generate_commands(args.client_id, args.client_secret)
    
    print("\nRun these commands to set up environment variables in Railway:\n")
    for cmd in commands:
        print(cmd)
    
    print("\nOr set these variables in the Railway dashboard:\n")
    print(f"GOOGLE_CLIENT_ID = {args.client_id}")
    print(f"GOOGLE_CLIENT_SECRET = {args.client_secret}")
    print(f"SECRET_KEY = {secrets.token_hex(32)}")
    
    print("\nMake sure your Google Cloud OAuth configuration has:")
    print("1. Authorized JavaScript origins: https://crypto-tracker.up.railway.app")
    print("2. Authorized redirect URI: https://crypto-tracker.up.railway.app/login/google/callback")
