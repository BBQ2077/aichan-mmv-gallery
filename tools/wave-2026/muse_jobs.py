"""Muse 圖單。用法：python _tools/muse_jobs.py <批號 1..>  → _jobs/muse_b<N>.json（每批 5 張）"""
import json, sys, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
KEEP = ("Keep this exact character from the reference images: same face and blue eyes, long wavy navy-blue hair with light-blue gradient tips, "
        "dark whale-fin ears, ahoge, white frilly maid headdress with small blue bows, navy and white maid dress with white apron and a small whale embroidery, "
        "black ribbon bow with blue gem, small navy whale tail. Same clean modern anime illustration style, soft cel shading, high detail. ")
REFS = ['10_img/ref_front.png', '10_img/ref_face.png']
J = [
    # 批 1：驗證一致性（場景、特寫、去背、無人）
    ('desk_night', '16:9', "She sits at a trading desk at night surrounded by six glowing monitors showing red and green candlestick charts, dark room lit only by the screens, blue and red light on her face, focused serious expression, one hand on the mouse, three-quarter view."),
    ('dive', '16:9', "She dives head-first down into the deep blue ocean, streams of bubbles rising around her, god rays from the bright surface above, her long hair and dress flowing upward, calm determined eyes, whale tail visible."),
    ('crest', '16:9', "She stands on the very crest of a gigantic ocean wave at golden sunset, the curling edge of the wave glowing bright red like a rising chart line, arms spread out for balance, wind in her hair, exhilarated smile, low angle, epic scale."),
    ('gold', '2:3', "Plain pure white background, no other objects. Full body. She hugs a large shiny gold bullion bar to her chest with both arms, sparkles around it, delighted happy face, slight head tilt."),
    ('jacket', '16:9', "No people in the image. A dark empty stage lit by a single cold spotlight from above; a black leather jacket is draped over the back of a lone chair in the center; a big dark screen behind the stage; smoke on the floor; melancholic, dramatic, cinematic."),
    # 批 2
    ('hormuz', '16:9', "Night at sea. She stands at the railing of a ship deck, seen from behind at three-quarter view, looking at a distant oil tanker burning on the horizon, orange fire and black smoke reflected on dark water, wind blowing her hair, worried face in profile."),
    ('bubble', '16:9', "She gently blows a huge iridescent soap bubble, dozens of soap bubbles floating around her reflecting neon city lights at night, dreamy bokeh, soft smile, half-closed eyes, waist-up."),
    ('crash', '16:9', "She stands in front of a wall of giant screens all glowing green with sharp downward arrows and falling chart lines, green light on her face, shocked expression with wide eyes and both hands on her cheeks, dramatic lighting, waist-up."),
    ('cheer', '2:3', "Plain pure white background. Full body. She jumps in the air cheering with both fists raised high, huge joyful open-mouth smile, red confetti flying around her, dress and hair bouncing."),
    ('bell', '16:9', "Inside a stock exchange hall with big digital screens and confetti falling, she stands at the podium and rings a large brass opening bell with a hammer, excited smile, crowd of silhouettes clapping behind her."),
    # 批 3
    ('seoul', '16:9', "Night street in Seoul with bright Korean neon signs; she holds up a smartphone showing a soaring red stock chart app, excited sparkling eyes, open smile, crowd of people around also looking at phones, waist-up."),
    ('tokyo', '16:9', "Rooftop in Tokyo at night, she leans on the railing with a giant electronic stock ticker board glowing on the building behind her, city lights bokeh, confident smirk, wind in hair."),
    ('wafer', '16:9', "In a blue-lit semiconductor cleanroom, she holds up a shining silicon wafer with both hands, rainbow light reflections on the wafer and her face, amazed expression, waist-up, close shot."),
    ('storm', '16:9', "Stormy ocean at night with lightning splitting the sky, heavy rain, she stands on a rock above crashing waves, hair and dress whipped by wind, determined serious expression, dramatic low angle."),
    ('breach', '16:9', "She bursts up out of the ocean surface like a breaching whale, huge white splash and water droplets frozen in the air, bright sunlight, joyful, dynamic upward motion, low angle from the water."),
    # 批 4
    ('dawn', '16:9', "Calm sea at dawn with soft pink and gold sky, she sits on the back of a huge dark-blue whale floating on the still water, hugging her knees, peaceful gentle smile, looking at the horizon, wide shot, serene."),
    ('nyc', '16:9', "Seen from behind, she stands in Times Square at night looking up at enormous digital billboards full of stock tickers and charts, cold blue and red lights, small figure, wide shot."),
    ('phone_hand', '16:9', "Extreme close-up of her hand holding a smartphone showing a red and green candlestick chart, her blue hair and maid sleeve cuff visible, shallow depth of field, glowing screen light, night."),
    ('eyes', '16:9', "Extreme close-up of her blue eyes filling the frame, red and green stock chart lines reflected in her irises, intense focused gaze, dark background."),
    ('btc', '2:3', "Plain pure white background, no other objects. Full body. She holds a giant golden bitcoin coin in front of her like a shield, nervous sweat drop, uncertain smile."),
    # 批 5
    ('oil', '16:9', "She stands among oil storage tanks and pumpjacks at dusk with flames from a burning refinery in the background, red sky, worried serious expression, wind, waist-up."),
    ('tired', '16:9', "Late night, she slumps over the trading desk with her cheek on the keyboard, exhausted, screens glowing behind showing tangled red and green lines, empty coffee cups, messy hair, puffed cheeks, sulking."),
    ('sink', '16:9', "She sinks slowly into dark deep water, arms loose, eyes closed, a few bubbles rising, faint blue light from far above, melancholic, wide shot, vertical composition with lots of darkness below."),
    ('confetti_hall', '16:9', "Wide shot of a crowded celebration on a trading floor, traders throwing papers and confetti, giant screens glowing red with upward arrows, she stands in the center raising one arm, triumphant."),
    ('wave_ride', '16:9', "Side view, she surfs fast across the face of a towering blue wave on a surfboard shaped like a whale, spray behind her, focused grin, speed motion, sunny sky."),
    # 批 6：年初、停火、山頂、槓桿斷線、黃金崩
    ('newyear', '16:9', "New Year's Eve midnight on a city rooftop, huge fireworks bursting in the night sky behind her, she holds a sparkler and looks up at the fireworks with a bright excited smile, warm orange and blue light, waist-up, three-quarter view."),
    ('dove', '16:9', "Morning after a storm at sea, black smoke clearing into blue sky, she stands on a ship bow and releases a white dove from her hands, sunlight breaking through clouds, relieved hopeful expression, wind in her hair."),
    ('peak', '16:9', "Night. She stands alone on the sharp summit of a towering mountain made of glowing red candlestick bars, the whole city lights far below, a cold wind, she looks up at the sky where one bright star shines, small figure in a wide epic shot."),
    ('chain', '16:9', "Close shot, dark stormy background with green lightning; she grips a thick glowing chain that is snapping apart in the middle, metal fragments and sparks flying, shocked wide eyes, dramatic motion."),
    ('gold_fall', '16:9', "Gold coins and gold bars raining down and shattering around her against a dark background, she reaches out with one hand trying to catch them, surprised sad expression, golden sparks, motion blur, waist-up."),
    # 批 7：海面線圖的天空背景（無人，地平線壓低，上方大片天空留給線圖）
    ('sky_dawn', '16:9', "No people. Wide panoramic anime background painting: a vast calm ocean at dawn, the horizon line very low near the bottom fifth of the image, huge open sky with soft pink, peach and gold clouds, first sunlight on the horizon, gentle reflections on the water, lots of empty sky, high detail, cinematic."),
    ('sky_storm', '16:9', "No people. Wide panoramic anime background painting: a dark stormy ocean at night, horizon low near the bottom fifth, massive black-blue storm clouds filling the sky, distant lightning flashes inside the clouds, heavy rain streaks, white-capped waves, ominous cold teal and deep navy palette, cinematic."),
    ('sky_night', '16:9', "No people. Wide panoramic anime background painting: a clear night sky full of stars and a faint milky way over a calm dark sea, horizon low near the bottom fifth with a thin line of distant glowing city lights, moonlight path on the water, deep navy and violet, cinematic."),
    ('sky_war', '16:9', "No people. Wide panoramic anime background painting: an ocean strait at night under a burning red-orange sky, horizon low near the bottom fifth, distant oil tankers on fire with tall black smoke columns, embers in the air, the sea reflecting fire, ominous, cinematic."),
    ('sky_gold', '16:9', "No people. Wide panoramic anime background painting: a dramatic golden sunset over the open ocean, horizon low near the bottom fifth, towering glowing cumulus clouds lit gold and crimson, sun rays bursting through, sparkling sea, triumphant mood, cinematic."),
    # 批 8：水下與鯨
    ('sea_under', '16:9', "No people. Underwater view looking up toward the bright rippling ocean surface from below, god rays streaming down into deep blue water, small bubbles, darker deep blue at the bottom, anime background painting, cinematic, empty composition."),
    ('sea_whale', '16:9', "No people. A gigantic dark-blue whale gliding just beneath the glowing ocean surface at twilight, seen from a low angle near the waterline, its long shadow and white belly, light rays, small fish, majestic, anime background painting, cinematic."),
]
n = int(sys.argv[1]); seg = J[(n - 1) * 5:n * 5]
jobs = []
for name, ratio, p in seg:
    nobody = p.startswith('No people')
    jobs.append({'out': f'10_img/muse/{name}.png', 'mode': 'muse_t2i' if nobody else 'muse_edit', 'ratio': ratio,
                 'prompt': p if nobody else KEEP + p, **({} if nobody else {'refs': REFS})})
pathlib.Path(R / '_jobs' / f'muse_b{n}.json').write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'_jobs/muse_b{n}.json', [j['out'] for j in jobs])
