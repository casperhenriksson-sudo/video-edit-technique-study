"""Original procedural footage and original soundtrack; no stock/client media."""
from __future__ import annotations
import argparse
import functools
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

W, H, FPS, DURATION, RATE = 1280, 720, 24, 30, 48_000
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'
WHITE = (246, 247, 241)
CYAN = (120, 228, 218)
TITLES = ['A GOOD EDIT\nSTARTS HERE.', 'GIVE EVERY\nWORD ROOM.', 'LET THE\nBEAT LEAD.', 'MAKE THE\nCOLOR WORK.', 'MAKE THE\nCUT INTENTIONAL.', 'YOUR NEXT\nEDIT STARTS NOW.']
CAPTIONS = [
    ('One idea. Six shots. Thirty seconds.', 'Hook first. Explain second.'),
    ('Keep captions inside a consistent safe area.', 'Two short lines. Strong contrast. Space to breathe.'),
    ('120 BPM. One pulse every half second.', 'Transitions begin on the beat at 5, 10, 15, 20 and 25 seconds.'),
    ('The same source, before and after the grade.', 'Lift the warmth. Hold the shadows. Keep a consistent palette.'),
    ('Dissolve at 05.0 s. Directional wipe at 10.0 s.', 'Use a transition to connect ideas, not to cover a weak cut.'),
    ('Hook. Captions. Rhythm. Color. Transition.', 'Original procedural visuals and original synthesized audio.')
]

@functools.lru_cache(None)
def font(size: int, bold: bool = False):
    candidates = [Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / ('seguisb.ttf' if bold else 'segoeui.ttf'),
                  Path('/usr/share/fonts/truetype/dejavu') / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError('Install Segoe UI or DejaVu Sans, or adapt the font search list.')

def text(draw, xy, value, size, fill=WHITE, bold=False):
    draw.text(xy, value, font=font(size, bold), fill=fill, spacing=0, stroke_width=0)

def source_scene(shot: int, local: float):
    # All footage is drawn here: layered landscape, slow camera drift, moving sun.
    yy = np.linspace(0, 1, H)[:, None, None]
    top = np.array([20, 38, 59])[None, None, :]
    bottom = np.array([106, 132, 138])[None, None, :]
    gradient = np.broadcast_to(top * (1 - yy) + bottom * yy, (H, W, 3)).astype(np.uint8).copy()
    im = Image.fromarray(gradient)
    d = ImageDraw.Draw(im)
    drift = 18 * math.sin(local / 6 + shot * 0.7)
    sun_x = 905 + 30 * shot + drift
    sun_y = 230 + 8 * math.sin(local / 2)
    radius = 95 + shot * 3
    d.ellipse((sun_x-radius, sun_y-radius, sun_x+radius, sun_y+radius), fill=(221, 185, 137))
    for layer, color in enumerate([(56, 79, 94), (30, 60, 76), (17, 39, 55)]):
        base = 360 + layer * 100
        points = [(x, base + 55 * math.sin(x / (150 + layer * 45) + shot * .7 + drift / 100))
                  for x in range(-100, W + 150, 50)]
        d.polygon(points + [(W + 100, H), (-100, H)], fill=color)
    return im

def grade(im):
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.12)).enhance(1.05)
    lut = ([min(255, int(p * 1.05 + 6)) for p in range(256)] +
           [min(255, int(p * 1.01 + 2)) for p in range(256)] +
           [max(0, min(255, int(p * .91))) for p in range(256)])
    return im.point(lut)

