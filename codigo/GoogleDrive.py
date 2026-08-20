import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CARPETA_CODIGO = os.path.dirname(os.path.abspath(__file__))
CARPETA_PROYECTO = os.path.dirname(CARPETA_CODIGO)
CONFIG_DIR = os.path.join(CARPETA_PROYECTO, 'config')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'google_drive.json')
TOKEN_PATH = os.path.join(CONFIG_DIR, 'google_token.json')

SCOPES = ['https://www.googleapis.com/auth/drive.file']


def _cargar_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def autenticar():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            config = _cargar_config()
            flow = InstalledAppFlow.from_client_config(
                {
                    'web': {
                        'client_id': config['client_id'],
                        'client_secret': config['client_secret'],
                        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                        'token_uri': 'https://oauth2.googleapis.com/token',
                    }
                },
                SCOPES,
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as f:
            f.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)


def _borrar_archivos_carpeta(service, folder_id):
    resultados = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields='files(id)',
        pageSize=100,
    ).execute()
    archivos = resultados.get('files', [])
    for archivo in archivos:
        service.files().delete(fileId=archivo['id']).execute()
    return len(archivos)


def subir_listas(archivos, folder_id):
    """Borra los archivos viejos de la carpeta y sube los nuevos.
    archivos = lista de rutas locales (.xlsx, .pdf)
    folder_id = ID de la carpeta en Google Drive
    Returns: cantidad de archivos subidos, o None si fallo."""
    try:
        service = autenticar()
        borados = _borrar_archivos_carpeta(service, folder_id)
        subidos = 0
        for ruta in archivos:
            if not os.path.exists(ruta):
                continue
            nombre = os.path.basename(ruta)
            mime = ('application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet' if nombre.endswith('.xlsx')
                    else 'application/pdf')
            media = MediaFileUpload(ruta, mimetype=mime, resumable=True)
            service.files().create(
                body={'name': nombre, 'parents': [folder_id]},
                media_body=media,
                fields='id',
            ).execute()
            subidos += 1
        return subidos
    except Exception as e:
        print(f'  (Error al subir a Google Drive: {e})')
        return None
