# TODO

## Feito na 2.0

- [x] Escolha entre áudios separados ou um único MP3.
- [x] Concatenação via FFmpeg na ordem dos links, com nome configurável e proteção contra sobrescrita.
- [x] Transcrição opcional do arquivo único (Faster-Whisper `large-v3`).
- [x] Módulo `transcricao.py` reaproveitável, também executável sozinho.
- [x] Dependências instaladas sob demanda, incluindo as bibliotecas CUDA.

## Próximos passos

- [ ] Oferecer transcrição também no modo de arquivos separados.
- [ ] Permitir escolher o tamanho do modelo (`small`/`medium`/`large-v3`) para quem roda em CPU.
- [ ] Permitir escolher o idioma da transcrição em vez de fixar `pt`.
- [ ] Exportar também com timestamps (`.srt` / `.vtt`).
- [ ] Barra de progresso durante o download de cada áudio.
- [ ] Retentar automaticamente os links que falharem e listar os que ficaram de fora ao final.
- [ ] Aceitar links a partir de um arquivo de texto, além da entrada manual.
- [ ] Aceitar pastas do Google Drive, não apenas arquivos individuais.
- [ ] Testes automatizados do fluxo (download stubado + concatenação + transcrição).
- [ ] Empacotar como executável para uso sem Python instalado.

## Em aberto

- Ao juntar, o áudio é sempre re-codificado em 192 kbps. Copiar o stream quando todos os arquivos já forem MP3 compatíveis seria mais rápido e sem perda.
- O aviso de repetição do Whisper é apenas informativo: não refaz o trecho problemático.
