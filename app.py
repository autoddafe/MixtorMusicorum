import os
import random
from flask import Flask, request, redirect, session, render_template, url_for
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

app = Flask(__name__)
app.secret_key = 'una_clave_muy_secreta'  # Cámbiala por algo seguro y único

# Spotify Developer credentials
CLIENT_ID = 'afef24aa481843a988b604d1415f54f0'
CLIENT_SECRET = '258a52b25cae459ab957bb01c6a01ef2'
REDIRECT_URI = 'https://musicorum.onrender.com/callback'
SCOPE = 'playlist-modify-public playlist-modify-private playlist-read-private user-read-email user-read-private'

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path='.cache'
    )

# Página principal
@app.route('/')
def index():
    token_info = session.get('token_info', None)
    profile = None
    if token_info:
        sp = Spotify(auth=token_info['access_token'])
        try:
            profile = sp.current_user()
        except:
            session.clear()
            return redirect(url_for('index'))

    auth_url = create_spotify_oauth().get_authorize_url()
    return render_template('index.html', auth_url=auth_url, logged_in=bool(token_info), profile=profile)

# Callback de Spotify
@app.route('/callback')
def callback():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')

    if code:
        token_info = sp_oauth.get_access_token(code)
        session['token_info'] = token_info
        return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))

# Obtener token desde sesión
def get_token():
    token_info = session.get('token_info', None)
    if not token_info:
        raise Exception("No token found")
    return token_info

# Ruta para mezclar la playlist
@app.route('/mix', methods=['POST'])
def mix():
    try:
        token_info = get_token()
    except:
        return redirect('/')

    sp = Spotify(auth=token_info['access_token'])
    user = sp.current_user()

    playlist_url = request.form.get('playlist_url')
    try:
        playlist_id = playlist_url.split('/')[-1].split('?')[0]

        # Validar que la playlist existe
        playlist = sp.playlist(playlist_id)

        # Validar que el usuario autenticado es el dueño de la playlist
        if playlist['owner']['id'] != user['id']:
            return render_template(
                'index.html',
                auth_url=create_spotify_oauth().get_authorize_url(),
                logged_in=True,
                profile=user,
                error="No eres el propietario de esta playlist, no puedes modificarla."
            )

        # Obtener canciones
        tracks = []
        results = sp.playlist_items(playlist_id)
        tracks.extend(results['items'])

        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])

        # Mezclar canciones
        uris = [item['track']['uri'] for item in tracks if item['track'] and item['track']['uri']]
        random.shuffle(uris)

        # Reemplazar canciones por bloques de 100
        sp.playlist_replace_items(playlist_id, uris[:100])

        if len(uris) > 100:
            for i in range(100, len(uris), 100):
                sp.playlist_add_items(playlist_id, uris[i:i+100])

        return render_template(
            'index.html',
            auth_url=create_spotify_oauth().get_authorize_url(),
            logged_in=True,
            profile=user,
            success=True
        )

    except SpotifyException as e:
        print(f"Spotify error: {e}")
        return render_template(
            'index.html',
            auth_url=create_spotify_oauth().get_authorize_url(),
            logged_in=True,
            profile=user,
            error="Hubo un error con Spotify. Verifica el enlace o intenta de nuevo."
        )

    except Exception as e:
        print(f"Error general: {e}")
        return render_template(
            'index.html',
            auth_url=create_spotify_oauth().get_authorize_url(),
            logged_in=True,
            profile=user,
            error="Ocurrió un error inesperado. Intenta de nuevo."
        )

# Ejecutar la app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Usado por Render
    app.run(host='0.0.0.0', port=port, debug=True)
