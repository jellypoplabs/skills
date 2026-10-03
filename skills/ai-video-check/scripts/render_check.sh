#!/bin/bash
# Check a rendered video file: duration, audio, loudness, black frames, frozen frames, silence, contact sheet.
# Usage: bash render_check.sh <video.mp4> [expected_seconds]
set -uo pipefail

V="${1:?usage: render_check.sh <video.mp4> [expected_seconds]}"
EXPECT="${2:-}"
[ -f "$V" ] || { echo "FAIL  file not found: $V"; exit 2; }
command -v ffmpeg >/dev/null || { echo "FAIL  ffmpeg is not installed. On a Mac: install Homebrew from https://brew.sh, then run: brew install ffmpeg"; exit 2; }

problems=0
warn() { echo "WARN  $*"; problems=$((problems + 1)); }

dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$V")
size=$(wc -c <"$V" | tr -d ' ')
res=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$V")
has_audio=$(ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 "$V" | head -1)
printf "INFO  duration %.2f s, video %s, size %s bytes\n" "$dur" "$res" "$size"

if [ -n "$EXPECT" ]; then
  awk -v d="$dur" -v e="$EXPECT" 'BEGIN{x=d-e; if (x<0) x=-x; exit !(x>0.5)}' && warn "duration $dur s differs from expected $EXPECT s"
fi
mb_per_10s=$(awk -v s="$size" -v d="$dur" 'BEGIN{printf "%.2f", s/1048576/(d/10)}')
awk -v m="$mb_per_10s" 'BEGIN{exit !(m<0.4)}' && warn "file is very small (${mb_per_10s} MB per 10 s): often a blank render"

if [ -z "$has_audio" ]; then
  warn "no audio stream"
else
  lufs=$(ffmpeg -nostats -i "$V" -af ebur128 -f null - 2>&1 | awk '/Integrated loudness/{f=1} f&&/I:/{print $2; exit}')
  echo "INFO  integrated loudness ${lufs} LUFS (short video platforms: about -14)"
  silences=$(ffmpeg -nostats -i "$V" -af silencedetect=noise=-50dB:d=2 -f null - 2>&1 | grep -oE "silence_(start|end): [0-9.]*" | paste - -)
  [ -n "$silences" ] && while read -r s; do warn "silence >2 s: $s"; done <<<"$silences"
fi

blacks=$(ffmpeg -nostats -i "$V" -vf blackdetect=d=0.5:pix_th=0.10 -an -f null - 2>&1 | grep -o "black_start:[0-9.]* black_end:[0-9.]*")
[ -n "$blacks" ] && while read -r b; do warn "black section $b"; done <<<"$blacks"
freezes=$(ffmpeg -nostats -i "$V" -vf freezedetect=n=0.001:d=2 -an -f null - 2>&1 | grep -oE "freeze_(start|end): [0-9.]*" | paste - - )
[ -n "$freezes" ] && while read -r f; do warn "frozen picture $f"; done <<<"$freezes"

# Frozen picture plus silence at the very end reads as a stuck video
tail_freeze=$(awk -v f="$freezes" -v d="$dur" 'BEGIN{n=split(f,a,/[ \t]+/); s=""; for(i=1;i<=n;i++) if(a[i]=="freeze_start:") s=a[i+1]; if(s!="" && d-s>3) printf "%.1f", d-s}')
[ -n "$tail_freeze" ] && warn "the last ${tail_freeze} s do not move; viewers may think the video is stuck (keep a still ending under about 3 s)"

sheet="${V%.*}_sheet.jpg"
touch "$sheet" 2>/dev/null || sheet="${TMPDIR:-/tmp}/$(basename "${V%.*}")_sheet.jpg"
n=16
step=$(awk -v d="$dur" -v n="$n" 'BEGIN{printf "%.3f", d/n}')
ffmpeg -v error -y -i "$V" -vf "fps=1/$step,scale=480:-1,drawtext=text='%{pts\:hms}':x=8:y=8:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.6,tile=4x4" -frames:v 1 "$sheet" 2>/dev/null \
  || { ffmpeg -v error -y -i "$V" -vf "fps=1/$step,scale=480:-1,tile=4x4" -frames:v 1 "$sheet"; echo "NOTE  this ffmpeg cannot draw text, so the sheet has no timestamps; frame k is at about (k-1) x ${step} s"; }
echo "INFO  contact sheet: $sheet (16 frames, look at every one)"

if [ "$problems" -eq 0 ]; then echo "OK    no machine problems found. Now look at the frames yourself."; else echo "DONE  $problems warning(s). Fix or explain each one before delivering."; fi
exit $([ "$problems" -eq 0 ] && echo 0 || echo 1)
