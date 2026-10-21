"""Verify the rendered media, timing, audio pulses and caption safe area."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import numpy as np
from PIL import ImageDraw, Image
from render import CAPTIONS, TITLES, font, source_scene, grade

p = argparse.ArgumentParser()
p.add_argument('video', type=Path)
p.add_argument('--ffmpeg', required=True)
a = p.parse_args()
probe = subprocess.run([a.ffmpeg, '-hide_banner', '-i', str(a.video)], capture_output=True, text=True).stderr
assert re.search(r'Duration: 00:00:30\.00', probe), probe
assert re.search(r'Video: h264.*1280x720.*24 fps', probe), probe
assert re.search(r'Audio: aac.*48000 Hz, stereo', probe), probe
decoded = subprocess.run([a.ffmpeg, '-v', 'error', '-nostats', '-progress', 'pipe:1', '-i', str(a.video),
                          '-map', '0:v:0', '-an', '-f', 'null', '-'], capture_output=True, text=True, check=True)
assert not decoded.stderr.strip(), decoded.stderr
frames = int(re.findall(r'^frame=(\d+)', decoded.stdout, re.M)[-1])
assert frames == 720, frames
sound = subprocess.run([a.ffmpeg, '-v', 'error', '-i', str(a.video), '-map', '0:a:0', '-ac', '1', '-ar', '48000',
                        '-f', 'f32le', 'pipe:1'], capture_output=True, check=True)
assert not sound.stderr.strip(), sound.stderr
samples = np.frombuffer(sound.stdout, dtype='<f4')
assert abs(len(samples)/48000 - 30) < .03
assert np.max(np.abs(samples)) < .999, 'Clipped decoded audio'
offsets = []
for beat in range(1, 60):
    window = np.abs(samples[int(beat*.5*48000):int((beat*.5+.12)*48000)])
    offset = int(np.argmax(window))/48000
    assert offset < .06, f'Audio accent too far after beat {beat}: {offset}'
    offsets.append(offset)
draw = ImageDraw.Draw(Image.new('RGB', (1280, 720)))
widths = []
for title in TITLES:
    for line in title.split('\n'):
        width = draw.textlength(line, font=font(84, True)); widths.append(width)
        assert width <= 1152, (line, width)
for pair in CAPTIONS:
    for i, line in enumerate(pair):
        width = draw.textlength(line, font=font(30 if i == 0 else 25, i == 0)); widths.append(width)
        assert width <= 1140, (line, width)
raw = np.array(source_scene(3, 2.5)).astype(float)
graded = np.array(grade(source_scene(3, 2.5))).astype(float)
assert np.mean(np.abs(raw-graded)) > 1, 'Grade must materially change the image'
result = dict(video=a.video.name, bytes=a.video.stat().st_size,
              sha256=hashlib.sha256(a.video.read_bytes()).hexdigest(), video_duration_seconds=30,
              frames_decoded=frames, dimensions=[1280,720], fps=24, video_codec='h264', audio_codec='aac',
              audio_sample_rate=48000, audio_channels=2, audio_decoded_seconds=len(samples)/48000,
              decoded_audio_peak=float(np.max(np.abs(samples))), checked_audio_accents=59,
              maximum_accent_offset_seconds=max(offsets), largest_text_width_pixels=max(widths),
              caption_safe_area_passed=True, full_video_audio_decode_passed=True, original_media=True,
              ai_assisted=True)
(a.video.parent/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
