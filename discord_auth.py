# discord_auth.py
import requests
from flask import redirect, session, url_for
import os
from models import db, User


def get_discord_login_url():
    client_id = os.getenv('DISCORD_CLIENT_ID')
    redirect_uri = os.getenv('DISCORD_REDIRECT_URI')
    return (f"https://discord.com/api/oauth2/authorize"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code&scope=identify")


def exchange_code_for_token(code):
    client_id = os.getenv('DISCORD_CLIENT_ID')
    client_secret = os.getenv('DISCORD_CLIENT_SECRET')
    redirect_uri = os.getenv('DISCORD_REDIRECT_URI')

    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'scope': 'identify'
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    response = requests.post('https://discord.com/api/oauth2/token',
                             data=data, headers=headers)
    return response.json()


def get_discord_user(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get('https://discord.com/api/users/@me', headers=headers)
    return response.json()


def get_or_create_user(discord_user_data):
    user = User.query.filter_by(discord_id=discord_user_data['id']).first()

    if not user:
        user = User(
            discord_id=discord_user_data['id'],
            discord_username=f"{discord_user_data['username']}#{discord_user_data.get('discriminator', '0')}"
        )
        db.session.add(user)
        db.session.commit()

    return user