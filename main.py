import sys
import subprocess
import tempfile
from pathlib import Path
import shutil


def instalar_pacote(pacote):
    """Instala um pacote via pip."""
    print(f"Instalando '{pacote}'...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--upgrade", pacote]
    )


# ==========================
# Garante que yt-dlp exista
# ==========================
try:
    import yt_dlp
except ImportError:
    instalar_pacote("yt-dlp")
    import yt_dlp


# ==========================
# Garante que FFmpeg exista
# ==========================
def garantir_ffmpeg():
    if shutil.which("ffmpeg") is not None:
        return

    print("\nFFmpeg não encontrado.")
    print("Tentando instalar automaticamente...\n")

    try:
        instalar_pacote("imageio-ffmpeg")
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

        # Faz o yt-dlp usar esse executável
        return ffmpeg

    except Exception as e:
        print("Não foi possível instalar o FFmpeg automaticamente.")
        print(e)
        sys.exit(1)


FFMPEG_LOCATION = garantir_ffmpeg()
FFMPEG_BIN = FFMPEG_LOCATION or "ffmpeg"

NOME_PADRAO = "audio_completo"
CARACTERES_INVALIDOS = '<>:"/\\|?*'


def escolher_modo():
    print("Como deseja salvar os áudios?")
    print("  [1] Separados  - um MP3 por link")
    print("  [2] Único      - todos juntos em um só MP3")
    print()

    while True:
        escolha = input("> ").strip()

        if escolha in ("1", "2"):
            return escolha

        print("Digite 1 ou 2.")


def limpar_nome(nome):
    for caractere in CARACTERES_INVALIDOS:
        nome = nome.replace(caractere, "")

    return nome.strip().rstrip(".")


def perguntar_nome_final():
    print(f"\nNome do arquivo final (ENTER para '{NOME_PADRAO}'):")

    nome = limpar_nome(input("> ").strip())

    return nome or NOME_PADRAO


def caminho_livre(pasta, nome):
    destino = pasta / f"{nome}.mp3"
    contador = 2

    while destino.exists():
        destino = pasta / f"{nome} ({contador}).mp3"
        contador += 1

    return destino


def coletar_links():
    print("Cole os links do Google Drive.")
    print("Pressione ENTER em branco para iniciar o download.\n")

    links = []

    while True:
        link = input("> ").strip()

        if not link:
            break

        links.append(link)

    return links


def escolher_arquivo(caminhos):
    existentes = [Path(c) for c in caminhos if c and Path(c).exists()]

    if not existentes:
        return None

    mp3 = [c for c in existentes if c.suffix.lower() == ".mp3"]

    return mp3[-1] if mp3 else existentes[-1]


def baixar_mp3(link, pasta):
    gerados = []

    def registrar(evento):
        if evento.get("status") == "finished":
            gerados.append(evento.get("info_dict", {}).get("filepath"))

    opcoes = {
        "format": "bestaudio/best",
        "outtmpl": str(pasta / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "postprocessor_hooks": [registrar],
    }

    if FFMPEG_LOCATION:
        opcoes["ffmpeg_location"] = FFMPEG_LOCATION

    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(link, download=True)

        arquivo = escolher_arquivo(gerados)

        if arquivo is None:
            baixados = (info or {}).get("requested_downloads") or []
            arquivo = escolher_arquivo(
                [item.get("filepath") for item in baixados]
            )

        print("✓ Concluído\n")

        return arquivo

    except Exception as e:
        print("✗ Erro:")
        print(e)
        print()

        return None


def juntar_mp3(arquivos, destino, pasta_temp):
    lista = pasta_temp / "arquivos.txt"

    linhas = [
        "file '{}'".format(
            arquivo.resolve().as_posix().replace("'", "'\\''")
        )
        for arquivo in arquivos
    ]

    lista.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    resultado = subprocess.run(
        [
            FFMPEG_BIN,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lista),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(destino),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if resultado.returncode != 0:
        print("✗ Erro ao juntar os áudios:")
        print((resultado.stderr or "").strip()[-2000:])

        return False

    return True


def baixar_separados(links):
    for i, link in enumerate(links, 1):
        print(f"[{i}/{len(links)}]")
        baixar_mp3(link, Path.cwd())

    print("Todos os downloads finalizaram.")


def baixar_unico(links, nome_final):
    pasta_temp = Path(tempfile.mkdtemp(prefix="drive_mp3_"))

    try:
        arquivos = []

        for i, link in enumerate(links, 1):
            print(f"[{i}/{len(links)}]")
            arquivo = baixar_mp3(link, pasta_temp)

            if arquivo is not None:
                arquivos.append(arquivo)

        if not arquivos:
            print("Nenhum áudio foi baixado.")
            return

        destino = caminho_livre(Path.cwd(), nome_final)

        if len(arquivos) == 1:
            shutil.move(str(arquivos[0]), str(destino))
        else:
            print(f"Juntando {len(arquivos)} áudios...")

            if not juntar_mp3(arquivos, destino, pasta_temp):
                return

        print(f"Arquivo final: {destino.name}")

    finally:
        shutil.rmtree(pasta_temp, ignore_errors=True)


def main():
    modo = escolher_modo()
    nome_final = perguntar_nome_final() if modo == "2" else None

    print()
    links = coletar_links()

    if not links:
        print("Nenhum link informado.")
        return

    print(f"\nBaixando {len(links)} arquivo(s)...\n")

    if modo == "1":
        baixar_separados(links)
    else:
        baixar_unico(links, nome_final)


if __name__ == "__main__":
    main()
