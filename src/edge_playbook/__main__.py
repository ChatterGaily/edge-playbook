"""Main entrypoint for the edge-playback package."""

import threading
import argparse
import os
import subprocess
import sys
import tempfile
from shutil import which

from .util import pr_err

use_mpv = False

class play_mp3 (threading.Thread):
    def __init__(self, mp3_fname1, srt_fname1, mp3_fname2, srt_fname2):
        threading.Thread.__init__(self)
        self.mp3_fname1 = mp3_fname1
        self.srt_fname1 = srt_fname1
        self.mp3_fname2 = mp3_fname2
        self.srt_fname2 = srt_fname2
        self.buffer1 = ""
        self.buffer2 = ""
        self.need_stop_play = False
    def run(self):
        switcher_of_2play = 0
        while not (self.need_stop_play and self.buffer1 == "" and self.buffer2 == "") :
            if switcher_of_2play == 0:
                buffer1Lock.acquire()
                print('\033[32m' + self.buffer1, end="")
                if sys.platform == "win32" and not use_mpv:
                    # pylint: disable-next=import-outside-toplevel
                    from .win32_playback import play_mp3_win32
                    play_mp3_win32(self.mp3_fname1)
                else:
                    with subprocess.Popen(
                        [
                            "mpv",
                            f"--really-quiet",
                            f"--sub-file={self.srt_fname1}",
                            self.mp3_fname1,
                        ]
                    ) as process:
                        process.communicate()  
                buffer1_wait_Lock.acquire()
                self.buffer1 = ""
                buffer1Lock.release()
                switcher_of_2play = 1
            else:
                buffer2Lock.acquire()
                buffer1_wait_Lock.release()
                print('\033[34m' + self.buffer2, end="")
                if sys.platform == "win32" and not use_mpv:
                    # pylint: disable-next=import-outside-toplevel
                    # from .win32_playback import play_mp3_win32
                    play_mp3_win32(self.mp3_fname2)
                else:
                    with subprocess.Popen(
                        [
                            "mpv",
                            f"--really-quiet",
                            f"--sub-file={self.srt_fname2}",
                            self.mp3_fname2,
                        ]
                    ) as process:
                        process.communicate()  
                self.buffer2 = ""
                buffer2Lock.release()
                switcher_of_2play = 0
    def set_buffer1(self, buffer1):
        self.buffer1 = buffer1
    def set_buffer2(self, buffer2):
        self.buffer2 = buffer2       
    def set_stop_play(self):
        self.need_stop_play = True 

buffer1Lock = threading.Lock()
buffer2Lock = threading.Lock()
buffer1_wait_Lock = threading.Lock()

