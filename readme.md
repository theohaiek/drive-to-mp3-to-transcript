# drive-to-mp3-to-transcript

Pipeline em Python para baixar áudios do Google Drive, convertê-los em MP3 e — opcionalmente — transcrevê-los para texto, tudo pelo terminal.

**Versão 2.0** — junta o downloader de áudio e o transcritor local (Whisper) em um único projeto.

## Fluxo

```text
links do Drive  ->  MP3  ->  [opcional] arquivo único  ->  [opcional] transcrição .txt
```

## Funcionalidades

- Pergunta no início se os áudios devem ficar separados ou unidos em um único MP3.
- No modo único, oferece a transcrição automática do áudio final.
- Recebe múltiplos links do Google Drive via terminal.
- Finaliza a entrada quando uma linha vazia é enviada.
- Baixa apenas o áudio de cada arquivo.
- Converte automaticamente para MP3.
- Salva os arquivos na mesma pasta onde o script é executado.
- Transcrição local com Faster-Whisper `large-v3`, usando GPU NVIDIA quando disponível e caindo para CPU automaticamente.
- Instala sozinho todas as dependências (`yt-dlp`, `imageio-ffmpeg`, `faster-whisper`, `tqdm`, `huggingface_hub` e as bibliotecas CUDA) conforme forem necessárias.

## Requisitos

- Python 3.9 ou superior.
- Conexão com a internet.
- Opcional: GPU NVIDIA com driver atualizado, para transcrever muito mais rápido.

Nenhuma instalação manual de bibliotecas é necessária. O modelo de transcrição (~3 GB) só é baixado se a transcrição for escolhida.

## Como usar

```bash
python main.py
```

Escolha como salvar:

```text
  [1] Separados  - um MP3 por link
  [2] Único      - todos juntos em um só MP3
```

Na opção **2** é possível informar o nome do arquivo final (ENTER usa `audio_completo`) e decidir se ele deve ser transcrito.

Cole um link por linha:

```text
https://drive.google.com/file/d/XXXXXXXX/view
https://drive.google.com/file/d/YYYYYYYY/view
```

Quando terminar, pressione **Enter** em uma linha vazia para iniciar os downloads.

## Saída

Os arquivos MP3 são salvos na mesma pasta do script.

No modo único, os áudios são baixados em uma pasta temporária, unidos na ordem em que os links foram colados e salvos como um só MP3. Se já existir um arquivo com o mesmo nome, um sufixo numérico é adicionado. Quando a transcrição é escolhida, o `.txt` é gravado ao lado do MP3, com o mesmo nome.

## Transcrever arquivos já existentes

O módulo de transcrição também funciona sozinho, sem passar pelo download:

```bash
python transcricao.py            # transcreve os áudios da pasta atual
python transcricao.py "C:\pasta" # transcreve os áudios de outra pasta
```

Nesse modo, os textos vão para `results/transcription/` e arquivos já transcritos são pulados.

Formatos aceitos: `mp3`, `wav`, `m4a`, `aac`, `ogg`, `opus`, `flac`, `wma`, `mp4`, `mov`, `mkv`.

## Notas técnicas da transcrição

- A GPU é detectada por `nvidia-smi`, e não por `torch.cuda.is_available()`: no Windows, o `pip install torch` instala o PyTorch sem CUDA e a checagem sempre falharia. O PyTorch, aliás, não é usado — o Faster-Whisper não precisa dele.
- O CTranslate2 depende das bibliotecas cuBLAS e cuDNN 9. Elas são instaladas e registradas no `PATH` automaticamente; sem isso a GPU nunca é usada, mesmo com driver correto.
- Se a GPU falhar ao carregar o modelo, o script volta para CPU e mostra o erro.
- Contra o loop de repetição do Whisper (a transcrição repetindo a mesma frase até o fim): o fallback de temperatura fica ativo (`temperature` é uma tupla, não um valor fixo) e há a trava `no_repeat_ngram_size`. Como rede extra, um aviso aparece no console quando linhas idênticas se repetem em sequência.
- A barra de progresso é resistente a timestamps que não avançam, para não parecer travada.

## Observações

- Os arquivos do Google Drive precisam estar compartilhados com permissão de acesso.
- O nome do MP3 será baseado no nome original do arquivo, exceto no modo único.
- O download é realizado com `yt-dlp` e a conversão para MP3 pelo FFmpeg.
- O idioma da transcrição é português (`LANGUAGE` em `transcricao.py`).
