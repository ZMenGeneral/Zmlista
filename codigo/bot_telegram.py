# -*- coding: utf-8 -*-
"""
bot_telegram.py
Bot de Telegram para descargar publicaciones de Instagram, TikTok y YouTube.

Como configurarlo:
    1. En Telegram busca el usuario @BotFather, envia /newbot, elige un
       nombre y un nombre de usuario, y copia el TOKEN que te da.
    2. Guarda el token en config/bot_token.txt (solo el token, sin espacios).
       (O usa la variable de entorno BOT_TOKEN)
    3. Instala las dependencias (una sola vez):
         pip install python-telegram-bot yt-dlp
    4. Ejecuta el bot y dejalo abierto:
         python bot_telegram.py
    5. En Telegram abre el chat con tu bot y enviame el enlace de la
       publicacion que quieras descargar.

Nota: el bot corre en esta PC. Mientras el programa este abierto, responde.
"""
import asyncio
import os
import re
import shutil
import sys
import tempfile

from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

RAIZ = os.path.dirname(os.path.abspath(__file__))
PROYECTO = os.path.dirname(RAIZ)
CONFIG = os.path.join(PROYECTO, 'config')

LIMITE_ARCHIVO = 45 * 1024 * 1024  # 45 MB (Telegram admite ~50 MB por archivo)


def leer_token():
    env = os.environ.get('BOT_TOKEN')
    if env:
        return env.strip()
    ruta = os.path.join(CONFIG, 'bot_token.txt')
    if os.path.isfile(ruta):
        with open(ruta, encoding='utf-8') as f:
            tok = f.read().strip()
        if tok:
            return tok
    return ''


def detectar_plataforma(url):
    u = url.lower()
    if 'youtube.com' in u or 'youtu.be' in u:
        return 'YouTube'
    if 'tiktok.com' in u:
        return 'TikTok'
    if 'instagram.com' in u:
        return 'Instagram'
    return 'Desconocido'


def descargar_media(url):
    """Descarga el video/imagen con yt-dlp. Devuelve (ruta, carpeta_temporal)."""
    import yt_dlp

    carpeta = tempfile.mkdtemp(prefix='bot_telegram_')
    opciones = {
        'format': 'best[ext=mp4][height<=1080]/best',
        'outtmpl': os.path.join(carpeta, '%(title).60s [%(id)s].%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'windowsfilenames': True,
        'merge_output_format': 'mp4',
        'max_filesize': LIMITE_ARCHIVO,
        'http_headers': {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0 Safari/537.36'),
        },
    }
    # ffmpeg incluido por imageio-ffmpeg (necesario para unir video+audio)
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.isfile(ffmpeg):
            opciones['ffmpeg_location'] = os.path.dirname(ffmpeg)
    except Exception:
        pass
    cookies = os.path.join(CONFIG, 'cookies.txt')
    if os.path.isfile(cookies):
        opciones['cookiefile'] = cookies

    with yt_dlp.YoutubeDL(opciones) as ydl:
        info = ydl.extract_info(url, download=True)
        ruta = ydl.prepare_filename(info)
        if not os.path.isfile(ruta):
            archivos = [os.path.join(carpeta, f) for f in os.listdir(carpeta)]
            archivos = [a for a in archivos if os.path.isfile(a)]
            if archivos:
                ruta = max(archivos, key=os.path.getsize)
    return ruta, carpeta


async def inicio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Hola! Soy tu bot descargador.\n\n'
        'Enviame un enlace de:\n'
        '   - YouTube (video)\n'
        '   - TikTok\n'
        '   - Instagram (reel o publicacion)\n\n'
        'Y te devuelvo el archivo para descargarlo.\n\n'
        'Limite: 45 MB por archivo.')


async def manejar_mensaje(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = (update.message.text or '').strip()
    if not texto:
        return

    match = re.search(r'https?://\S+', texto)
    if not match:
        await update.message.reply_text('Escribe o pega el enlace de la publicacion.')
        return
    url = match.group(0).rstrip('.,;')

    plataforma = detectar_plataforma(url)
    if plataforma == 'Desconocido':
        await update.message.reply_text(
            'Ese enlace no es de Instagram, TikTok ni YouTube.')
        return

    msg = await update.message.reply_text(
        f'Descargando de {plataforma}...\n{url[:90]}')

    try:
        ruta, carpeta = await asyncio.to_thread(descargar_media, url)
    except Exception as e:
        motivo = str(e)
        if 'max_filesize' in motivo:
            motivo = 'El archivo es mayor a 45 MB.'
        elif ('not available to everyone' in motivo or 'login' in motivo.lower()
              or 'private' in motivo.lower() or 'sign in' in motivo.lower()
              or 'cookie' in motivo.lower()):
            motivo = ('Instagram/TikTok pide iniciar sesion para ver esta publicacion.\n\n'
                      'Para arreglarlo:\n'
                      '1. En Chrome inicia sesion en instagram.com\n'
                      '2. Instala la extension "Get cookies.txt LOCALLY"\n'
                      '3. Abre instagram.com y exporta las cookies\n'
                      '4. Guarda el archivo como config/cookies.txt\n'
                      'Y vuelve a enviarme el enlace.')
        await msg.edit_text('No pude descargarlo.\n\n' + motivo)
        return

    try:
        tam = os.path.getsize(ruta) / (1024 * 1024)
        ext = os.path.splitext(ruta)[1].lower()
        caption = f'{plataforma}  |  {tam:.1f} MB'
        with open(ruta, 'rb') as f:
            if ext in ('.jpg', '.jpeg', '.png', '.webp'):
                await update.message.reply_photo(f, caption=caption)
            elif ext in ('.mp4', '.mov', '.webm', '.mkv', '.avi'):
                await update.message.reply_video(f, caption=caption,
                                                 supports_streaming=True)
            else:
                await update.message.reply_document(f, caption=caption)
    except Exception as e:
        await msg.edit_text(f'No pude enviarte el archivo.\nMotivo: {str(e)[:200]}')
        return
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
        try:
            await msg.delete()
        except Exception:
            pass


def main():
    token = leer_token()
    if not token:
        print()
        print('  ERROR: No encontre el token del bot.')
        print('  1. En Telegram abre @BotFather y crea un bot con /newbot.')
        print('  2. Copia el token y guardalo en:')
        print('     ' + os.path.join(CONFIG, 'bot_token.txt'))
        print()
        sys.exit(1)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler('start', inicio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                   manejar_mensaje))

    print()
    print('  Bot de descargas en linea.')
    print('  En Telegram abre tu bot y enviale un enlace.')
    print('  Ctrl+C para detenerlo.')
    print()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
