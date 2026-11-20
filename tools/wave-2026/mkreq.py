"""產生 YuE2 候選請求：lyrics_zh-cn.txt × 風格 × seed → _jobs/song_<tag>.json"""
import json, pathlib, sys
R = pathlib.Path(__file__).resolve().parent.parent
LY = (R / '20_audio' / 'lyrics_zh-cn.txt').read_text(encoding='utf-8').strip()
STY = {
    'rock': 'Mandarin, anime opening, J-pop rock, energetic, driving electric guitar, punchy drums, synth bass, bright powerful female vocal, catchy chorus, 140 BPM',
    'edm': 'Mandarin, electronic pop, EDM, future bass, punchy kick, sidechain synths, big synth drop, bright female vocal, energetic, 128 BPM',
    'epic': 'Mandarin, cinematic pop rock, epic, orchestral strings, big drums, distorted guitar, powerful emotional female vocal, anthemic chorus, 132 BPM',
    'synth': 'Mandarin, synthwave, retro 80s, pulsing synth bass, gated drums, airy female vocal, driving, 120 BPM',
}
out = []
for tag in sys.argv[1].split(','):
    st, seed = tag.split(':')
    j = {'style': STY[st], 'lyrics': LY, 'duration': 270.0, 'lm_seed': int(seed), 'seed': int(seed), 'output_format': 'mp3'}
    p = R / '_jobs' / f'song_{st}_{seed}.json'
    p.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding='utf-8')
    out.append(str(p))
print('\n'.join(out))
