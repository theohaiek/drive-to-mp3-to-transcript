import os
import sys
import time
import importlib
import subprocess
from pathlib import Path


LANGUAGE = "pt"
MODEL_SIZE = "large-v3"
MODEL_REPO = "Systran/faster-whisper-large-v3"

# TEMPERATURE precisa ser uma lista/tupla (e não um único número) para o
# fallback funcionar: se o faster-whisper detectar um trecho repetitivo
# (compression_ratio_threshold) ou de baixa confiança (log_prob_threshold) na
# temperatura 0.0, ele tenta de novo nas temperaturas seguintes em vez de
# simplesmente continuar (e repetir) o texto ruim.
TEMPERATURE = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
NO_REPEAT_NGRAM_SIZE = 3   # nunca deixa repetir a mesma sequência de 3 tokens seguidos (0 = desativado)
CONDITION_ON_PREVIOUS_TEXT = True   # usa o texto da janela anterior como contexto.
# ^ Se algum áudio específico continuar entrando em loop, mude para False:
#   perde um pouco de coerência entre janelas, mas o modelo fica bem mais
#   resistente a ficar preso repetindo.

LIMITE_AVISO_REPETICAO = 8   # linhas idênticas seguidas até soar o alarme

AUDIO_EXT = {
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus",
    ".flac", ".wma", ".mp4", ".mov", ".mkv",
}

_modelo = None
_device = None
_compute = None


def pip_install(*pacotes):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--upgrade", *pacotes]
    )


def importar(nome, pacote=None):
    try:
        return importlib.import_module(nome)
    except ImportError:
        print(f"Instalando '{pacote or nome}'...")
        pip_install(pacote or nome)
        importlib.invalidate_caches()
        return importlib.import_module(nome)


# ============================================================
# Detecção de GPU
# ============================================================

