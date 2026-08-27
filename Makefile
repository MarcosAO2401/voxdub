# VoxDub — atajos de un comando.
#   make            -> levanta la app (binario si existe, si no: venv + serve)
#   make run       -> igual que make
#   make bin       -> (re)construye el binario autónomo
#   make desktop   -> app de escritorio Tauri (requiere Rust + webkit)
#   make models    -> descarga modelos reales (Wav2Lip, Piper, torch)

run:
	./run.sh

bin:
	python scripts/build_backend.py

desktop:
	./run_tauri.sh

models:
	python scripts/setup_models.py

.PHONY: run bin desktop models
