#!/usr/bin/env python3
"""
Gerenciador experimental de vídeos para Turing Smart Screen Rev. C.

Testado para trabalhar com a implementação local de:
    library/lcd/lcd_comm_rev_c.py

Comandos:
    self-test
    list
    size REMOTE
    upload LOCAL [--remote REMOTE] [--internal] [--overwrite] [--play]
    delete REMOTE
    play REMOTE
    stop
    probe LOCAL

IMPORTANTE:
- Pare o main.py antes de executar este script.
- O upload escreve no armazenamento interno/SD da tela.
- Comece com `self-test`, que envia apenas um arquivo temporário de 4 KiB.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from library.lcd.lcd_comm_rev_c import Command, LcdCommRevC


DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 480
DEFAULT_SD_VIDEO_DIR = "/mnt/SDCARD/video/"
DEFAULT_INTERNAL_VIDEO_DIR = "/root/video/"
PACKET_DATA_SIZE = 249


def human_size(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB")
    number = float(value)
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:.1f} {unit}"
        number /= 1024
    return f"{value} B"


def main_program_running() -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-f", r"python(3)? .*main\.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def validate_remote_path(remote_path: str, allow_directory: bool = False) -> bytes:
    if not remote_path.startswith(("/",)):
        raise ValueError("O caminho remoto precisa ser absoluto.")

    if not (
        remote_path.startswith(DEFAULT_SD_VIDEO_DIR)
        or remote_path.startswith(DEFAULT_INTERNAL_VIDEO_DIR)
    ):
        raise ValueError(
            "Por segurança, o destino deve ficar em "
            f"{DEFAULT_SD_VIDEO_DIR} ou {DEFAULT_INTERNAL_VIDEO_DIR}"
        )

    if remote_path.endswith("/") and not allow_directory:
        raise ValueError("O caminho remoto deve incluir o nome do arquivo.")

    try:
        encoded = remote_path.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "Use somente caracteres ASCII no nome remoto."
        ) from exc

    if len(encoded) > 255:
        raise ValueError("O caminho remoto não pode passar de 255 bytes.")

    return encoded


def make_path_command(
    opcode: int,
    remote_path: str,
    allow_directory: bool = False,
) -> bytearray:
    path_bytes = validate_remote_path(
        remote_path,
        allow_directory=allow_directory,
    )

    command = bytearray((opcode, 0xEF, 0x69, 0x00))
    command += len(path_bytes).to_bytes(3, "big")
    command += b"\x00\x00\x00"
    command += path_bytes
    return command


def clean_reply(reply: bytes) -> str:
    return reply.rstrip(b"\x00").decode("ascii", errors="replace").strip()


class VideoManager:
    def __init__(self, com_port: str = "AUTO"):
        self.lcd = LcdCommRevC(
            com_port=com_port,
            display_width=DISPLAY_WIDTH,
            display_height=DISPLAY_HEIGHT,
            update_queue=None,
        )
        self.lcd.InitializeComm()

    def close(self) -> None:
        try:
            self.lcd.closeSerial()
        except Exception:
            pass

    def flush_input(self) -> None:
        try:
            self.lcd.serial_flush_input()
        except Exception:
            pass

    def stop(self) -> None:
        self.lcd._send_command(
            Command.STOP_VIDEO,
            bypass_queue=True,
        )
        self.lcd._send_command(
            Command.STOP_MEDIA,
            bypass_queue=True,
        )

    def list_videos(self, internal: bool = False) -> tuple[list[str], list[str]]:
        directory = (
            DEFAULT_INTERNAL_VIDEO_DIR if internal else DEFAULT_SD_VIDEO_DIR
        )

        self.flush_input()
        self.lcd._send_command(
            Command.SEND_PAYLOAD,
            payload=make_path_command(
                0x65,
                directory,
                allow_directory=True,
            ),
            bypass_queue=True,
        )
        reply = clean_reply(self.lcd.ReadData(10240))

        directories: list[str] = []
        files: list[str] = []

        dir_match = re.search(r"dir:(.*?)file:", reply)
        if dir_match:
            directories = [item for item in dir_match.group(1).split("/") if item]

        file_match = re.search(r"file:(.*)", reply)
        if file_match:
            files = [item for item in file_match.group(1).split("/") if item]

        return directories, files

    def get_size(self, remote_path: str) -> int:
        self.flush_input()
        self.lcd._send_command(
            Command.SEND_PAYLOAD,
            payload=make_path_command(0x6E, remote_path),
            bypass_queue=True,
        )

        reply = clean_reply(self.lcd.ReadData(1024))
        match = re.search(r"\d+", reply)
        return int(match.group(0)) if match else 0

    def delete(self, remote_path: str) -> None:
        self.flush_input()
        self.lcd._send_command(
            Command.SEND_PAYLOAD,
            payload=make_path_command(0x66, remote_path),
            bypass_queue=True,
        )
        time.sleep(1.0)
        self.flush_input()

    def play(self, remote_path: str) -> None:
        size = self.get_size(remote_path)
        if size <= 0:
            raise FileNotFoundError(
                f"O arquivo remoto não foi encontrado: {remote_path}"
            )

        self.lcd._send_command(
            Command.SEND_PAYLOAD,
            payload=make_path_command(0x78, remote_path),
            bypass_queue=True,
            readsize=1024,
        )

    def upload(
        self,
        local_path: Path,
        remote_path: str,
        overwrite: bool = False,
        packet_delay: float = 0.0,
    ) -> None:
        local_path = local_path.expanduser().resolve()

        if not local_path.is_file():
            raise FileNotFoundError(f"Arquivo local não encontrado: {local_path}")

        remote_bytes = validate_remote_path(remote_path)
        file_size = local_path.stat().st_size

        if file_size <= 0:
            raise ValueError("O arquivo local está vazio.")

        if file_size > 0xFFFFFFFF:
            raise ValueError("Arquivos maiores que 4 GiB não são suportados.")

        existing_size = self.get_size(remote_path)
        if existing_size > 0:
            if not overwrite:
                raise FileExistsError(
                    f"Já existe um arquivo remoto com {human_size(existing_size)}. "
                    "Use --overwrite para substituí-lo."
                )
            print(f"Removendo arquivo existente: {remote_path}")
            self.delete(remote_path)

        # Para evitar disputa com a reprodução e com o worker de overlay.
        self.stop()
        time.sleep(0.5)
        self.flush_input()

        # Protocolo:
        # 6f ef 69 00
        # tamanho do caminho em 3 bytes (big endian)
        # 00 00 00
        # caminho ASCII
        # tamanho do arquivo em 4 bytes (little endian)
        upload_header = bytearray((0x6F, 0xEF, 0x69, 0x00))
        upload_header += len(remote_bytes).to_bytes(3, "big")
        upload_header += b"\x00\x00\x00"
        upload_header += remote_bytes
        upload_header += struct.pack("<I", file_size)

        self.lcd._send_command(
            Command.SEND_PAYLOAD,
            payload=upload_header,
            bypass_queue=True,
        )

        sent = 0
        started = time.monotonic()
        last_print = 0.0

        with local_path.open("rb") as source:
            while True:
                chunk = source.read(PACKET_DATA_SIZE)
                if not chunk:
                    break

                self.lcd._send_command(
                    Command.SEND_PAYLOAD,
                    payload=bytearray(chunk),
                    bypass_queue=True,
                )
                sent += len(chunk)

                now = time.monotonic()
                if now - last_print >= 0.25 or sent == file_size:
                    elapsed = max(now - started, 0.001)
                    percentage = sent * 100 / file_size
                    speed = sent / elapsed
                    print(
                        f"\rEnviando: {percentage:6.2f}% "
                        f"({human_size(sent)} / {human_size(file_size)}) "
                        f"— {human_size(int(speed))}/s",
                        end="",
                        flush=True,
                    )
                    last_print = now

                if packet_delay > 0:
                    time.sleep(packet_delay)

        print()

        # A tela precisa finalizar a gravação antes da consulta.
        time.sleep(2.0)
        self.flush_input()

        remote_size = 0
        for attempt in range(10):
            remote_size = self.get_size(remote_path)
            if remote_size == file_size:
                break
            time.sleep(1.0)

        if remote_size != file_size:
            raise RuntimeError(
                "A transmissão terminou, mas a verificação falhou: "
                f"local={file_size} bytes, remoto={remote_size} bytes."
            )

        elapsed = max(time.monotonic() - started, 0.001)
        print(
            f"Upload confirmado: {remote_path}\n"
            f"Tamanho: {human_size(remote_size)}\n"
            f"Tempo: {elapsed:.1f} s"
        )


def probe_video(path: Path) -> bool:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        print("ffprobe não está instalado; pulando a validação do vídeo.")
        return True

    command = [
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=codec_name,width,height,pix_fmt,r_frame_rate",
        "-of", "json",
        str(path),
    ]

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        print(result.stderr.strip() or "Não foi possível analisar o vídeo.")
        return False

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        print("Nenhum stream de vídeo foi encontrado.")
        return False

    stream = streams[0]
    codec = stream.get("codec_name")
    width = stream.get("width")
    height = stream.get("height")
    pixel_format = stream.get("pix_fmt")
    fps = stream.get("r_frame_rate")

    print("Informações do vídeo:")
    print(f"  Codec: {codec}")
    print(f"  Resolução: {width}x{height}")
    print(f"  Pixel format: {pixel_format}")
    print(f"  FPS: {fps}")

    compatible = True

    if codec != "h264":
        print("  AVISO: o codec recomendado é H.264.")
        compatible = False

    if (width, height) != (480, 480):
        print("  AVISO: a resolução recomendada é 480x480.")
        compatible = False

    if pixel_format not in ("yuv420p", "yuvj420p"):
        print("  AVISO: o pixel format recomendado é yuv420p.")
        compatible = False

    return compatible


def make_default_remote(local_path: Path, internal: bool) -> str:
    directory = (
        DEFAULT_INTERNAL_VIDEO_DIR if internal else DEFAULT_SD_VIDEO_DIR
    )
    return directory + local_path.name


def run_self_test(manager: VideoManager) -> None:
    remote_path = DEFAULT_SD_VIDEO_DIR + "chatgpt_upload_test.bin"

    with tempfile.NamedTemporaryFile(
        prefix="turing-upload-test-",
        suffix=".bin",
        delete=False,
    ) as temporary:
        temporary.write(os.urandom(4096))
        local_path = Path(temporary.name)

    try:
        print("Enviando arquivo de teste de 4 KiB...")
        manager.upload(
            local_path=local_path,
            remote_path=remote_path,
            overwrite=True,
        )

        remote_size = manager.get_size(remote_path)
        if remote_size != 4096:
            raise RuntimeError(
                f"Tamanho inesperado no teste: {remote_size} bytes."
            )

        print("Teste de upload aprovado.")
        print("Removendo arquivo temporário da tela...")
        manager.delete(remote_path)

        final_size = manager.get_size(remote_path)
        if final_size == 0:
            print("Teste de exclusão aprovado.")
        else:
            print(
                "AVISO: o upload funcionou, mas o arquivo de teste "
                "não foi removido automaticamente."
            )
    finally:
        local_path.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gerenciador experimental de vídeos da Turing Rev. C."
    )
    parser.add_argument(
        "--port",
        default="AUTO",
        help='Porta serial, por exemplo /dev/ttyACM0. Padrão: "AUTO".',
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Continuar mesmo que pareça haver um main.py em execução.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "self-test",
        help="Envia, verifica e remove um arquivo temporário de 4 KiB.",
    )

    list_parser = subparsers.add_parser(
        "list",
        help="Lista arquivos da pasta de vídeos.",
    )
    list_parser.add_argument("--internal", action="store_true")

    size_parser = subparsers.add_parser(
        "size",
        help="Consulta o tamanho de um arquivo remoto.",
    )
    size_parser.add_argument("remote")

    upload_parser = subparsers.add_parser(
        "upload",
        help="Envia um arquivo para a tela.",
    )
    upload_parser.add_argument("local", type=Path)
    upload_parser.add_argument("--remote")
    upload_parser.add_argument("--internal", action="store_true")
    upload_parser.add_argument("--overwrite", action="store_true")
    upload_parser.add_argument("--play", action="store_true")
    upload_parser.add_argument(
        "--packet-delay",
        type=float,
        default=0.0,
        help="Pausa opcional entre pacotes, em segundos.",
    )
    upload_parser.add_argument(
        "--skip-probe",
        action="store_true",
        help="Não validar codec e resolução com ffprobe.",
    )

    delete_parser = subparsers.add_parser(
        "delete",
        help="Exclui um arquivo remoto.",
    )
    delete_parser.add_argument("remote")

    play_parser = subparsers.add_parser(
        "play",
        help="Reproduz um vídeo já armazenado na tela.",
    )
    play_parser.add_argument("remote")

    subparsers.add_parser("stop", help="Para o vídeo atual.")

    probe_parser = subparsers.add_parser(
        "probe",
        help="Mostra codec, resolução e formato do vídeo.",
    )
    probe_parser.add_argument("local", type=Path)

    return parser


def cli() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "probe":
        return 0 if probe_video(args.local.expanduser().resolve()) else 2

    if main_program_running() and not args.force:
        print(
            "Parece que o main.py está em execução.\n"
            "Pare-o antes do upload para evitar dois processos usando "
            "/dev/ttyACM0 ao mesmo tempo.\n\n"
            'Exemplo: pkill -f "python3 main.py"',
            file=sys.stderr,
        )
        return 3

    manager: Optional[VideoManager] = None

    try:
        manager = VideoManager(com_port=args.port)

        if args.command == "self-test":
            run_self_test(manager)

        elif args.command == "list":
            directories, files = manager.list_videos(
                internal=args.internal
            )
            print("Pastas:", directories or "(nenhuma)")
            print("Arquivos:", files or "(nenhum)")

        elif args.command == "size":
            size = manager.get_size(args.remote)
            print(f"{size} bytes ({human_size(size)})")

        elif args.command == "upload":
            local_path = args.local.expanduser().resolve()
            remote_path = args.remote or make_default_remote(
                local_path,
                internal=args.internal,
            )

            if not args.skip_probe and local_path.suffix.lower() in (
                ".mp4", ".mov", ".mkv", ".avi", ".webm", ".h264"
            ):
                compatible = probe_video(local_path)
                if not compatible:
                    print(
                        "O vídeo não está no formato recomendado. "
                        "Use --skip-probe para enviar mesmo assim.",
                        file=sys.stderr,
                    )
                    return 2

            manager.upload(
                local_path=local_path,
                remote_path=remote_path,
                overwrite=args.overwrite,
                packet_delay=max(0.0, args.packet_delay),
            )

            if args.play:
                manager.play(remote_path)

        elif args.command == "delete":
            manager.delete(args.remote)
            print(f"Exclusão solicitada: {args.remote}")

        elif args.command == "play":
            manager.play(args.remote)
            print(f"Reproduzindo: {args.remote}")

        elif args.command == "stop":
            manager.stop()
            print("Vídeo interrompido.")

        return 0

    except KeyboardInterrupt:
        print("\nOperação interrompida.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    finally:
        if manager is not None:
            manager.close()


if __name__ == "__main__":
    raise SystemExit(cli())