def detectar_gpu():
    """Retorna o nome da GPU NVIDIA (via nvidia-smi) ou None."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0].strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return None


def _dirs_libs_nvidia():
    """Diretórios com as DLLs de cuBLAS/cuDNN instaladas via pip."""
    try:
        import nvidia
    except ImportError:
        return []

    dirs = []

    for base in list(getattr(nvidia, "__path__", [])):
        base = Path(base)
        for comp in ("cublas", "cudnn"):
            for sub in ("bin", "lib"):
                d = base / comp / sub
                if d.is_dir():
                    dirs.append(d)

    return dirs


def preparar_cuda():
    """
    Instala (se necessário) e registra as bibliotecas CUDA que o CTranslate2
    usa. Retorna True se o ambiente CUDA ficou pronto.
    """
    dirs = _dirs_libs_nvidia()

    if not dirs:
        print("Instalando bibliotecas CUDA (cuBLAS + cuDNN)...")
        try:
            pip_install("nvidia-cublas-cu12", "nvidia-cudnn-cu12>=9.0,<10.0")
        except Exception as e:
            print("  Falha ao instalar bibliotecas CUDA:", e)
            return False

        importlib.invalidate_caches()
        dirs = _dirs_libs_nvidia()

    if not dirs:
        return False

    for d in dirs:
        os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):   # somente Windows
            try:
                os.add_dll_directory(str(d))
            except OSError:
                pass

    return True


# ============================================================
# Modelo
# ============================================================

def carregar_modelo():
    global _modelo, _device, _compute

    if _modelo is not None:
        return _modelo

    # Garante que a barra de progresso do download do modelo apareça.
    os.environ.pop("HF_HUB_DISABLE_PROGRESS_BARS", None)

    faster_whisper = importar("faster_whisper", "faster-whisper")
    huggingface_hub = importar("huggingface_hub")
    importar("tqdm")

    print()
    gpu = detectar_gpu()

    if gpu:
        print("GPU NVIDIA detectada:", gpu)
        if preparar_cuda():
            _device, _compute = "cuda", "float16"
            print("CUDA pronto. Usando GPU.")
        else:
            _device, _compute = "cpu", "int8"
            print("Não foi possível preparar o CUDA. Usando CPU.")
    else:
        _device, _compute = "cpu", "int8"
        print("Nenhuma GPU NVIDIA encontrada (ou driver ausente). Usando CPU.")

    print("Modelo :", MODEL_SIZE)
    print("Idioma :", LANGUAGE)
    print("Device :", _device, f"({_compute})")
    print()

    print("Baixando/verificando modelo (~3 GB na primeira vez)...\n")
    caminho_modelo = huggingface_hub.snapshot_download(MODEL_REPO)
    print("\nCarregando modelo...")

    try:
        _modelo = faster_whisper.WhisperModel(
            caminho_modelo, device=_device, compute_type=_compute
        )
    except Exception as e:
        if _device != "cuda":
            raise

        print("\nFalha ao iniciar na GPU:")
        print(" ", e)
        print("Voltando para CPU...\n")

        _device, _compute = "cpu", "int8"
        _modelo = faster_whisper.WhisperModel(
            caminho_modelo, device=_device, compute_type=_compute
        )

    print(f"Modelo carregado em {_device.upper()}.\n")

    return _modelo


def dispositivo():
    return f"{_device} ({_compute})" if _device else "não inicializado"


# ============================================================
# Transcrição
# ============================================================

def transcrever(audio, destino=None):
    """
    Transcreve um arquivo de áudio e grava o texto em um .txt.
    Retorna o caminho do .txt ou None em caso de erro.
    """
    audio = Path(audio)
    destino = Path(destino) if destino else audio.with_suffix(".txt")

    from tqdm import tqdm

    try:
        modelo = carregar_modelo()

        segmentos, info = modelo.transcribe(
            str(audio),
            language=LANGUAGE,
            beam_size=5,
            best_of=5,
            vad_filter=True,
            temperature=TEMPERATURE,
            condition_on_previous_text=CONDITION_ON_PREVIOUS_TEXT,
            no_repeat_ngram_size=NO_REPEAT_NGRAM_SIZE,
        )

        linhas = []
        total = max(1, round(info.duration))
        repeticoes_seguidas = 0
        aviso_disparado = False
        inicio = time.time()

        with tqdm(total=total, unit="s", desc=audio.name, leave=False) as barra:
            anterior = 0

            for seg in segmentos:
                texto = seg.text.strip()

                # Rede de segurança: detecta loop de repetição mesmo que os
                # parâmetros de decodificação não tenham evitado 100% dos casos.
                if texto and linhas and texto == linhas[-1]:
                    repeticoes_seguidas += 1
                else:
                    repeticoes_seguidas = 0

                linhas.append(texto)

                if repeticoes_seguidas == LIMITE_AVISO_REPETICAO and not aviso_disparado:
                    aviso_disparado = True
                    tqdm.write(
                        f"  [aviso] possível loop de repetição em {audio.name} "
                        f"perto de {seg.end:.0f}s: \"{texto[:60]}\""
                    )

                # Protege a barra contra timestamps que não avançam.
                atual = min(total, round(seg.end))
                if atual > anterior:
                    barra.update(atual - anterior)
                    anterior = atual

            if anterior < total:
                barra.update(total - anterior)

        destino.write_text("\n".join(linhas), encoding="utf-8")

        aviso = " (com aviso de repetição, vale revisar o .txt)" if aviso_disparado else ""
        print(f"✓ Transcrição concluída em {time.time() - inicio:.1f}s{aviso}")

        return destino

    except Exception as e:
        print("✗ Erro na transcrição:")
        print(e)
        print()

        return None


def transcrever_pasta(pasta=".", saida=None):
    """Transcreve todos os áudios de uma pasta, pulando os já transcritos."""
    pasta = Path(pasta)
    saida = Path(saida) if saida else pasta / "results" / "transcription"

    arquivos = [
        f for f in pasta.iterdir()
        if f.is_file() and f.suffix.lower() in AUDIO_EXT
    ]

    if not arquivos:
        print("Nenhum áudio encontrado em", pasta.resolve())
        return

    print(f"Foram encontrados {len(arquivos)} arquivo(s).\n")
    saida.mkdir(parents=True, exist_ok=True)

    inicio = time.time()
    ok = 0
    pulados = 0

    for audio in arquivos:
        destino = saida / (audio.stem + ".txt")

        if destino.exists():
            print(f"[pulado] {audio.name} (já transcrito)")
            pulados += 1
            continue

        if transcrever(audio, destino) is not None:
            ok += 1

    print()
    print("=" * 60)
    print("Finalizado")
    print(f"Transcritos agora : {ok}")
    print(f"Já existentes     : {pulados}")
    print(f"Dispositivo       : {dispositivo()}")
    print(f"Saída             : {saida.resolve()}")
    print(f"Tempo total       : {time.time() - inicio:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    transcrever_pasta(sys.argv[1] if len(sys.argv) > 1 else ".")
    input("\nPressione ENTER para sair...")