def _main() -> None:
    depcheck_failed = False

    parser = argparse.ArgumentParser(
        prog="edge-playback",
        description="Speak text using Microsoft Edge's online text-to-speech API",
        epilog="See `edge-tts` for additional arguments",
    )
    parser.add_argument(
        "--mpv",
        action="store_true",
        help="Use mpv to play audio. By default, false on Windows and true on all other platforms",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=str,
        default="",
        help="same as edge-tts --text but read from file",
    )    
    parser.add_argument(
        "--line",
        type=str,
        default="1",
        help="from the line number start play",
    )       
    args, tts_args = parser.parse_known_args()

    use_mpv = sys.platform != "win32" or args.mpv

    deps = ["edge-tts"]
    if use_mpv:
        deps.append("mpv")

    for dep in deps:
        if not which(dep):
            pr_err(f"{dep} is not installed.")
            depcheck_failed = True

    if depcheck_failed:
        pr_err("Please install the missing dependencies.")
        sys.exit(1)

    keep = os.environ.get("EDGE_PLAYBACK_KEEP_TEMP") is not None
    mp3_fname = os.environ.get("EDGE_PLAYBACK_MP3_FILE")
    srt_fname = os.environ.get("EDGE_PLAYBACK_SRT_FILE")
    media, subtitle = None, None
    try:
        if not mp3_fname:
            media = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            media.close()
            mp3_fname = media.name

        if not srt_fname and use_mpv:
            subtitle = tempfile.NamedTemporaryFile(suffix=".srt", delete=False)
            subtitle.close()
            srt_fname = subtitle.name

        # print(f"Media file: {mp3_fname}")
        # if srt_fname:
        #    print(f"Subtitle file: {srt_fname}\n")

        edge_tts_cmd = ["edge-tts", f"--write-media={mp3_fname}"]
        if srt_fname:
            edge_tts_cmd.append(f"--write-subtitles={srt_fname}")
        edge_tts_cmd = edge_tts_cmd + tts_args

        if args.file != "":
            if sys.platform == "win32" and not use_mpv:
                # pylint: disable-next=import-outside-toplevel
                from .win32_playback import play_mp3_win32
            mp3_fname1 = mp3_fname
            srt_fname1 = srt_fname

            media2 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            media2.close()
            mp3_fname2 = media2.name
            subtitle2 = tempfile.NamedTemporaryFile(suffix=".srt", delete=False)
            subtitle2.close()
            srt_fname2 = subtitle2.name    
            mp3_player = play_mp3(mp3_fname1, srt_fname1, mp3_fname2, srt_fname2)
            mp3_player_need_init = True

            switcher_of_2play = True
            line_buffer1 = ""
            line_buffer2 = ""

            start_line = 1
            if int(args.line) > 1:
                start_line = int(args.line)
            line_counter = 1

            with open(args.file, "r", encoding="utf-8") as file:
                for line in file:
                    line_counter = line_counter + 1
                    if line_counter >= start_line:
                        if switcher_of_2play:
                            line_buffer1 += line
                            if len(line_buffer1) > 200:
                                edge_tts_cmd1 = ["edge-tts"]
                                edge_tts_cmd1 = edge_tts_cmd1 + tts_args
                                edge_tts_cmd1.append(f"--write-media={mp3_fname1}")
                                if srt_fname:
                                    edge_tts_cmd1.append(f"--write-subtitles={srt_fname1}")
                                edge_tts_cmd1.append(f"--text={line_buffer1}")
                                buffer1Lock.acquire()
                                with subprocess.Popen(edge_tts_cmd1) as process:
                                    process.communicate()
                                # print(line_buffer1)
                                mp3_player.set_buffer1(line_buffer1)
                                buffer1Lock.release()
                                line_buffer1 = ""    
                                switcher_of_2play = False
                                if mp3_player_need_init:
                                    mp3_player.start()
                                    mp3_player_need_init = False
                                buffer1_wait_Lock.acquire()
                                buffer1_wait_Lock.release()
           
                        else:
                            line_buffer2 += line
                            if len(line_buffer2) > 200:
                                edge_tts_cmd2 = ["edge-tts"]
                                edge_tts_cmd2 = edge_tts_cmd2 + tts_args
                                edge_tts_cmd2.append(f"--write-media={mp3_fname2}")
                                if srt_fname:
                                    edge_tts_cmd2.append(f"--write-subtitles={srt_fname2}")
                                edge_tts_cmd2.append(f"--text={line_buffer2}")
                                buffer2Lock.acquire()
                                with subprocess.Popen(edge_tts_cmd2) as process:
                                    process.communicate()
                                # print(line_buffer2)
                                mp3_player.set_buffer2(line_buffer2)
                                buffer2Lock.release()
                                line_echo = ""
                                line_buffer2 = ""          
                                switcher_of_2play = True   
            if line_counter >= start_line:
                mp3_player.set_stop_play()
                mp3_player.join()    

        else:
            with subprocess.Popen(edge_tts_cmd) as process:
                process.communicate()

            if sys.platform == "win32" and not use_mpv:
                # pylint: disable-next=import-outside-toplevel
                from .win32_playback import play_mp3_win32

                play_mp3_win32(mp3_fname)
            else:
                with subprocess.Popen(
                    [
                        "mpv",
                        f"--sub-file={srt_fname}",
                        mp3_fname,
                    ]
                ) as process:
                    process.communicate()
    finally:
        if keep:
            print(f"\nKeeping temporary files: {mp3_fname} and {srt_fname}")
        else:
            if mp3_fname is not None and os.path.exists(mp3_fname):
                os.unlink(mp3_fname)
            if srt_fname is not None and os.path.exists(srt_fname):
                os.unlink(srt_fname)


if __name__ == "__main__":
    _main()