def shot_background(shot: int, local: float):
    raw = source_scene(shot, local)
    im = grade(raw)
    if shot == 3:
        im.paste(raw.crop((0, 0, W//2, H)), (0, 0))
    return im

def caption_layer(shot: int, global_t: float):
    layer = Image.new('RGBA', (W, H))
    d = ImageDraw.Draw(layer)
    d.rectangle((0, 0, W, H), fill=(5, 12, 23, 36))
    # Soft dark field protects text while keeping the original footage visible.
    for x in range(950):
        d.line((x, 0, x, H), fill=(5, 12, 23, 36 + int(100 * (1 - x / 950))))
    text(d, (64, 42), 'CUT / COLOR / RHYTHM', 22, CYAN, True)
    text(d, (1040, 42), f'{min(29, int(global_t)):02d} / 30', 22)
    text(d, (64, 132), f'0{shot+1}  /  {['HOOK', 'CAPTIONS', 'RHYTHM', 'GRADE', 'TRANSITIONS', 'RECAP'][shot]}', 19, CYAN)
    for i, line in enumerate(TITLES[shot].split('\n')):
        text(d, (60, 184 + 101 * i), line, 84, bold=True)
    if shot == 3:
        d.line((W//2, 390, W//2, 505), fill=CYAN, width=2)
        text(d, (66, 438), 'SOURCE', 20, WHITE, True)
        text(d, (W//2+24, 438), 'WARM GRADE', 20, WHITE, True)
    if shot == 2:
        pulse = math.exp(-(global_t % .5) * 13)
        for bar in range(13):
            x = 790 + bar * 29
            height = 35 + (65 + 55 * math.sin(bar * .8)) * pulse
            d.rounded_rectangle((x, 470-height, x+16, 470), radius=5, fill=CYAN+(210,))
    d.rounded_rectangle((48, 528, 1232, 638), radius=16, fill=(6, 15, 27, 232))
    text(d, (70, 541), CAPTIONS[shot][0], 30, WHITE, True)
    text(d, (70, 585), CAPTIONS[shot][1], 25, WHITE)
    for beat in range(60):
        x = 68 + beat * 19.4
        active = beat == min(59, int(global_t * 2))
        r = 5 if active else 2
        d.ellipse((x-r, 668-r, x+r, 668+r), fill=CYAN+(255 if active else 75,))
    text(d, (64, 690), 'TECHNIQUE STUDY  |  AI-ASSISTED  |  ORIGINAL MEDIA', 13, (190, 204, 209, 255))
    return layer

def frame(t: float):
    shot = min(5, int(t // 5))
    local = t - shot * 5
    current = shot_background(shot, local)
    if shot and local < 1:
        previous = shot_background(shot-1, 5+local)
        progress = local * local * (3 - 2 * local)
        if shot % 2:
            current = Image.blend(previous, current, progress)
        else:
            edge = int(W * progress)
            previous.paste(current.crop((0, 0, edge, H)), (0, 0))
            ImageDraw.Draw(previous).line((edge, 0, edge, H), fill=CYAN, width=3)
            current = previous
    # Titles cut on the beat above the footage transition, so words never ghost.
    current = Image.alpha_composite(current.convert('RGBA'), caption_layer(shot, t)).convert('RGB')
    if t > 29.5:
        current = Image.blend(current, Image.new('RGB', (W, H), (5, 12, 23)), (t-29.5)/.5)
    return current

def soundtrack():
    count = RATE * DURATION
    t = np.arange(count) / RATE
    audio = np.zeros(count)
    # A soft original chord bed, with a kick on each 120-BPM beat.
    for freq in [130.8128, 155.5635, 195.9977]:
        audio += .023 * np.sin(2*np.pi*freq*t) * (1+.15*np.sin(2*np.pi*.1*t))
    for beat in range(60):
        start = int(beat * .5 * RATE)
        length = min(int(.24 * RATE), count-start)
        bt = np.arange(length)/RATE
        phase = 2*np.pi*(53*bt + 2.8*(1-np.exp(-bt*35)))
        audio[start:start+length] += .25*np.sin(phase)*np.exp(-bt*21)
        click = .025*np.sin(2*np.pi*2000*bt)*np.exp(-bt*120)
        audio[start:start+length] += click
    fade = np.minimum(1, t/.08)*np.minimum(1, (DURATION-t)/.5)
    audio *= fade
    stereo = np.column_stack([audio, audio*.97])
    assert np.max(np.abs(stereo)) < 1
    pcm = (stereo * 32767).astype('<i2')
    with wave.open(str(OUT/'original-soundtrack.wav'), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm.tobytes())
    return dict(sample_rate=RATE, channels=2, samples=count, peak=float(np.max(np.abs(stereo))),
                rms=float(np.sqrt(np.mean(stereo**2))), bpm=120, beats=60)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ffmpeg', default=shutil.which('ffmpeg'))
    args = parser.parse_args()
    if not args.ffmpeg:
        parser.error('Provide --ffmpeg /path/to/ffmpeg from your official package source.')
    OUT.mkdir(exist_ok=True)
    audio = soundtrack()
    times = [.5, 5.5, 7.5, 10.5, 12.5, 17.5, 22.5, 27.5]
    contact = Image.new('RGB', (W*2, H*4))
    for i, at in enumerate(times):
        still = frame(at); still.save(OUT/f'frame-{at:04.1f}.png')
        contact.paste(still, ((i%2)*W, (i//2)*H))
    contact.resize((1280, 1440)).save(OUT/'contact-sheet.jpg', quality=93)
    cmd = [args.ffmpeg, '-hide_banner', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{W}x{H}', '-r', str(FPS), '-i', 'pipe:0', '-i', str(OUT/'original-soundtrack.wav'),
           '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-af', 'volume=1.8',
           '-t', str(DURATION), '-movflags', '+faststart', str(OUT/'thirty-second-edit.mp4')]
    with (OUT/'encoding.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=log)
        try:
            for index in range(FPS*DURATION):
                process.stdin.write(frame(index/FPS).tobytes())
                if index % (FPS*5) == 0:
                    print(f'Rendered {index//FPS}/{DURATION} seconds', flush=True)
        finally:
            process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError('FFmpeg failed; inspect the local encoding log.')
    output = OUT/'thirty-second-edit.mp4'
    info = dict(duration=DURATION, fps=FPS, frames=FPS*DURATION, width=W, height=H,
                bytes=output.stat().st_size, sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                audio_source=audio, audio_output=dict(codec='aac', sample_rate=48000, channels=2, gain=1.8),
                transition_starts=[5,10,15,20,25],
                transition_types=['dissolve','directional wipe','dissolve','directional wipe','dissolve'],
                transition_duration=1, original_procedural_media=True, ai_assisted=True)
    (OUT/'render-metadata.json').write_text(json.dumps(info, indent=2)+'\n')
    print(json.dumps(info), flush=True)

if __name__ == '__main__':
    main()
