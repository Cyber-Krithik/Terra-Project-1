"""Entry point for Dungeon Survivor: The Last Lantern."""
from pathlib import Path
import math
import pygame
from animation import AnimatedGif
import random

from collections import deque

pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()

WIDTH = 1152
HEIGHT = 768
FPS = 60


def make_tone(frequency, duration, volume=0.18, decay=5.0):
    if pygame.mixer.get_init() is None:
        return None
    sample_rate = pygame.mixer.get_init()[0]
    sample_count = max(1, round(sample_rate * duration))
    samples = bytearray()
    for index in range(sample_count):
        time = index / sample_rate
        envelope = math.exp(-decay * time / duration)
        wave = math.sin(2 * math.pi * frequency * time)
        sample = round(32767 * volume * envelope * wave)
        samples.extend(sample.to_bytes(2, byteorder="little", signed=True))
    return pygame.mixer.Sound(buffer=bytes(samples))


def make_sound_chord(frequencies, duration=0.16, volume=0.12):
    if pygame.mixer.get_init() is None:
        return None
    sample_rate = pygame.mixer.get_init()[0]
    sample_count = max(1, round(sample_rate * duration))
    samples = bytearray()
    for index in range(sample_count):
        time = index / sample_rate
        envelope = math.exp(-4.5 * time / duration)
        wave = sum(math.sin(2 * math.pi * frequency * time) for frequency in frequencies)
        sample = round(32767 * volume * envelope * wave / len(frequencies))
        samples.extend(sample.to_bytes(2, byteorder="little", signed=True))
    return pygame.mixer.Sound(buffer=bytes(samples))


def make_music_track(roots, melody, tempo, mood):
    if pygame.mixer.get_init() is None:
        return None

    sample_rate = pygame.mixer.get_init()[0]
    seconds_per_beat = 60 / tempo
    duration = len(roots) * 4 * seconds_per_beat
    sample_count = round(sample_rate * duration)
    samples = bytearray()
    chord_intervals = (0, 7, 12) if mood == "minor" else (0, 4, 7, 11)
    rng = random.Random(17 + len(roots) + tempo)

    def midi_frequency(note):
        return 440 * 2 ** ((note - 69) / 12)

    for sample_index in range(sample_count):
        time = sample_index / sample_rate
        beat = time / seconds_per_beat
        beat_number = int(beat)
        beat_fraction = beat - beat_number
        bar = (beat_number // 4) % len(roots)
        root = roots[bar]
        pad = sum(
            math.sin(2 * math.pi * midi_frequency(root + interval) * time)
            for interval in chord_intervals
        ) / len(chord_intervals)

        bass_envelope = math.exp(-beat_fraction * 3.6)
        bass = math.sin(math.tau * midi_frequency(root - 12) * time) * bass_envelope

        melody_step = int(beat * 2) % len(melody)
        note = melody[melody_step]
        lead = 0.0
        if note is not None:
            step_fraction = beat * 2 - int(beat * 2)
            lead_envelope = min(1.0, step_fraction * 15, (1.0 - step_fraction) * 10)
            lead = math.sin(math.tau * midi_frequency(note) * time) * lead_envelope

        kick = 0.0
        if beat_fraction < 0.13 and beat_number % 4 in (0, 2):
            kick_time = beat_fraction * seconds_per_beat
            kick = math.sin(math.tau * (78 - 22 * kick_time) * kick_time)
            kick *= math.exp(-kick_time * 24)

        snare = 0.0
        if beat_fraction < 0.085 and beat_number % 4 in (1, 3):
            snare = rng.uniform(-1, 1) * math.exp(-beat_fraction * 38)

        value = 32767 * (
            pad * 0.12
            + bass * 0.22
            + lead * (0.18 if mood == "minor" else 0.2)
            + kick * 0.32
            + snare * 0.10
        )
        edge_fade = min(1.0, time / 0.025, (duration - time) / 0.025)
        sample = round(max(-32767, min(32767, value * edge_fade)))
        samples.extend(sample.to_bytes(2, byteorder="little", signed=True))

    return pygame.mixer.Sound(buffer=bytes(samples))


SOUNDS = {
    "sword": make_tone(220, 0.12, 0.16, 4.5),
    "enemy_hit": make_tone(155, 0.10, 0.15, 5.5),
    "enemy_death": make_sound_chord((110, 164), 0.24, 0.17),
    "revive": make_sound_chord((330, 440, 554), 0.42, 0.10),
    "slam": make_tone(68, 0.42, 0.28, 2.2),
    "victory": make_sound_chord((392, 494, 587, 784), 0.75, 0.12),
    "upgrade": make_sound_chord((440, 587, 740), 0.35, 0.11),
    "bell": make_sound_chord((523, 659, 784, 1047), 1.3, 0.18),
}

MUSIC_TRACKS = {}
MUSIC_CHANNEL = None
current_music_theme = None
if pygame.mixer.get_init() is not None:
    pygame.mixer.set_reserved(1)
    MUSIC_CHANNEL = pygame.mixer.Channel(0)
    MUSIC_TRACKS = {
        "dungeon": make_music_track(
            (40, 43, 38, 35),
            (64, None, 67, 69, 71, None, 67, None, 64, 67, 71, None, 69, 67, 64, None),
            112,
            "minor",
        ),
        "victory": make_music_track(
            (57, 60, 62, 55),
            (76, None, 79, 81, 83, None, 81, 79, 76, 79, 84, None, 83, 81, 79, None),
            94,
            "major",
        ),
        "defeat": make_music_track(
            (38, 35, 33, 35),
            (62, None, 65, None, 69, None, 65, None, 62, None, 60, None, 65, None, 62, None),
            76,
            "minor",
        ),
    }


def play_sound(name):
    sound = SOUNDS.get(name)
    if sound is not None:
        sound.play()


def play_music(theme):
    global current_music_theme

    if MUSIC_CHANNEL is None or current_music_theme == theme:
        return
    track = MUSIC_TRACKS.get(theme)
    if track is None:
        return
    MUSIC_CHANNEL.play(track, loops=-1, fade_ms=700)
    current_music_theme = theme


player_dead = False
player_death_timer = 0

STATE_PAUSED = "paused"
POTION_HEAL_AMOUNT = 1

TILE_SIZE = 48
FLOOR_DARK = (45, 48, 57)
FLOOR_LIGHT = (50, 53, 62)
WALL_COLOR = (105, 91, 78)

PLAYER_SIZE = 34
PLAYER_SPEED = 240
PLAYER_COLOR = (101,210,191)
PLAYER_MAX_HEALTH = 5
BASE_PLAYER_SPEED = PLAYER_SPEED
BASE_PLAYER_MAX_HEALTH = PLAYER_MAX_HEALTH
BASE_PLAYER_ATTACK_DAMAGE = 1
screen_shake = 0.0
camera_offset_x = 0
camera_offset_y = 0
damage_numbers = []
death_particles = []
boss_victory_pending = False
player_invuln_timer = 0.0
boss_intro_timer = 0.0
boss_slam_combo_remaining = 0
boss_slam_combo_pause = 0.0
upgrade_choice_pending = False
hit_flash_timer = 0.0
combo_count = 0
combo_timer = 0.0
upgrade_choice_rects = []
hit_flash_timer = 0.0
combo_count = 0.0
combo_timer = 0.0

chest = pygame.Rect(
    2 * TILE_SIZE,
    13 * TILE_SIZE,
    TILE_SIZE,
    TILE_SIZE,
)

gate = pygame.Rect(
    22*TILE_SIZE,
    13*TILE_SIZE,
    TILE_SIZE,
    TILE_SIZE,
)

chest_open = False
has_key = False
objective_message="Defeat all guardians, claim the key, and reach the gate"

player = pygame.Rect(
    TILE_SIZE*2,
    TILE_SIZE*2,
    PLAYER_SIZE,
    PLAYER_SIZE,
)

PLAYER_ATTACK_DAMAGE = BASE_PLAYER_ATTACK_DAMAGE
PLAYER_ATTACK_COOLDOWN = 0.45

player_facing = "down"
player_attack_timer = 0.0
player_attack_flash = 0.0

player_health = PLAYER_MAX_HEALTH
player_dash_timer = 0.0
player_dash_cooldown = 0.0

PROJECT_FOLDER = Path(__file__).resolve().parent
STORY_SCENE_FOLDER = PROJECT_FOLDER / "Game_Scenes"
FESTIVAL_IMAGE = STORY_SCENE_FOLDER / "Larkspur_Festival_Scene.png"

STATE_TITLE = "title"
STATE_STORY = "story"
STATE_PLAYING = "playing"
STATE_INSTRUCTIONS = "instructions"
STATE_VICTORY = "victory"
STATE_GAME_OVER = "game_over"
STATE_CREDITS = "credits"
STORY_SCENE_FILES = [
    "Designer (1).png", # Lantern Night
    "Designer (2).png", # The Silent Bell
    "Designer (3).png", # The Opening
    "Designer (4).png", # Something Below
    "Designer (5).png", # The Lantern
    "Designer (6).png", # A Promise
    "Designer (7).png", # Descent
    "Designer (8).png", # A New Challenge
]

START_BUTTON = pygame.Rect(WIDTH // 2 - 130, round(HEIGHT * 0.75) - 32, 260, 64)
STORY_CONTINUE_BUTTON = pygame.Rect(WIDTH - 68 - 196, HEIGHT - 26 - 39, 162, 28)
DESCENT_BUTTON = pygame.Rect(WIDTH // 2 - 125, 535, 250, 42)
ENDING_ACTION_BUTTON = pygame.Rect(WIDTH // 2 - 130, 526, 260, 52)
VICTORY_RESTART_BUTTON = pygame.Rect(WIDTH // 2 - 286, 526, 260, 52)
VICTORY_HOME_BUTTON = pygame.Rect(WIDTH // 2 + 26, 526, 260, 52)
CREDITS_RESTART_BUTTON = pygame.Rect(WIDTH // 2 - 230, 532, 220, 48)
CREDITS_TITLE_BUTTON = pygame.Rect(WIDTH // 2 + 10, 532, 220, 48)
TRANSITION_SECONDS = 0.72
STORY = [
    (
        "Lantern Night (1/8)",
        [
            "Every year, the people of Larkspur gather beneath a sea of lanterns.",
            "When the Dawn Bell rings, its light carries their wishes into the night.",
        ],
    ),
    (
        "The Silent Bell (2/8)",
        [
            "But this year, the bell remained silent.",
            "The lanterns dimmed. The crowd fell still.",
        ],
    ),
    (
        "The Opening (3/8)",
        [
            "Then the earth trembled.",
            "A great crack split open beneath the old bell tower.",
        ],
    ),
    (
        "Something Below (4/8)",
        [
            "Shapes emerged from the darkness.",
            "Ancient guardians wandered the streets with empty eyes.",
        ],
    ),
    (
        "The Lantern (5/8)",
        [
            "As fear spread through the town, one light remained.",
            "A cracked lantern began to glow inside Neri's home.",
        ],
    ),
    (
        "A Promise (6/8)",
        [
            "It had belonged to Neri's grandmother, the last Bellkeeper.",
            "The woman who disappeared beneath the tower years ago.",
        ],
    ),
    (
        "Descent (7/8)",
        [
            "The lantern's flame pointed toward the dungeon below.",
            "Neri took a breath and followed its light.",
        ],
    ),
    (
        "A New Challenge (8/8)",
        [
            "Neri looks down below and sees the dungeon stretching into darkness.",
            "The last lantern flickers, and he takes a step into the unknown...",
        ],
    ),
]

state = STATE_TITLE
story_page = 0
title_font = pygame.font.SysFont("georgia", 47, bold=True)
subtitle_font = pygame.font.SysFont("avenir next", 21)
label_font = pygame.font.SysFont("avenir next", 15, bold=True)
story_title_font = pygame.font.SysFont("georgia", 36, bold=True)
story_body_font = pygame.font.SysFont("avenir next", 22)
button_font = pygame.font.SysFont("avenir next", 18, bold=True)
body_font = pygame.font.Font(None, 32)

# Hand-built crypt layout: a broad fighting hall, paired side sanctums, and
# a lower reliquary gallery that leads toward the locked eastern gate.
MAP_1 = [
    "########################",
    "#......................#",
    "#......#...............#",
    "#......#......#####....#",
    "#......#...............#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#.............#####....#",
    "#......................#",
    "#......#...............#",
    "#......#...............#",
    "#......#...............#",
    "#................##....#",
    "#......................#",
    "########################",
]

MAP_2 = [
    "########################",
    "#......................#",
    "#......................#",
    "#...#####......#####...#",
    "#...#..............#...#",
    "#...#..............#...#",
    "#...#..............#...#",
    "#......................#",
    "#..##################..#",
    "#......................#",
    "#......................#",
    "#...#..............#...#",
    "#...#..............#...#",
    "#...####........####...#",
    "#......................#",
    "########################",
]

MAP_3 = [
    "########################",
    "#......................#",
    "#......................#",
    "#...#####......#####...#",
    "#...#..............#...#",
    "#...#..............#...#",
    "#...#..............#...#",
    "#...#..............#...#",
    "#...#####......#####...#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#.....####....####.....#",
    "#......................#",
    "########################",
]

MAP_4 = [
    "########################",
    "#......................#",
    "#...###..........###...#",
    "#...#..............#...#",
    "#...#..............#...#",
    "#.......########.......#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#.......########.......#",
    "#......................#",
    "#...#..............#...#",
    "#...###..........###...#",
    "#......................#",
    "########################",
]

MAP_5 = [
    "########################",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "########################",
]

DUNGEON_ROOMS = [
    MAP_1,
    MAP_2,
    MAP_3,
    MAP_4,
    MAP_5,
]

ROOM_THEMES = (
    ("ROOT CELLARS", (132, 190, 133)),
    ("FLOODED ARCHIVE", (102, 201, 231)),
    ("EMBERWORKS", (255, 143, 89)),
    ("BELLKEEPER'S WALK", (218, 190, 128)),
    ("QUIET CHAMBER", (187, 155, 246)),
)
current_room_index = 0
total_rooms_required = 10
rooms_cleared_in_run = 0

ROOM_ENTRANCES = (2*TILE_SIZE, 7*TILE_SIZE)
player.topleft = ROOM_ENTRANCES

screen = pygame.display.set_mode((WIDTH, HEIGHT))
world_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
pygame.display.set_caption("Dungeon Survivor: The Last Lantern")
clock = pygame.time.Clock()

def get_random_enemy_mix():
    possible_enemies = [
        ("warrior", 14, 7),
        ("mage", 16, 5),
        ("zombie", 15 ,11),
        ("mage", 18, 10),
        ("warrior", 12, 10)
    ]

    count = random.randint(2, 4)
    selected = random.sample(possible_enemies, min(count, len(possible_enemies)))
    return selected

def spawn_random_room_enemies(room_index=None):
    if room_index == None:
        room_index=current_room_index

    constructors = {
        "warrior": IronboundWarrior,
        "mage": AshweaverMage,
        "zombie": HollowZombie,
    }
    enemies_in_room = []

    safe_plan_index = room_index % len(ROOM_ENEMY_PLANS)

    enemy_plan = get_random_enemy_mix()

    for enemy_type, tile_column, tile_row in enemy_plan:
        enemy_class = constructors[enemy_type]
        enemy_x = tile_column*TILE_SIZE + (TILE_SIZE-36)//2
        enemy_y = tile_row*TILE_SIZE + (TILE_SIZE+36) // 2
        enemies_in_room.append(enemy_class(enemy_x,enemy_y))

    return enemies_in_room

PLAYER_SPRITE_SIZE = (80, 80)
ENEMY_SPRITE_SIZE = (90, 90)
BOSS_SPRITE_SIZE = (128, 128)

NERI_ANIMATION_DIR = PROJECT_FOLDER / "Character Animations" / "Neri's Animations"

neri_animations = {
    "se":{
        "idle": AnimatedGif(
            NERI_ANIMATION_DIR / "Idle_Neri_SE.gif",
            size=PLAYER_SPRITE_SIZE,
        ),
        "walk": AnimatedGif(
            NERI_ANIMATION_DIR / "Walking_Neri_SE.gif",
            size=PLAYER_SPRITE_SIZE,
        ),
        "attack": AnimatedGif(
            NERI_ANIMATION_DIR / "Attacking_Neri_SE.gif",
            size=PLAYER_SPRITE_SIZE,
        ),
        "death": AnimatedGif(
            NERI_ANIMATION_DIR / "Death_Neri_SE.gif",
            size=PLAYER_SPRITE_SIZE,
            loop=False,
        ),
        "Victorious": AnimatedGif(
            NERI_ANIMATION_DIR / "Victorious_Neri.gif",
            size=PLAYER_SPRITE_SIZE,
        ),
        "Victorious2": AnimatedGif(
            NERI_ANIMATION_DIR / "Victorious2_Neri.gif",
            size=PLAYER_SPRITE_SIZE,
        ),
    },
    "sw": {
        "idle": AnimatedGif(
            NERI_ANIMATION_DIR / "Idle_Neri_SW.gif",
            size=PLAYER_SPRITE_SIZE,
        ),
        "walk": AnimatedGif(
            NERI_ANIMATION_DIR / "Walking_Neri_SW.gif",
            size=PLAYER_SPRITE_SIZE,
        ),
        "attack": AnimatedGif(
            NERI_ANIMATION_DIR / "Attacking_Neri_SW.gif",
            size=PLAYER_SPRITE_SIZE,
        ),
        "death": AnimatedGif(
            NERI_ANIMATION_DIR / "Death_Neri_SW.gif",
            size=PLAYER_SPRITE_SIZE,
            loop=False,
        ),
    },
}

active_neri_direction = "se"
active_neri_action = "idle"
active_neri_animation = neri_animations["se"]["idle"]

WARRIOR_ANIMATION_DIR = PROJECT_FOLDER / "Character Animations" / "Ironbound Warrior"

warrior_animations = {
    "se":{
        "idle": AnimatedGif(
            WARRIOR_ANIMATION_DIR / "Idle_Warrior_S.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "walk": AnimatedGif(
            WARRIOR_ANIMATION_DIR / "Walking_Warrior_SE.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "attack": AnimatedGif(
            WARRIOR_ANIMATION_DIR / "Attacking_Warrior_SE.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "death": AnimatedGif(
            WARRIOR_ANIMATION_DIR / "Defeated_Warrior_SE.gif",
            size=ENEMY_SPRITE_SIZE,
            loop=False,
        ),
    },
    "sw":{
        "idle": AnimatedGif(
            WARRIOR_ANIMATION_DIR / "Idle_Warrior_S.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "walk": AnimatedGif(
            WARRIOR_ANIMATION_DIR / "Walking_Warrior_SW.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "attack": AnimatedGif(
            WARRIOR_ANIMATION_DIR / "Attacking_Warrior_SW.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "death": AnimatedGif(
            WARRIOR_ANIMATION_DIR / "Defeated_Warrior_SW.gif",
            size=ENEMY_SPRITE_SIZE,
            loop=False,
        ),
    },
}

MAGE_ANIMATION_DIR = PROJECT_FOLDER / "Character Animations" / "Ashweaver Mage"

mage_animations = {
    "se":{
        "idle": AnimatedGif(
            MAGE_ANIMATION_DIR / "Idle_Mage_S.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "walk": AnimatedGif(
            MAGE_ANIMATION_DIR / "Walking_Mage_SE.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "attack": AnimatedGif(
            MAGE_ANIMATION_DIR / "Attacking_Mage_SE.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "death": AnimatedGif(
            MAGE_ANIMATION_DIR / "Death_Mage_SE.gif",
            size=ENEMY_SPRITE_SIZE,
            loop=False,
        ),
    },
    "sw":{
        "idle": AnimatedGif(
            MAGE_ANIMATION_DIR / "Idle_Mage_S.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "walk": AnimatedGif(
            MAGE_ANIMATION_DIR / "Walking_Mage_SW.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "attack": AnimatedGif(
            MAGE_ANIMATION_DIR / "Attacking_Mage_SW.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "death": AnimatedGif(
            MAGE_ANIMATION_DIR / "Death_Mage_SW.gif",
            size=ENEMY_SPRITE_SIZE,
            loop=False,
        ),
    },
}

ZOMBIE_ANIMATION_DIR = PROJECT_FOLDER / "Character Animations" / "Hollow Zombie"

zombie_animations = {
    "se":{
        "idle": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Idle_Zombie_S.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "walk": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Walking_Zombie_SE.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "attack": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Attacking_Zombie_SE.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "death": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Death(1)_Zombie_SE.gif",
            size=ENEMY_SPRITE_SIZE,
            loop=False,
        ),
        "revive": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Revival_Zombie_SE.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "idle2": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Idle(2)_Zombie_S.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "walk2": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Walk(2)_Zombie_SE.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "attack2": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Attack(2)_Zombie_SE.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "death2": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Death(2)_Zombie_SE.gif",
            size=ENEMY_SPRITE_SIZE,
            loop=False,
        )
    },
    "sw":{
        "idle": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Idle_Zombie_S.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "walk": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Walking_Zombie_SW.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "attack": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Attacking_Zombie_SW.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "death": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Death(1)_Zombie_SW.gif",
            size=ENEMY_SPRITE_SIZE,
            loop=False,
        ),
        "revive": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Revival_Zombie_SW.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "idle2": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Idle(2)_Zombie_S.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "walk2": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Walk(2)_Zombie_SW.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "attack2": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Attack(2)_Zombie_SW.gif",
            size=ENEMY_SPRITE_SIZE,
        ),
        "death2": AnimatedGif(
            ZOMBIE_ANIMATION_DIR / "Death(2)_Zombie_SW.gif",
            size=ENEMY_SPRITE_SIZE,
            loop=False,
        ),
    },
}

COMMANDER_ANIMATION_DIR = PROJECT_FOLDER / "Character Animations" / "Ancient Guardian Commander"

commander_animations = {
    "se": {
        "idle": AnimatedGif(
            COMMANDER_ANIMATION_DIR / "Idle_Commander_S.gif",
            size=BOSS_SPRITE_SIZE,
        ),
        "walk": AnimatedGif(
            COMMANDER_ANIMATION_DIR / "Walking_Commander_SE.gif",
            size=BOSS_SPRITE_SIZE,
        ),
        "attack": AnimatedGif(
            COMMANDER_ANIMATION_DIR / "Attacking_Commander_SE.gif",
            size=BOSS_SPRITE_SIZE,
        ),
        "slam": AnimatedGif(
            COMMANDER_ANIMATION_DIR / "GroundSlam_Commander_SE.gif",
            size=BOSS_SPRITE_SIZE,
        ),
        "death": AnimatedGif(
            COMMANDER_ANIMATION_DIR / "Defeated_Commander_SE.gif",
            size=BOSS_SPRITE_SIZE,
            loop=False,
        ),
    },
    "sw":{
        "idle": AnimatedGif(
            COMMANDER_ANIMATION_DIR / "Idle_Commander_S.gif",
            size=BOSS_SPRITE_SIZE,
        ),
        "walk": AnimatedGif(
            COMMANDER_ANIMATION_DIR / "Walking_Commander_SW.gif",
            size=BOSS_SPRITE_SIZE,
        ),
        "attack": AnimatedGif(
            COMMANDER_ANIMATION_DIR / "Attacking_Commander_SW.gif",
            size=BOSS_SPRITE_SIZE,
        ),
        "slam": AnimatedGif(
            COMMANDER_ANIMATION_DIR / "GroundSlam_Commander_SW.gif",
            size=BOSS_SPRITE_SIZE,
        ),
        "death": AnimatedGif(
            COMMANDER_ANIMATION_DIR / "Defeated_Commander_SW.gif",
            size=BOSS_SPRITE_SIZE,
            loop=False,
        ),
    },
}

# Fade in from black on launch; later transitions dissolve from the last frame.
transition_surface = pygame.Surface((WIDTH, HEIGHT)).convert()
transition_surface.fill((0, 0, 0))
transition_started = pygame.time.get_ticks()
transition_seconds = 1.35

festival_background = pygame.image.load(str(FESTIVAL_IMAGE)).convert()
festival_background = pygame.transform.smoothscale(festival_background, (WIDTH + 40, HEIGHT + 28))
story_backgrounds = []
for scene_filename in STORY_SCENE_FILES:
    scene_path = STORY_SCENE_FOLDER / scene_filename
    if scene_path.exists():
        scene_image = pygame.image.load(str(scene_path)).convert()
        scene_image = pygame.transform.smoothscale(scene_image, (WIDTH + 40, HEIGHT + 28))
        story_backgrounds.append(scene_image)
    else:
        story_backgrounds.append(None)

def stone_tone(row, column):
    """Pick a repeatable stone variation from the current room's palette."""
    tones = ((48, 51, 55), (53, 56, 59), (58, 60, 62), (44, 48, 52))
    return tones[(row * 7 + column * 11 + row * column) % len(tones)]


def draw_floor_slab(x, y, row, column):
    """Draw one broad, irregular flagstone with a chipped, beveled rim."""
    depth = min(1.0, max(0.0, y / HEIGHT))
    width = 48 + ((row * 13 + column * 7) % 4) * 12 + int(depth * 12)
    height = 29 + int(depth * 13) + ((row + column) % 3) * 2
    base = stone_tone(row, column)
    left, top = x + 2, y + 2
    slab = [
        (left + 8, top), (left + width - 7, top + 1),
        (left + width - 2, top + 6), (left + width - 3, top + height - 7),
        (left + width - 10, top + height - 2), (left + 7, top + height - 1),
        (left + 1, top + height - 7), (left, top + 7),
    ]
    shadow = tuple(max(channel - 38, 8) for channel in base)
    pygame.draw.polygon(screen, shadow, [(px + 1, py + 3) for px, py in slab])
    pygame.draw.polygon(screen, base, slab)
    highlight = tuple(min(channel + 27, 255) for channel in base)
    shadow = tuple(max(channel - 21, 0) for channel in base)
    pygame.draw.lines(screen, highlight, False, slab[:4], 1)
    pygame.draw.lines(screen, shadow, False, slab[3:7], 2)

    # A few restrained chips and hairline cracks make the paving feel worn.
    if (row * 5 + column * 3) % 7 == 0:
        crack_x = x + 13 + (column % 4) * 5
        crack_y = y + 10 + (row % 3) * 4
        pygame.draw.line(screen, (37, 42, 56), (crack_x, crack_y), (crack_x + 3, crack_y + 2), 1)
        pygame.draw.line(screen, (37, 42, 56), (crack_x + 3, crack_y + 2), (crack_x + 2, crack_y + 5), 1)


def draw_wall_block(x, y, row, column):
    """Render the dungeon masonry as chunky inset stone blocks."""
    block = pygame.Rect(x + 1, y + 1, TILE_SIZE - 2, TILE_SIZE - 2)
    wall_tones = ((44, 49, 57), (48, 53, 61), (53, 57, 64), (40, 46, 55))
    tone = wall_tones[(row * 3 + column * 5) % len(wall_tones)]
    pygame.draw.rect(screen, tuple(max(channel - 28, 5) for channel in tone), block)
    # Two staggered courses of long cut stones read as masonry, not a grid.
    course_colors = (tone, tuple(max(c - 7, 0) for c in tone))
    for course in range(2):
        course_top = block.y + 2 + course * 18
        course_height = 16
        split = 18 + ((row * 7 + column * 11 + course * 13) % 8)
        if course == 1:
            split = 8 + ((row * 5 + column * 3) % 6)
        split_x = block.x + split
        intervals = [(block.x + 2, split_x), (split_x + 3, block.right - 2)]
        for brick_x, brick_right in intervals:
            brick_rect = pygame.Rect(brick_x, course_top, brick_right - brick_x, course_height)
            pygame.draw.rect(screen, course_colors[course], brick_rect, border_radius=2)
            pygame.draw.line(screen, (83, 92, 111), (brick_rect.x + 3, brick_rect.y + 1), (brick_rect.right - 3, brick_rect.y + 1), 1)
            pygame.draw.line(screen, (28, 34, 49), (brick_rect.x + 3, brick_rect.bottom - 1), (brick_rect.right - 3, brick_rect.bottom - 1), 2)
    pygame.draw.line(screen, (88, 98, 118), (block.x + 3, block.y + 1), (block.right - 3, block.y + 1), 1)


def draw_torch(x, y, elapsed):
    """Warm wall sconces give the cold stone room a readable focal light."""
    flicker = 0.86 + 0.14 * math.sin(elapsed * 8 + x)
    glow = pygame.Surface((150, 150), pygame.SRCALPHA)
    light_color = (255, 145, 52)
    for radius, alpha in ((62, 12), (44, 21), (25, 34)):
        pygame.draw.circle(glow, (*light_color, int(alpha * flicker)), (75, 75), radius)
    screen.blit(glow, (x - 75, y - 75))
    mount = pygame.Rect(x - 7, y - 1, 14, 15)
    pygame.draw.rect(screen, (38, 39, 49), mount, border_radius=3)
    pygame.draw.rect(screen, (126, 91, 57), mount, 1, border_radius=3)
    pygame.draw.line(screen, (24, 25, 34), (x - 6, y + 10), (x + 6, y + 10), 4)
    pygame.draw.line(screen, (121, 76, 48), (x, y + 9), (x, y - 5), 3)
    flame_height = 9 + int(2 * flicker)
    pygame.draw.polygon(screen, (255, 126, 42), [(x, y - flame_height), (x - 5, y - 2), (x, y + 2), (x + 5, y - 2)])
    pygame.draw.polygon(screen, (255, 221, 125), [(x, y - flame_height + 4), (x - 2, y - 2), (x, y), (x + 2, y - 2)])


def draw_actor_shadow(rect):
    width = max(48, rect.width + 26)
    height = max(16, rect.height // 3)
    shadow = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (4, 6, 10, 105), shadow.get_rect())
    pygame.draw.ellipse(
        shadow,
        (22, 25, 30, 90),
        shadow.get_rect().inflate(-width // 4, -height // 3),
    )
    screen.blit(shadow, (rect.centerx - width // 2, rect.bottom - height // 2))


def draw_player_lantern(center, elapsed):
    glow = pygame.Surface((128, 128), pygame.SRCALPHA)
    pulse = 0.92 + 0.08 * math.sin(elapsed * 3.0)
    for radius, alpha in ((59, 8), (42, 13), (26, 18)):
        pygame.draw.circle(
            glow,
            (255, 184, 91, round(alpha * pulse)),
            (64, 64),
            radius,
        )
    screen.blit(glow, (center[0] - 64, center[1] - 64))


def draw_chest(elapsed):
    """Draw a worn, iron-bound reliquary chest for the room key."""
    glow = pygame.Surface((76, 76), pygame.SRCALPHA)
    pulse = 0.5 + 0.5 * math.sin(elapsed * 2.2)
    pygame.draw.circle(glow, (255, 190, 94, 11 + int(pulse * 9)), (38, 38), 31)
    screen.blit(glow, (chest.centerx - 38, chest.centery - 38))

    shadow = pygame.Rect(chest.x + 5, chest.y + 31, 38, 10)
    pygame.draw.ellipse(screen, (15, 17, 22), shadow)
    plinth = pygame.Rect(chest.x + 5, chest.y + 28, 38, 8)
    pygame.draw.rect(screen, (48, 49, 49), plinth, border_radius=2)
    pygame.draw.rect(screen, (93, 88, 77), plinth, 1, border_radius=2)

    body = pygame.Rect(chest.x + 7, chest.y + 14, 34, 19)
    pygame.draw.rect(screen, (65, 39, 29), body, border_radius=2)
    pygame.draw.rect(screen, (105, 62, 38), body.inflate(-4, -4), border_radius=1)
    pygame.draw.rect(screen, (35, 31, 29), body, 2, border_radius=2)

    if chest_open:
        lid = [
            (body.left + 1, body.top + 2),
            (body.left + 4, body.top - 7),
            (body.right - 4, body.top - 7),
            (body.right - 1, body.top + 2),
        ]
        pygame.draw.polygon(screen, (79, 47, 31), lid)
        pygame.draw.lines(screen, (150, 104, 57), True, lid, 2)
        pygame.draw.rect(screen, (255, 211, 117), (body.centerx - 4, body.centery - 1, 8, 4))
    else:
        lid = pygame.Rect(body.x, body.y - 5, body.width, 9)
        pygame.draw.rect(screen, (83, 49, 32), lid, border_radius=5)
        pygame.draw.rect(screen, (130, 83, 46), lid, 2, border_radius=5)

    for band_x in (body.x + 5, body.right - 7):
        pygame.draw.rect(screen, (91, 94, 91), (band_x, body.y - 3, 3, body.height + 6))
        pygame.draw.line(screen, (157, 153, 133), (band_x, body.y), (band_x + 2, body.y), 1)
    lock = pygame.Rect(body.centerx - 4, body.y + 4, 8, 11)
    pygame.draw.rect(screen, (130, 103, 62), lock, border_radius=2)
    pygame.draw.rect(screen, (207, 177, 110), lock, 1, border_radius=2)
    pygame.draw.circle(screen, (39, 34, 28), (lock.centerx, lock.y + 5), 1)
    pygame.draw.line(screen, (39, 34, 28), (lock.centerx, lock.y + 5), (lock.centerx, lock.bottom - 2), 1)


def draw_gate():
    """Draw an arched, barred dungeon portcullis in a carved stone frame."""
    arch = pygame.Rect(gate.x - 8, gate.y - 16, 64, 72)
    arch_shape = [
        (arch.left, arch.bottom), (arch.left, arch.top + 25),
        (arch.left + 5, arch.top + 12), (arch.left + 15, arch.top + 4),
        (arch.centerx, arch.top), (arch.right - 15, arch.top + 4),
        (arch.right - 5, arch.top + 12), (arch.right, arch.top + 25),
        (arch.right, arch.bottom),
    ]
    pygame.draw.polygon(screen, (27, 30, 36), arch_shape)
    pygame.draw.lines(screen, (81, 82, 80), False, arch_shape, 6)
    pygame.draw.lines(screen, (126, 121, 108), False, arch_shape[1:8], 1)
    opening = pygame.Rect(gate.x + 5, gate.y - 3, 38, 49)
    opening_shape = [
        (opening.left, opening.bottom), (opening.left, opening.top + 16),
        (opening.left + 5, opening.top + 6), (opening.centerx, opening.top),
        (opening.right - 5, opening.top + 6), (opening.right, opening.top + 16),
        (opening.right, opening.bottom),
    ]
    pygame.draw.polygon(screen, (14, 17, 21), opening_shape)

    if has_key:
        gate_door = pygame.Rect(opening.x + 8, opening.y + 14, 21, 35)
        pygame.draw.polygon(screen, (103, 67, 43), [
            gate_door.topleft, (gate_door.right + 4, gate_door.y + 4),
            (gate_door.right + 4, gate_door.bottom - 3), gate_door.bottomleft,
        ])
        pygame.draw.line(screen, (177, 137, 82), gate_door.topleft, gate_door.bottomleft, 2)
        pygame.draw.circle(screen, (205, 167, 101), (gate_door.right, gate_door.centery), 2)
    else:
        for bar_x in (opening.x + 9, opening.x + 18, opening.x + 27):
            pygame.draw.line(screen, (112, 116, 116), (bar_x, opening.y + 8), (bar_x, opening.bottom - 1), 3)
            pygame.draw.line(screen, (166, 166, 155), (bar_x, opening.y + 8), (bar_x, opening.bottom - 1), 1)
        for bar_y in (opening.y + 16, opening.y + 34):
            pygame.draw.line(screen, (92, 97, 100), (opening.x + 4, bar_y), (opening.right - 4, bar_y), 4)
            pygame.draw.line(screen, (158, 157, 146), (opening.x + 4, bar_y), (opening.right - 4, bar_y), 1)
        pygame.draw.rect(screen, (100, 76, 50), (opening.centerx - 4, opening.y + 3, 8, 11), border_radius=2)
        pygame.draw.circle(screen, (197, 158, 93), (opening.centerx, opening.y + 8), 2)


def draw_dungeon(elapsed=0):
    """Paint a shadowy flagstone chamber with masonry, torchlight, and objectives."""
    screen.fill((23, 26, 38))
    row_index = 0
    y = -4
    while y < HEIGHT:
        depth = min(1.0, max(0.0, y / HEIGHT))
        row_height = 29 + int(depth * 13) + (row_index % 3) * 2
        x = -92 + (row_index % 2) * 31
        column_index = 0
        while x < WIDTH:
            draw_floor_slab(x, y, row_index, column_index)
            width = 48 + ((row_index * 13 + column_index * 7) % 4) * 12 + int(depth * 12)
            x += width + 4
            column_index += 1
        y += row_height + 4
        row_index += 1

    for torch_x, phase in ((340, 0.0), (WIDTH - 340, 0.8)):
        pool = pygame.Surface((210, 122), pygame.SRCALPHA)
        flicker = 0.9 + 0.1 * math.sin(elapsed * 8 + torch_x + phase)
        for radius, alpha in ((96, 5), (68, 8), (38, 10)):
            pygame.draw.ellipse(
                pool,
                (255, 163, 79, int(alpha * flicker)),
                (105 - radius, 20 - radius // 3, radius * 2, radius),
            )
        screen.blit(pool, (torch_x - 105, 83))

    room_map = DUNGEON_ROOMS[current_room_index]
    for row_index, row in enumerate(room_map):
        for column_index, tile in enumerate(row):
            if tile == "#":
                draw_wall_block(column_index * TILE_SIZE, row_index * TILE_SIZE, row_index, column_index)

    # A dark lintel and worn pilasters make the walkable floor read as a chamber.
    pygame.draw.rect(screen, (25, 28, 33), (0, 0, WIDTH, 13))
    pygame.draw.line(screen, (83, 86, 87), (0, 12), (WIDTH, 12), 2)
    for x in (TILE_SIZE, WIDTH - TILE_SIZE - 8):
        pygame.draw.rect(screen, (33, 37, 42), (x, TILE_SIZE, 8, HEIGHT - 2 * TILE_SIZE))
        pygame.draw.line(screen, (75, 77, 77), (x, TILE_SIZE), (x + 7, TILE_SIZE), 2)
    pygame.draw.line(screen, (30, 34, 39), (2, HEIGHT - 43), (WIDTH - 3, HEIGHT - 43), 5)
    pygame.draw.line(screen, (78, 79, 76), (2, HEIGHT - 45), (WIDTH - 3, HEIGHT - 45), 1)
    draw_torch(340, 55, elapsed)
    draw_torch(WIDTH - 340, 55, elapsed + 0.8)
    draw_chest(elapsed)
    draw_gate()
    screen.blit(VIGNETTE, (0, 0))


def draw_room_status():
    panel = pygame.Surface((270, 82), pygame.SRCALPHA)
    pygame.draw.rect(
        panel, (12, 15, 27, 220), panel.get_rect(), border_radius=10
    )
    pygame.draw.rect(
        panel, (190, 145, 75, 225), panel.get_rect(), 2, border_radius=10
    )

    title_font = pygame.font.Font(None, 29)
    detail_font = pygame.font.Font(None, 23)

    title = title_font.render(
        ROOM_THEMES[current_room_index][0],
        True,
        ROOM_THEMES[current_room_index][1],
    )
    enemies_left = sum(
        enemy.alive
        or getattr(enemy, "reviving", False)
        or getattr(enemy, "pending_revive", False)
        for enemy in room_enemies
    )
    detail_text = f"Enemies left: {enemies_left}" if enemies_left else "Room cleared"

    detail = detail_font.render(detail_text, True, (220, 223, 231))

    threat_tier = min(3, 1 + rooms_cleared_in_run // 3)
    room_label = pygame.font.Font(None, 18).render(
        f"ROOM {min(rooms_cleared_in_run + 1, total_rooms_required)} / {total_rooms_required}"
        f"    THREAT {threat_tier}",
        True,
        (172, 180, 199),
    )
    panel.blit(room_label, (14, 7))
    panel.blit(title, (14, 23))
    panel.blit(detail, (14, 56))
    screen.blit(panel, (18,94))


def draw_boss_health():
    boss = next(
        (
            enemy for enemy in room_enemies
            if isinstance(enemy, AncientGuardianCommander)
            and not enemy.dying
        ),
        None,
    )
    if boss is None:
        return

    panel = pygame.Rect(WIDTH // 2 - 205, 94, 410, 54)
    draw_glass_panel(panel, (9, 10, 21, 226), (151, 103, 91, 200))
    name = pygame.font.Font(None, 21).render(
        "ANCIENT GUARDIAN COMMANDER",
        True,
        (235, 205, 177),
    )
    screen.blit(name, name.get_rect(center=(panel.centerx, panel.y + 14)))
    bar = pygame.Rect(panel.x + 20, panel.y + 30, panel.width - 40, 10)
    fill_width = round((bar.width - 2) * max(0, boss.health) / boss.max_health)
    pygame.draw.rect(screen, (28, 20, 25), bar, border_radius=5)
    pygame.draw.rect(
        screen,
        (174, 53, 61),
        pygame.Rect(bar.x + 1, bar.y + 1, fill_width, bar.height - 2),
        border_radius=4,
    )
    pygame.draw.rect(screen, (210, 166, 136), bar, 1, border_radius=5)

def draw_screen_flash():
    if hit_flash_timer > 0:
        flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        alpha = round(120*(hit_flash_timer/0.12))
        flash_surf.fill((210,50,50,alpha))
        screen.blit(flash_surf, (0,0))

def draw_combo_counter():
    if combo_count > 1:
        font = pygame.font.SysFont("Georgia", 22, bold=True)
        text = font.render(f"{combo_count}x COMBO!", True, (255, 215, 100))
        shadow = font.render(f"{combo_count}x COMBO!", True, (20, 15, 10))
        x = player.centerx - text.get_width() // 2
        y= player.top - 36
        screen.blit(shadow, (x+1, y+2))
        screen.blit(text,(x,y))

def draw_minimap():
    panel_width = 180
    panel_height = 42
    panel = pygame.Rect(WIDTH-panel_width-18, HEIGHT - 64, panel_width, panel_height)
    draw_glass_panel(panel, (6, 11, 23, 210), (191, 153, 96, 170))

    label = pygame.font.SysFont("avenir next", 10, bold=True).render(
        "DUNGEON PROGRESS",
        True,
        (220, 190, 130),
    )
    screen.blit(label, (panel.x + 10, panel.y + 4))

    dot_spacing = 15
    start_x = panel.x+12
    dot_y = panel.y + 27
    for i in range(total_rooms_required):
        dot_x= start_x + (i*dot_spacing)
        if i < rooms_cleared_in_run:
            color = (120, 210, 140)
        elif i == rooms_cleared_in_run:
            color = (255,210,80)
        else:
            color = (70, 75, 90)
        pygame.draw.circle(screen, color, (dot_x, dot_y), 5)

def hits_wall(rect):
    if (not has_key or room_enemies) and rect.colliderect(gate):
        return True
    room_map = DUNGEON_ROOMS[current_room_index]
    for row_index, row in enumerate(room_map):
        for column_index, tile in enumerate(row):
            if tile == "#":
                wall = pygame.Rect(
                    column_index *TILE_SIZE,
                    row_index*TILE_SIZE,
                    TILE_SIZE,
                    TILE_SIZE,
                )
                if rect.colliderect(wall):
                    return True
    return False


def enemies_remain():
    return any(
        enemy.alive
        or getattr(enemy, "reviving", False)
        or getattr(enemy, "pending_revive", False)
        for enemy in room_enemies
    )


def move_player_axis(amount, axis):
    remaining = round(amount)
    while remaining:
        step = min(8, abs(remaining)) * (1 if remaining > 0 else -1)
        if axis == "x":
            player.x += step
        else:
            player.y += step
        if hits_wall(player):
            if axis == "x":
                player.x -= step
            else:
                player.y -= step
            break
        remaining -= step


def get_player_attack_hitbox():
    reach = 38
    thickness = 30

    if player_facing == "left":
        return pygame.Rect(
            player.left - reach,
            player.centery - thickness//2,
            reach,
            thickness,
        )
    if player_facing == "right":
        return pygame.Rect(
            player.right,
            player.centery - thickness // 2,
            reach,
            thickness,
        )
    if player_facing == "up":
        return pygame.Rect(
            player.centerx - thickness // 2,
            player.top - reach,
            thickness,
            reach,
        )

    return pygame.Rect(
        player.centerx - thickness//2,
        player.bottom,
        thickness,
        reach,
    )

def find_next_path_point(start_rect, target_rect):
    """return to the center of the next floor tile on a route to the target"""
    room_map = DUNGEON_ROOMS[current_room_index]

    start = (
        start_rect.centery//TILE_SIZE,
        start_rect.centerx//TILE_SIZE,
    )
    goal = (
        target_rect.centery//TILE_SIZE,
        target_rect.centerx//TILE_SIZE,
    )

    if start == goal:
        return target_rect.center

    rows = len(room_map)
    queue = deque([start])
    previous = {start: None}

    while queue:
        row, column = queue.popleft()

        if (row, column) == goal:
            break

        for row_step, column_step in ((-1,0), (1,0), (0,-1), (0,1)):
            next_row = row+row_step
            next_column = column + column_step

            if not (0 <= next_row < rows):
                continue
            if not(0 <= next_column < len(room_map[next_row])):
                continue
            if room_map[next_row][next_column] == "#":
                continue

            next_tile = (next_row, next_column)
            if next_tile not in previous:
                previous[next_tile] = (row,column)
                queue.append(next_tile)

    if goal not in previous:
        return target_rect.center

    step = goal
    while previous[step] != start:
        step = previous[step]

    row, column = step
    return (
        column * TILE_SIZE + TILE_SIZE//2,
        row*TILE_SIZE + TILE_SIZE//2,
    )

def has_line_of_sight(enemy_rect, target_rect):
    distance = math.hypot(target_rect.centerx - enemy_rect.centerx, target_rect.centery - enemy_rect.centery)
    if distance > 350:
        return False
    return True

def draw_darkness_overlay(elapsed):
    darkness = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    darkness.fill((8, 10, 18, 225))

    flicker = 0.9 + 0.1*math.sin(elapsed * 5.0)
    lantern_radius = round(130 *flicker)

    pygame.draw.circle(darkness, (0,0,0,0), player.center, lantern_radius)
    pygame.draw.circle(darkness, (8, 10, 18, 120), player.center, lantern_radius+45)

    screen.blit(darkness, (0,0))

def spawn_sword_particles(position, facing):
    for _ in range(6):
        angle = random.uniform(-0.5, 0.5)
        if facing == "left":
            base_angle = math.pi
        elif facing == "right":
            base_angle = 0.0
        elif facing == "up":
            base_angle = (-math.pi)/2
        else:
            base_angle = math.pi/2

        final_angle = base_angle + angle
        speed = random.uniform(60, 140)
        sword_particles.append({
            "x": float(position[0]),
            "y": float(position[1]),
            "vx": math.cos(final_angle)*speed,
            "vy": math.sin(final_angle)*speed,
            "life": 0.15,
            "max_life": 0.15,
        })

def update_sword_particles(delta_seconds):
    for particle in sword_particles[:]:
        particle["life"] -= delta_seconds
        particle["x"] += particle["vx"] * delta_seconds
        particle["y"] += particle["vy"] * delta_seconds
        if particle["life"] <= 0:
            sword_particles.remove(particle)

def draw_sword_particles(surface):
    for particle in sword_particles:
        life_ratio = max(0.0, particle["life"] / particle["max_life"])
        alpha = round(255*life_ratio)
        color = (255,235, 150, alpha)
        pygame.draw.circle(
            surface,
            color,
            (round(particle["x"]), round(particle["y"])),
            3,
        )

def draw_pause_screen():
    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((3,6,14,160))
    screen.blit(veil, (0,0))

    panel = pygame.Rect(WIDTH//2-220, HEIGHT//2 - 130, 440, 260)
    draw_glass_panel(panel, (8, 13, 26, 240), (215, 174, 111, 200))

    title = story_title_font.render("GAME_PAUSED", True, (255, 231, 184))
    screen.blit(title, title.get_rect(center=(WIDTH//2, panel.y + 55)))

    resume_text = label_font.render("Press 'P' to resume", True, (232, 194, 133))
    screen.blit(resume_text, resume_text.get_rect(center=(WIDTH//2, panel.y+120)))

    quit_text = label_font.render("Press 'ESC' to quit", True, (200, 140, 140))
    screen.blit(quit_text, quit_text.get_rect(center=(WIDTH//2, panel.y+170)))

class Enemy:
    """Shared health, movement, and attack stats for dungeon enemies"""

    def __init__(
            self,
            x,
            y,
            *,
            max_health,
            speed,
            damage,
            attack_range,
            attack_cooldown,
            color,
            animations,
    ):
        self.rect = pygame.Rect(x+4,y+4,36,36)
        self.sprite_size = ENEMY_SPRITE_SIZE
        self.max_health = max_health
        self.health = max_health
        self.speed = speed
        self.damage = damage
        self.attack_range = attack_range
        self.attack_cooldown = attack_cooldown
        self.attack_timer = 0
        self.color = color
        self.alive = True
        self.path_refresh_timer = 0
        self.next_path_point = None
        self.attacking = False
        self.attack_animation_timer = 0

        self.animations = animations
        self.facing = "se"
        self.action = "walk"
        self.current_animation = self.animations[self.facing]["walk"]

        self.dying = False
        self.death_timer = 0.0
        self.ready_for_removal = False

        self.hit_flash = 0

    def move_toward(self, target_rect, delta_seconds):
        distance_to_player = math.hypot(target_rect.centerx - self.rect.centerx, target_rect.centery - self.rect.centery)
        if distance_to_player > 400:
            self.action = "idle"
            return

        self.path_refresh_timer -= delta_seconds

        if self.path_refresh_timer <= 0 or self.next_path_point is None:
            self.next_path_point = find_next_path_point(self.rect, target_rect)
            self.path_refresh_timer = 0.2

        if self.next_path_point is None:
            target_x, target_y=target_rect.center
        else:
            target_x, target_y=self.next_path_point

        dx = target_x - self.rect.centerx
        dy = target_y - self.rect.centery
        distance = (dx*dx+dy*dy)**0.5

        stop_distance = self.attack_range * 0.6
        if distance <= stop_distance or distance == 0:
            self.action = "idle"
            return

        if abs(dx) > abs(dy):
            self.facing = "se" if dx > 0 else "sw"
        else:
            self.facing = "se" if dy > 0 else "sw"

        self.action = "walk"
        travel = min(self.speed*delta_seconds, distance)
        move_x = (dx/distance)*travel
        move_y = (dy/distance) * travel

        next_rect = self.rect.copy()
        next_rect.x += round(move_x)
        if not hits_wall(next_rect):
            self.rect.x=next_rect.x
        else:
            self.next_path_point = None

        next_rect = self.rect.copy()
        next_rect.y += round(move_y)
        if not hits_wall(next_rect):
            self.rect.y = next_rect.y
        else:
            self.next_path_point = None

    def update(self, target_rect, delta_seconds):
        if self.dying:
            self.death_timer -= delta_seconds
            animation_key = "death"
            if self.action == "death" and hasattr(self, "get_animation_key"):
                animation_key = self.get_animation_key()
            death_animation = self.animations[self.facing].get(
                animation_key,
                self.animations[self.facing]["death"],
            )
            if self.current_animation != death_animation:
                self.current_animation = death_animation
                self.current_animation.reset()
            self.current_animation.update(delta_seconds)
            if self.death_timer <= 0:
                self.ready_for_removal = True
            return

        self.attack_timer = max(0.0, self.attack_timer - delta_seconds)

        if self.attack_animation_timer > 0:
            self.attack_animation_timer = max(
                0.0,
                self.attack_animation_timer - delta_seconds
            )
        else:
            self.attacking = False
            self.move_toward(target_rect, delta_seconds)
            distance_x = target_rect.centerx - self.rect.centerx
            distance_y = target_rect.centery - self.rect.centery
            distance = math.hypot(distance_x, distance_y)

            if distance <= self.attack_range and self.attack_timer <= 0:
                self.action = "attack"
                self.attacking = True
                self.attack_animation_timer = 0.45
                self.attack_timer = self.attack_cooldown
                apply_player_damage(self.damage, target_rect.midtop)

        anim_key = self.action if self.action in self.animations[self.facing] else "walk"
        target_anim = self.animations[self.facing][anim_key]

        if target_anim != self.current_animation:
            self.current_animation = target_anim
            self.current_animation.reset()

        self.current_animation.update(delta_seconds)

        self.hit_flash = max(
            0,
            self.hit_flash-delta_seconds
        )

    def draw(self, surface):
        if (
            not self.alive
            and not getattr(self, "reviving", False)
            and not self.dying
        ):
            return

        self.current_animation.draw(
            surface,
            (
                self.rect.centerx,
                self.rect.bottom - self.sprite_size[1]//2,
            ),
        )

        if not self.dying:
            bar_width = max(self.rect.width, self.sprite_size[0] - 20)
            health_ratio = self.health / self.max_health
            bar_x = self.rect.centerx - bar_width // 2
            bar_y = self.rect.bottom - self.sprite_size[1] - 8
            background = pygame.Rect(bar_x, bar_y, bar_width, 6)
            foreground = pygame.Rect(bar_x + 1, bar_y + 1, int((bar_width - 2) * health_ratio), 4)
            pygame.draw.rect(surface, (21, 20, 25), background, border_radius=3)
            pygame.draw.rect(surface, (101, 48, 48), foreground, border_radius=2)
            pygame.draw.rect(surface, (212, 192, 155), background, 1, border_radius=3)

        if self.hit_flash>0:
            flash_rect = pygame.Rect(
                0,
                0,
                self.sprite_size[0] - 12,
                self.sprite_size[1] - 12,
            )
            flash_rect.center = (
                self.rect.centerx,
                self.rect.bottom - self.sprite_size[1] // 2,
            )
            pulse = 1 + round((self.hit_flash / 0.15) * 2)
            pygame.draw.ellipse(surface, (255, 232, 177), flash_rect, pulse)

    def take_damage(self, amount):
        if self.dying:
            return False

        self.health = max(0, self.health - amount)
        self.hit_flash = 0.15
        add_damage_number(amount, self.rect.midtop, (255, 222, 150))
        add_screen_shake(3)
        play_sound("enemy_hit")

        if self.health <= 0:
            self.alive=False
            self.dying = True
            self.action = "death"
            death_key = self.animations[self.facing].get("death")
            death_length = sum(death_key.durations) if death_key else 0.8
            self.death_timer = max(1.0, death_length + 0.25)
            self.hit_flash = 0.15
            add_screen_shake(7)
            spawn_death_particles(self.rect.center)
            play_sound("enemy_death")

            if random.random() < 0.35:
                health_potions.append(HealthPotion(self.rect.centerx-12, self.rect.centery-12))
            return True
        return False

class IronboundWarrior(Enemy):
    """Fast Melee enemy that tries to get close to Neri"""
    def __init__(self, x, y):
        super().__init__(
            x,
            y,
            max_health=3,
            speed=110,
            damage=1,
            attack_range=38,
            attack_cooldown=0.6,
            color=(174,71,68),
            animations = warrior_animations,
        )


class IronboundElite(IronboundWarrior):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.max_health *= 2
        self.health = self.max_health
        self.damage = max(2, round(self.damage * 1.5))
        self.is_elite = True

    def draw(self, surface):
        super().draw(surface)
        if self.dying:
            return
        label = pygame.font.Font(None, 17).render("ELITE", True, (255, 217, 132))
        surface.blit(label, label.get_rect(center=(self.rect.centerx, self.rect.y - 13)))
        pygame.draw.rect(
            surface,
            (229, 177, 75),
            pygame.Rect(
                self.rect.centerx - (self.sprite_size[0] - 20) // 2 - 2,
                self.rect.bottom - self.sprite_size[1] - 10,
                self.sprite_size[0] - 16,
                10,
            ),
            1,
            border_radius=4,
        )


class MageProjectile:
    def __init__(self, start_position, target_position, damage, owner):
        self.position = pygame.Vector2(start_position)
        self.direction = pygame.Vector2(target_position) - self.position
        self.owner = owner

        if self.direction.length_squared()>0:
            self.direction = self.direction.normalize()

        self.speed = 260
        self.damage = damage
        self.rect = pygame.Rect(0, 0, 16, 16)
        self.rect.center = start_position
        self.glow = pygame.Surface((34, 34), pygame.SRCALPHA)
        pygame.draw.circle(self.glow, (125, 78, 187, 38), (17, 17), 16)
        pygame.draw.circle(self.glow, (166, 103, 228, 72), (17, 17), 10)

    def update(self, delta_seconds):
        if not self.owner.alive or self.owner.dying:
            return False

        self.position += self.direction *self.speed * delta_seconds
        self.rect.center = (round(self.position.x), round(self.position.y))

        if hits_wall(self.rect):
            return False

        if self.rect.colliderect(player):
            apply_player_damage(self.damage, player.midtop)
            return False

        return True

    def draw(self, surface):
        trail_end = (
            round(self.rect.centerx - self.direction.x * 18),
            round(self.rect.centery - self.direction.y * 18),
        )
        pygame.draw.line(surface, (116, 77, 165), trail_end, self.rect.center, 4)
        pygame.draw.line(surface, (195, 147, 245), trail_end, self.rect.center, 1)
        surface.blit(self.glow, (self.rect.centerx - 17, self.rect.centery - 17))
        pygame.draw.circle(surface, (177, 105, 238), self.rect.center, 8)
        pygame.draw.circle(surface, (231, 197, 255), self.rect.center, 4)

class AshweaverMage(Enemy):
    """A fragile ranged enemy that fires bolts while alive."""
    def __init__(self,x,y):
        super().__init__(
            x,
            y,
            max_health=2,
            speed=75,
            damage=1,
            attack_range=180,
            attack_cooldown=1.0,
            color=(117,92,190),
            animations = mage_animations,
        )

    def update(self, target_rect, delta_seconds):
        if self.dying or not self.alive:
            super().update(target_rect, delta_seconds)
            return

        self.attack_timer = max(0.0, self.attack_timer - delta_seconds)
        distance = math.hypot(target_rect.centerx - self.rect.centerx, target_rect.centery - self.rect.centery)

        if self.attack_animation_timer > 0:
            self.attack_animation_timer = max(0.0, self.attack_animation_timer - delta_seconds)
            self.action="attack"

        elif distance < self.attack_range * 0.65:
            dx = self.rect.centerx - target_rect.centerx
            dy = self.rect.centery - target_rect.centery
            angle = math.atan2(dy, dx)
            move_x = math.cos(angle)*self.speed * delta_seconds
            move_y = math.sin(angle)* self.speed*delta_seconds

            self.rect.x+= round(move_x)
            if hits_wall(self.rect):
                self.rect.x -= round(move_x)
            self.rect.y += round(move_y)
            if hits_wall(self.rect):
                self.rect.y -= round(move_y)
            self.action = "walk"
        elif distance > self.attack_range:
            self.move_toward(target_rect, delta_seconds)
        else:
            self.action ="idle"
            if self.attack_timer <= 0:
                enemy_projectiles.append(
                    MageProjectile(
                        self.rect.center,
                        target_rect.center,
                        self.damage,
                        self,
                    )
                )
                self.attack_timer = self.attack_cooldown
                self.attack_animation_timer = 0.45
                self.action = "attack"
        anim_key = self.action if self.action in self.animations[self.facing] else "idle"
        target_anim = self.animations[self.facing][anim_key]

        if target_anim != self.current_animation:
            self.current_animation = target_anim
            self.current_animation.reset()

        self.current_animation.update(delta_seconds)

class HollowZombie(Enemy):
    """slow enemy that returns once after its first defeat"""
    def __init__(self,x,y):
        super().__init__(
            x,
            y,
            max_health=3,
            speed=80,
            damage=1,
            attack_range=34,
            attack_cooldown=0.8,
            color=(91,143,104),
            animations = zombie_animations,
        )

        self.has_revived = False
        self.phase_two = False
        self.reviving = False
        self.pending_revive = False
        self.revive_timer=3.0

    def take_damage(self, amount):
        if self.dying or self.reviving or not self.alive:
            return False

        self.health = max(0, self.health - amount)
        self.hit_flash = 0.15
        add_damage_number(amount, self.rect.midtop, (255, 222, 150))
        add_screen_shake(3)
        play_sound("enemy_hit")

        if self.health <= 0:
            if not self.has_revived:
                self.health = 0
                self.alive = False
                self.dying = True
                self.action = "death"
                death_animation = self.animations[self.facing]["death"]
                self.death_timer = max(1.0, sum(death_animation.durations) + 0.25)
                self.pending_revive = True
                add_screen_shake(7)
                spawn_death_particles(self.rect.center)
                play_sound("enemy_death")
                return False

            self.alive = False
            self.dying = True
            self.action = "death"
            death_animation = self.animations[self.facing][self.get_animation_key()]
            self.death_timer = max(1.0, sum(death_animation.durations) + 0.25)
            add_screen_shake(7)
            spawn_death_particles(self.rect.center)
            play_sound("enemy_death")
            return True

        return False

    def update(self, target_rect, delta_seconds):
        if self.pending_revive and self.dying:
            super().update(target_rect, delta_seconds)
            if self.ready_for_removal:
                self.ready_for_removal = False
                self.dying = False
                self.pending_revive = False
                self.reviving = True
                self.revive_timer = 1.25
                self.action = "revive"
                play_sound("revive")
            return

        if self.reviving:
            self.revive_timer -= delta_seconds
            revive_animation = self.animations[self.facing]["revive"]
            if self.current_animation != revive_animation:
                self.current_animation = revive_animation
                self.current_animation.reset()
            self.current_animation.update(delta_seconds)
            if self.revive_timer <= 0:
                self.health = max(1, int(self.max_health * 0.35))
                self.alive = True
                self.reviving = False
                self.has_revived=True
                self.phase_two = True

            return
        super().update(target_rect, delta_seconds)
        anim_key = self.get_animation_key()
        if anim_key in self.animations[self.facing]:
            target_anim = self.animations[self.facing][anim_key]
            if target_anim != self.current_animation:
                self.current_animation = target_anim
                self.current_animation.reset()

    def get_animation_key(self):

        if not self.phase_two:
            return self.action

        phase_two_mapping = {
            "idle": "idle2",
            "walk": "walk2",
            "attack": "attack2",
            "death": "death2",
        }
        return phase_two_mapping.get(self.action, "walk2")

class AncientGuardianCommander(Enemy):

    def __init__(self, x, y):
        super().__init__(
            x,
            y,
            max_health=48,
            speed=65,
            damage=2,
            attack_range=95,
            attack_cooldown=2.3,
            color=(180,140,90),
            animations = commander_animations,
        )

        self.rect = pygame.Rect(x, y, 72, 72)
        self.sprite_size = BOSS_SPRITE_SIZE
        self.slam_windup = 0.0
        self.slam_windup_duration = 0.72
        self.slam_cooldown = 2.3
        self.slam_range = 112
        self.attack_timer = 1.2
        self.phase_two_spawned = False
        self.phase = 1
        self.slam_combo_remaining = 0
        self.slam_combo_pause = 0.0

    def update(self, target_rect, delta_seconds):
        if self.dying:
            super().update(target_rect, delta_seconds)
            return

        if self.health <= self.max_health * 0.25:
            self.phase = 3
            self.speed = 105
            self.damage = 3
            self.slam_cooldown = 1.3
        elif self.health <= self.max_health * 0.6:
            self.phase = 2
            self.speed = 82
            self.damage = 2
            self.slam_cooldown = 1.7
        else:
            self.phase = 1
            self.speed = 65
            self.damage = 2
            self.slam_cooldown = 2.3

        if self.phase >= 2 and not self.phase_two_spawned:
            for offset_x in (-80, 80):
                zombie = HollowZombie(self.rect.x + offset_x, self.rect.y)
                zombie.max_health = 4
                zombie.health = zombie.max_health
                zombie.speed = 90
                room_enemies.append(zombie)
            self.phase_two_spawned = True

        self.attack_timer = max(0.0, self.attack_timer - delta_seconds)
        dx = target_rect.centerx - self.rect.centerx
        dy = target_rect.centery - self.rect.centery
        distance = math.hypot(dx,dy)

        self.facing = "se" if dx >= 0 else "sw"

        if self.slam_combo_pause > 0:
            self.slam_combo_pause = max(0.0, self.slam_combo_pause - delta_seconds)
            self.action = "slam"
            if self.slam_combo_pause <= 0:
                self.slam_windup = 0.3
        elif self.slam_windup > 0:
            self.slam_windup = max(0.0, self.slam_windup - delta_seconds)
            self.action = "slam"
            if self.slam_windup <= 0:
                if distance <= self.slam_range:
                    apply_player_damage(self.damage, target_rect.midtop, True)
                play_sound("slam")
                if self.slam_combo_remaining > 1:
                    self.slam_combo_remaining -= 1
                    self.slam_combo_pause = 0.45
                else:
                    self.slam_combo_remaining = 0
                    self.attack_timer = self.slam_cooldown
                    self.action = "idle"
        elif self.attack_timer <= 0 and distance <= 135:
            if self.phase == 3:
                self.slam_combo_remaining = 3
                self.slam_windup = 0.3
            else:
                self.slam_windup = self.slam_windup_duration
            self.action = "slam"
        elif distance > self.attack_range:
            self.move_toward(target_rect, delta_seconds)
        else:
            self.action = "idle"

        anim_key = self.action if self.action in self.animations[self.facing] else "idle"
        target_anim = self.animations[self.facing][anim_key]

        if target_anim != self.current_animation:
            self.current_animation = target_anim
            self.current_animation.reset()

        self.current_animation.update(delta_seconds)


    def take_damage(self, amount):
        global boss_victory_pending
        defeated = super().take_damage(amount)
        if defeated:
            death_animation = self.animations[self.facing]["death"]
            self.death_timer = max(
                2.0,
                sum(death_animation.durations) + 0.5,
            )
            neri_animations["se"]["Victorious"].reset()
            boss_victory_pending = True
        return defeated


    def draw(self, surface):
        if self.slam_windup > 0:
            diameter = self.slam_range * 2
            telegraph = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
            pulse = (math.sin(pygame.time.get_ticks() / 70) + 1) / 2
            alpha = round(40 + pulse * 120)
            pygame.draw.circle(
                telegraph,
                (226, 89, 66, alpha),
                (self.slam_range, self.slam_range),
                self.slam_range,
            )
            pygame.draw.circle(
                telegraph,
                (255, 190, 139, min(255, alpha + 70)),
                (self.slam_range, self.slam_range),
                self.slam_range,
                3,
            )
            surface.blit(
                telegraph,
                (self.rect.centerx - self.slam_range, self.rect.centery - self.slam_range),
            )
        super().draw(surface)

health_potions = []
sword_particles = []

class HealthPotion:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 24, 24)
        self.timer = 15
        self.animation_time = 0.0

    def update(self, delta_seconds):
        self.timer -= delta_seconds
        self.animation_time += delta_seconds
        return self.timer > 0

    def draw(self, surface):
        center = self.rect.center
        bob = round(math.sin(self.animation_time * 4) * 2)
        center_y = center[1] + bob
        glow = pygame.Surface((44, 48), pygame.SRCALPHA)
        pulse = (math.sin(self.animation_time * 3.2) + 1) / 2
        pygame.draw.ellipse(
            glow,
            (242, 65, 84, 28 + round(pulse * 18)),
            (3, 3, 38, 40),
        )
        surface.blit(glow, (center[0] - 22, center_y - 24))
        pygame.draw.ellipse(
            surface,
            (15, 12, 18, 135),
            pygame.Rect(center[0] - 12, center_y + 11, 24, 7),
        )

        bottle = pygame.Rect(center[0] - 9, center_y - 6, 18, 20)
        neck = pygame.Rect(center[0] - 5, center_y - 13, 10, 9)
        cork = pygame.Rect(center[0] - 4, center_y - 17, 8, 5)
        pygame.draw.rect(surface, (58, 25, 34), bottle.inflate(4, 4), border_radius=6)
        pygame.draw.rect(surface, (190, 209, 209), neck, border_radius=3)
        pygame.draw.rect(surface, (121, 57, 62), bottle, border_radius=6)
        liquid = pygame.Rect(bottle.x + 2, bottle.y + 8, bottle.width - 4, 9)
        pygame.draw.rect(surface, (218, 49, 67), liquid, border_radius=4)
        pygame.draw.rect(surface, (248, 166, 157), bottle, 2, border_radius=6)
        pygame.draw.rect(surface, (225, 184, 119), cork, border_radius=2)
        pygame.draw.line(
            surface,
            (255, 218, 192),
            (bottle.x + 4, bottle.y + 4),
            (bottle.x + 4, bottle.y + 10),
            2,
        )
        pygame.draw.line(
            surface,
            (255, 231, 218),
            (center[0], center_y + 9),
            (center[0], center_y + 15),
            2,
        )
        pygame.draw.line(
            surface,
            (255, 231, 218),
            (center[0] - 3, center_y + 12),
            (center[0] + 3, center_y + 12),
            2,
        )

ROOM_ENEMY_PLANS = [
    #Room 1: Introduce melee combat
    [("warrior", 15, 7)],

    #Room 2: Warriors plus a ranged threat
    [("warrior", 13, 5), ("mage", 17, 9)],

    #Room 3: Adding in the Zombie
    [
        ("warrior", 13, 5),
        ("mage", 18, 5),
        ("zombie", 16, 10),
    ],
]

ENCOUNTER_WAVES = (
    ("warrior",),
    ("warrior", "mage"),
    ("warrior", "mage", "zombie"),
    ("warrior", "warrior", "mage", "zombie"),
    ("warrior", "warrior", "mage", "zombie", "zombie"),
    ("warrior", "warrior", "mage", "mage", "zombie"),
    ("warrior", "warrior", "mage", "mage", "zombie", "zombie"),
    ("warrior", "warrior", "warrior", "mage", "mage", "zombie", "zombie"),
    ("warrior", "warrior", "mage", "mage", "mage", "zombie", "zombie"),
    ("warrior", "warrior", "warrior", "mage", "mage", "mage", "zombie", "zombie"),
)


def spawn_room_enemies(room_index=None, progress_index=None):
    room_index = current_room_index if room_index is None else room_index
    progress_index = rooms_cleared_in_run if progress_index is None else progress_index

    constructors = {
        "warrior": IronboundWarrior,
        "elite": IronboundElite,
        "mage": AshweaverMage,
        "zombie": HollowZombie,
    }
    wave = ENCOUNTER_WAVES[min(progress_index, len(ENCOUNTER_WAVES) - 1)]
    if progress_index in (2, 5, 8):
        wave = ("elite",) + wave[1:]
    room_map = DUNGEON_ROOMS[room_index % len(DUNGEON_ROOMS)]
    player_tile = (ROOM_ENTRANCES[0] // TILE_SIZE, ROOM_ENTRANCES[1] // TILE_SIZE)
    chest_tile = (chest.centerx // TILE_SIZE, chest.centery // TILE_SIZE)
    gate_tile = (gate.centerx // TILE_SIZE, gate.centery // TILE_SIZE)
    selected_tiles = []
    enemy_list = []
    difficulty = min(1.72, 1.0 + progress_index * 0.08)

    for enemy_type in wave:
        candidates = [
            (column, row)
            for row in range(2, len(room_map) - 2)
            for column in range(8, len(room_map[row]) - 2)
            if room_map[row][column] == "."
            and (column, row) not in selected_tiles
            and abs(column - player_tile[0]) + abs(row - player_tile[1]) >= 4
            and abs(column - chest_tile[0]) + abs(row - chest_tile[1]) >= 3
            and abs(column - gate_tile[0]) + abs(row - gate_tile[1]) >= 3
        ]
        if not candidates:
            raise ValueError(f"No valid enemy spawn tile for room {room_index + 1}")

        tile_column, tile_row = max(
            candidates,
            key=lambda tile: (
                min(
                    abs(tile[0] - player_tile[0]) + abs(tile[1] - player_tile[1]),
                    8,
                )
                + min(
                    (
                        min(
                            abs(tile[0] - other[0]) + abs(tile[1] - other[1]),
                            5,
                        )
                        for other in selected_tiles
                    ),
                    default=5,
                ),
                -abs(tile[0] - 14),
                -abs(tile[1] - 8),
            ),
        )
        selected_tiles.append((tile_column, tile_row))

        enemy_class = constructors[enemy_type]
        enemy_x = tile_column * TILE_SIZE + (TILE_SIZE - 36) // 2
        enemy_y = tile_row * TILE_SIZE + (TILE_SIZE - 36) // 2
        enemy = enemy_class(enemy_x, enemy_y)
        enemy.max_health = max(1, round(enemy.max_health * difficulty))
        enemy.health = enemy.max_health
        enemy.speed *= 1.0 + progress_index * 0.035
        enemy.attack_cooldown = max(
            0.68,
            enemy.attack_cooldown * (1.0 - progress_index * 0.025),
        )
        enemy.attack_timer = enemy.attack_cooldown
        enemy_list.append(enemy)

    return enemy_list

def enter_next_room():
    global current_room_index, room_enemies, chest_open, has_key, objective_message
    global player_health, player_attack_timer, player_attack_flash
    global rooms_cleared_in_run, boss_victory_pending
    global boss_intro_timer, upgrade_choice_pending

    if enemies_remain():
        objective_message = "Defeat every guardian before leaving"
        return False
    if not has_key:
        objective_message = "Claim the lantern key before leaving"
        return False

    if rooms_cleared_in_run >= total_rooms_required -1:
        enemy_projectiles.clear()
        player.topleft = ROOM_ENTRANCES
        chest_open = False
        has_key = False
        player_attack_timer = 0.0
        player_attack_flash = 0.0

    if rooms_cleared_in_run == 9:
        enemy_projectiles.clear()
        boss_victory_pending = False
        boss_intro_timer = 2.5
        upgrade_choice_pending = False
        player.topleft = ROOM_ENTRANCES

        room_enemies = [
            AncientGuardianCommander(
                15*TILE_SIZE,
                7*TILE_SIZE,
            )
        ]

        objective_message = "Defeat the Ancient Guardian Commander"

        return True

    rooms_cleared_in_run+=1
    current_room_index = (current_room_index+1) % len(DUNGEON_ROOMS)

    room_enemies = spawn_room_enemies(current_room_index, rooms_cleared_in_run)
    enemy_projectiles.clear()
    chest_open=False
    has_key=False
    player.topleft=ROOM_ENTRANCES
    player_attack_timer = 0.0
    player_attack_flash = 0.0
    objective_message=(
        f"Room {rooms_cleared_in_run+1}: Defeat all guardians"
    )
    return True

room_enemies = spawn_room_enemies(0)
enemy_projectiles = []

def draw_centered(text, font, color, y):
     image=font.render(text, True, color)
     x = (WIDTH - image.get_width()) // 2
     screen.blit(image,(x,y))


def wrap_text(text, font, max_width):
    words = text.split()
    wrapped_lines = []
    current_line = ""

    for word in words:
        candidate = f"{current_line} {word}".strip()
        if font.size(candidate)[0] <= max_width:
            current_line = candidate
        else:
            if current_line:
                wrapped_lines.append(current_line)
            current_line = word

    if current_line:
        wrapped_lines.append(current_line)

    return wrapped_lines


def make_vignette():
    """Add a gentle edge shadow so the story artwork keeps its focal point."""
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(HEIGHT):
        vertical = max(0, int((abs(y - HEIGHT / 2) / (HEIGHT / 2) - 0.56) * 66))
        pygame.draw.line(shade, (4, 8, 18, vertical), (0, y), (WIDTH, y))
    for x in range(WIDTH):
        horizontal = max(0, int((abs(x - WIDTH / 2) / (WIDTH / 2) - 0.48) * 72))
        if horizontal:
            pygame.draw.line(shade, (4, 8, 18, horizontal), (x, 0), (x, HEIGHT))
    return shade


VIGNETTE = make_vignette()


def draw_cinematic_background(image, elapsed, drift=0.0):
    """Pan a little over the oversized illustration without stretching it."""
    offset_x = 20 + int(math.sin(elapsed * 0.12 + drift) * 8)
    offset_y = 14 + int(math.cos(elapsed * 0.10 + drift) * 5)
    screen.blit(image, (-offset_x, -offset_y))
    screen.blit(VIGNETTE, (0, 0))


def draw_ambient_sparks(elapsed, visible_height=HEIGHT):
    """Draw a few soft drifting lantern motes over the illustrated scenes."""
    motes = pygame.Surface((WIDTH, visible_height), pygame.SRCALPHA)
    for index in range(25):
        base_x = (index * 173 + 61) % WIDTH
        base_y = (index * 97 + 38) % max(visible_height, 1)
        x = int(base_x + math.sin(elapsed * 0.27 + index) * 5)
        y = int(base_y + math.cos(elapsed * 0.22 + index * 0.7) * 4)
        pulse = (math.sin(elapsed * 1.4 + index * 1.9) + 1) / 2
        alpha = 36 + int(pulse * 88)
        radius = 1 if index % 4 else 2
        tint = (255, 203, 119, alpha) if index % 3 else (142, 216, 232, alpha)
        pygame.draw.circle(motes, tint, (x, y), radius)
    screen.blit(motes, (0, 0))


def draw_lantern_mark(center_x, center_y, size=17):
    """A small lantern seal used as a quiet decorative accent."""
    glow = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 185, 74, 30), (size * 2, size * 2), size * 2)
    screen.blit(glow, (center_x - size * 2, center_y - size * 2))
    body = pygame.Rect(center_x - size // 2, center_y - size // 2, size, size + 4)
    pygame.draw.line(screen, (246, 202, 126), (center_x, body.top - 7), (center_x, body.top - 2), 2)
    pygame.draw.line(screen, (246, 202, 126), (body.left - 3, body.top), (body.right + 3, body.top), 2)
    pygame.draw.rect(screen, (246, 202, 126), body, 2, border_radius=3)
    pygame.draw.line(screen, (246, 202, 126), (center_x, body.top + 3), (center_x, body.bottom - 3), 1)
    pygame.draw.line(screen, (246, 202, 126), (body.left + 3, body.bottom + 2), (body.right - 3, body.bottom + 2), 2)


def draw_glass_panel(rect, fill=(7, 13, 28, 218), border=(221, 177, 104, 180)):
    """Draw a soft shadowed panel with a fine warm-metal border."""
    panel = pygame.Surface((rect.width + 14, rect.height + 14), pygame.SRCALPHA)
    pygame.draw.rect(panel, (0, 0, 0, 90), pygame.Rect(7, 8, rect.width, rect.height), border_radius=14)
    pygame.draw.rect(panel, fill, pygame.Rect(0, 0, rect.width, rect.height), border_radius=14)
    pygame.draw.rect(panel, border, pygame.Rect(0, 0, rect.width, rect.height), 1, border_radius=14)
    screen.blit(panel, (rect.x - 7, rect.y - 4))


def draw_start_button(elapsed):
    hovered = START_BUTTON.collidepoint(pygame.mouse.get_pos())
    pulse = (math.sin(elapsed * 2.0) + 1) / 2
    glow = pygame.Surface((START_BUTTON.width + 32, START_BUTTON.height + 32), pygame.SRCALPHA)
    glow_color = 35 + int(pulse * 28) if hovered else 18 + int(pulse * 13)
    pygame.draw.rect(
        glow,
        (255, 185, 78, glow_color),
        pygame.Rect(16, 16, START_BUTTON.width, START_BUTTON.height),
        border_radius=18,
    )
    screen.blit(glow, (START_BUTTON.x - 16, START_BUTTON.y - 16))
    fill = (239, 190, 105) if hovered else (190, 137, 66)
    pygame.draw.rect(screen, (12, 17, 30), START_BUTTON.move(0, 4), border_radius=13)
    pygame.draw.rect(screen, fill, START_BUTTON, border_radius=13)
    pygame.draw.rect(screen, (255, 229, 177), START_BUTTON, 2, border_radius=13)
    label = button_font.render("BEGIN THE JOURNEY", True, (25, 23, 25))
    screen.blit(label, label.get_rect(center=START_BUTTON.center))


def draw_title_screen(elapsed):
    draw_cinematic_background(festival_background, elapsed)
    draw_ambient_sparks(elapsed)

    title_panel = pygame.Rect(WIDTH // 2 - min(420, WIDTH // 2 - 36), round(HEIGHT * 0.07), min(840, WIDTH - 72), round(HEIGHT * 0.27))
    draw_glass_panel(title_panel, (5, 12, 27, 138), (232, 192, 126, 150))
    pygame.draw.line(screen, (142, 128, 105), (title_panel.x + 72, title_panel.y + 59), (title_panel.right - 72, title_panel.y + 59), 1)
    draw_lantern_mark(title_panel.x + 39, title_panel.centery, 12)
    draw_lantern_mark(title_panel.right - 39, title_panel.centery, 12)

    kicker = label_font.render("A LARKSPUR STORY", True, (246, 211, 150))
    screen.blit(kicker, kicker.get_rect(center=(WIDTH // 2, title_panel.y + 32)))
    title = title_font.render("THE LAST LANTERN", True, (255, 238, 199))
    screen.blit(title, title.get_rect(center=(WIDTH // 2, title_panel.y + 99)))
    subtitle = subtitle_font.render("When the bell falls silent, one small light must answer.", True, (220, 226, 231))
    screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, title_panel.y + 153)))

    draw_start_button(elapsed)
    hint = label_font.render("CLICK OR PRESS ENTER", True, (236, 224, 200))
    screen.blit(hint, hint.get_rect(center=(WIDTH // 2, min(HEIGHT - 38, START_BUTTON.bottom + 27))))


def draw_story_screen(elapsed):
    background = story_backgrounds[story_page]
    if background is not None:
        draw_cinematic_background(background, elapsed, story_page * 0.4)
    else:
        draw_dungeon(elapsed)
        pygame.draw.rect(screen, PLAYER_COLOR, player)
        screen.blit(VIGNETTE, (0, 0))
    draw_ambient_sparks(elapsed, HEIGHT - 250)

    panel = pygame.Rect(34, HEIGHT - 260, WIDTH - 68, 240)
    draw_glass_panel(panel, (5, 11, 25, 222), (215, 174, 111, 190))
    pygame.draw.line(screen, (211, 166, 98), (panel.x + 30, panel.y + 27), (panel.x + 55, panel.y + 27), 2)

    heading, paragraphs = STORY[story_page]
    heading = heading.rsplit(" (", 1)[0] if heading.endswith(")") else heading
    page_label = label_font.render(f"PROLOGUE     {story_page + 1:02d} / {len(STORY):02d}", True, (232, 194, 133))
    screen.blit(page_label, (panel.x + 32, panel.y + 16))
    heading_image = story_title_font.render(heading, True, (255, 231, 183))
    screen.blit(heading_image, (panel.x + 32, panel.y + 43))

    text_left = panel.x + 34
    text_right = panel.right - 34
    text_top = panel.y + 91
    footer_top = panel.bottom - 45
    available_height = footer_top - text_top - 5
    font_size = 22
    paragraph_lines = []
    while font_size >= 17:
        story_font = pygame.font.SysFont("avenir next", font_size)
        paragraph_lines = [wrap_text(paragraph, story_font, text_right - text_left) for paragraph in paragraphs]
        total_lines = sum(len(lines) for lines in paragraph_lines)
        gap = 8 * max(0, len(paragraph_lines) - 1)
        if total_lines * story_font.get_linesize() + gap <= available_height:
            break
        font_size -= 1
    y = text_top
    line_gap = story_font.get_linesize()
    for paragraph_index, lines in enumerate(paragraph_lines):
        for line in lines:
            text_image = story_font.render(line, True, (239, 239, 231))
            screen.blit(text_image, (text_left, y))
            y += line_gap
        if paragraph_index < len(paragraph_lines) - 1:
            y += 8

    progress_width = 118
    progress_x = panel.x + 32
    progress_y = panel.bottom - 23
    pygame.draw.line(screen, (85, 96, 111), (progress_x, progress_y), (progress_x + progress_width, progress_y), 2)
    pygame.draw.line(
        screen,
        (232, 183, 104),
        (progress_x, progress_y),
        (progress_x + int(progress_width * (story_page + 1) / len(STORY)), progress_y),
        2,
    )

    continue_text = "HOW TO PLAY" if story_page == len(STORY) - 1 else "CONTINUE"
    hovered = STORY_CONTINUE_BUTTON.collidepoint(pygame.mouse.get_pos())
    border_color = (255, 221, 160) if hovered else (182, 147, 98)
    pygame.draw.rect(screen, (17, 24, 39, 225), STORY_CONTINUE_BUTTON, border_radius=8)
    pygame.draw.rect(screen, border_color, STORY_CONTINUE_BUTTON, 1, border_radius=8)
    continue_image = label_font.render(continue_text, True, (249, 224, 183))
    screen.blit(continue_image, continue_image.get_rect(center=STORY_CONTINUE_BUTTON.center))


def draw_instruction_card(rect, eyebrow, title, lines):
    draw_glass_panel(rect, (10, 17, 31, 228), (175, 146, 104, 155))
    eyebrow_image = label_font.render(eyebrow.upper(), True, (220, 177, 111))
    screen.blit(eyebrow_image, (rect.x + 18, rect.y + 13))
    title_image = pygame.font.SysFont("georgia", 21, bold=True).render(title, True, (255, 231, 190))
    screen.blit(title_image, (rect.x + 18, rect.y + 35))
    body = pygame.font.SysFont("avenir next", 15)
    y = rect.y + 64
    for item in lines:
        wrapped = wrap_text(item, body, rect.width - 36)
        for line in wrapped:
            image = body.render(line, True, (224, 229, 232))
            screen.blit(image, (rect.x + 18, y))
            y += body.get_linesize() + 1


def draw_instructions_screen(elapsed):
    """Show a polished field guide before Neri enters the dungeon."""
    draw_dungeon(elapsed)
    draw_ambient_sparks(elapsed, HEIGHT - 20)
    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((4, 8, 17, 136))
    screen.blit(veil, (0, 0))

    frame = pygame.Rect(42, 34, WIDTH - 84, HEIGHT - 68)
    draw_glass_panel(frame, (7, 13, 26, 239), (220, 179, 112, 205))
    draw_lantern_mark(WIDTH // 2, 69, 12)
    heading = story_title_font.render("Before You Descend", True, (255, 231, 184))
    screen.blit(heading, heading.get_rect(center=(WIDTH // 2, 103)))
    subtitle = subtitle_font.render("A field guide for the Bellkeeper's heir", True, (210, 219, 227))
    screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 133)))

    top_y, top_h = 156, 142
    card_w = 258
    card_gap = 27
    card_left = (WIDTH - (3 * card_w + 2 * card_gap)) // 2
    draw_instruction_card(
        pygame.Rect(card_left, top_y, card_w, top_h), "01 / Movement", "Find your footing",
        ["Move: WASD or arrow keys.", "Attack: Space. Dash: Left Shift.", "Interact nearby: E."],
    )
    draw_instruction_card(
        pygame.Rect(card_left + card_w + card_gap, top_y, card_w, top_h), "02 / Survival", "Keep Neri alive",
        ["Neri: 5 hearts. Space deals 1 damage.", "Warrior: 3 hearts; contact deals 1 damage"],
    )
    draw_instruction_card(
        pygame.Rect(card_left + 2 * (card_w + card_gap), top_y, card_w, top_h), "03 / The objective", "Find the way out",
        ["Clear the room. Press E at the chest for its key, then press E at the sealed gate."],
    )

    roster_label = label_font.render("THREATS IN THE DARK", True, (227, 184, 119))
    screen.blit(roster_label, roster_label.get_rect(center=(WIDTH // 2, 319)))
    roster_y, roster_h, roster_w = 340, 136, 258
    draw_instruction_card(
        pygame.Rect(card_left, roster_y, roster_w, roster_h), "Melee / 3 hearts", "Ironbound Warrior",
        ["Presses straight into close range. Turn corners and strike when it commits."],
    )
    draw_instruction_card(
        pygame.Rect(card_left + card_w + card_gap, roster_y, roster_w, roster_h), "2 hearts / ranged", "Ashweaver Mage",
        ["Fires bolts that deal 1 damage. Use walls for cover."],
    )
    draw_instruction_card(
        pygame.Rect(card_left + 2 * (card_w + card_gap), roster_y, roster_w, roster_h), "3 hearts / rises once", "Hollow Zombie",
        ["Returns with 1 heart after its first defeat. Contact deals 1 damage."],
    )

    footer = label_font.render("CLEAR THE ROOM  ·  CLAIM THE KEY  ·  REACH THE GATE", True, (220, 202, 168))
    screen.blit(footer, footer.get_rect(center=(WIDTH // 2, 490)))
    build_note = pygame.font.SysFont("avenir next", 12, bold=True).render(
        "WARRIORS, MAGES, AND ZOMBIES GUARD THE WAY AHEAD",
        True,
        (159, 173, 188),
    )
    screen.blit(build_note, build_note.get_rect(center=(WIDTH // 2, 514)))
    hovered = DESCENT_BUTTON.collidepoint(pygame.mouse.get_pos())
    button_fill = (226, 176, 92) if hovered else (177, 126, 61)
    pygame.draw.rect(screen, (1, 5, 13), DESCENT_BUTTON.move(0, 4), border_radius=10)
    pygame.draw.rect(screen, button_fill, DESCENT_BUTTON, border_radius=10)
    pygame.draw.rect(screen, (255, 225, 170), DESCENT_BUTTON, 2, border_radius=10)
    begin = button_font.render("BEGIN DESCENT", True, (28, 24, 23))
    screen.blit(begin, begin.get_rect(center=DESCENT_BUTTON.center))
    hint = label_font.render("ENTER OR CLICK TO BEGIN  ·  ESC TO QUIT", True, (193, 204, 215))
    screen.blit(hint, hint.get_rect(center=(WIDTH // 2, 588)))


def reset_room():
    global current_room_index, room_enemies
    global player_health, chest_open, has_key, objective_message
    global PLAYER_MAX_HEALTH, PLAYER_SPEED, PLAYER_ATTACK_DAMAGE
    global player_facing, player_attack_timer, player_attack_flash
    global player_dash_timer, player_dash_cooldown
    global player_dead, player_death_timer
    global screen_shake, camera_offset_x, camera_offset_y, boss_victory_pending
    global player_invuln_timer, boss_intro_timer, upgrade_choice_pending
    global boss_slam_combo_remaining, boss_slam_combo_pause
    global rooms_cleared_in_run, active_neri_animation, active_neri_action
    global active_neri_direction
    global hit_flash_timer, combo_count, combo_timer

    current_room_index = 0
    rooms_cleared_in_run = 0
    PLAYER_MAX_HEALTH = BASE_PLAYER_MAX_HEALTH
    PLAYER_SPEED = BASE_PLAYER_SPEED
    PLAYER_ATTACK_DAMAGE = BASE_PLAYER_ATTACK_DAMAGE
    room_enemies = spawn_room_enemies(0)
    enemy_projectiles.clear()
    damage_numbers.clear()
    death_particles.clear()
    health_potions.clear()
    sword_particles.clear()

    player.topleft = ROOM_ENTRANCES
    player_health = PLAYER_MAX_HEALTH
    chest_open = False
    has_key = False
    objective_message = "Defeat all enemies, then claim the key"

    player_facing = "down"
    player_attack_timer = 0.0
    player_attack_flash = 0.0
    player_dash_timer = 0.0
    player_dash_cooldown = 0.0
    player_dead = False
    player_death_timer = 0.0
    screen_shake = 0.0
    camera_offset_x = 0
    camera_offset_y = 0
    boss_victory_pending = False
    player_invuln_timer = 0.0
    boss_intro_timer = 0.0
    boss_slam_combo_remaining = 0
    boss_slam_combo_pause = 0.0
    upgrade_choice_pending = False
    active_neri_action = "idle"
    active_neri_direction = "se"
    active_neri_animation = neri_animations["se"]["idle"]
    active_neri_animation.reset()
    neri_animations["se"]["Victorious"].reset()

def draw_ending_screen(elapsed, won=False):
    if won:
        draw_cinematic_background(festival_background, elapsed, 0.7)
        draw_ambient_sparks(elapsed)
        draw_victory_fireworks(elapsed)
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((3, 7, 17, 138))
        screen.blit(veil, (0, 0))
        panel = pygame.Rect(168, 112, WIDTH - 336, 494)
        draw_glass_panel(panel, (7, 13, 27, 232), (222, 180, 108, 210))
        draw_lantern_mark(WIDTH // 2, 168, 20)
        title = story_title_font.render("The Commander Falls", True, (255, 230, 184))
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 223)))
        message = (
            "The dungeon is silent. Neri has saved Larkspur, and the lantern's "
            "light will guide the way home."
        )
        for index, line in enumerate(wrap_text(message, subtitle_font, panel.width - 110)):
            image = subtitle_font.render(line, True, (219, 225, 231))
            screen.blit(image, image.get_rect(center=(WIDTH // 2, 276 + index * 30)))
        neri_animations["se"]["Victorious"].draw(screen, (WIDTH // 2, 424))
        draw_end_button(VICTORY_RESTART_BUTTON, "RESTART GAME")
        draw_end_button(VICTORY_HOME_BUTTON, "BACK TO HOME")
        prompt = label_font.render("R: RESTART     H: HOME", True, (234, 203, 151))
        screen.blit(prompt, prompt.get_rect(center=(WIDTH // 2, 601)))
        return

    draw_dungeon(elapsed)
    draw_ambient_sparks(elapsed)
    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((3, 7, 17, 180))
    screen.blit(veil, (0, 0))
    panel = pygame.Rect(168, 138, WIDTH - 336, 486)
    draw_glass_panel(panel, (7, 13, 27, 232), (222, 180, 108, 190))
    draw_lantern_mark(WIDTH // 2, 193, 20)
    title = story_title_font.render(
        "The Lantern Fades",
        True,
        (255, 230, 184),
    )
    screen.blit(title, title.get_rect(center=(WIDTH // 2, 251)))
    message = "The guardians overwhelm Neri, but the lantern's path remains."
    for index, line in enumerate(wrap_text(message, subtitle_font, panel.width - 100)):
        image = subtitle_font.render(line, True, (219, 225, 231))
        screen.blit(image, image.get_rect(center=(WIDTH // 2, 304 + index * 30)))
    action_label = "RESTART THE JOURNEY"
    prompt_label = "PRESS R OR ENTER TO TRY AGAIN"
    draw_end_button(ENDING_ACTION_BUTTON, action_label)
    prompt = label_font.render(prompt_label, True, (234, 203, 151))
    screen.blit(prompt, prompt.get_rect(center=(WIDTH // 2, ENDING_ACTION_BUTTON.bottom + 25)))


def draw_victory_fireworks(elapsed):
    burst_sites = (
        (WIDTH * 0.22, HEIGHT * 0.28, 0.0, (255, 100, 177)),
        (WIDTH * 0.75, HEIGHT * 0.24, 1.1, (255, 205, 105)),
        (WIDTH * 0.51, HEIGHT * 0.32, 2.2, (112, 225, 236)),
    )
    for center_x, center_y, offset, color in burst_sites:
        phase = (elapsed * 0.48 + offset) % 2.8
        if not 0.15 < phase < 1.25:
            continue
        radius = (phase - 0.15) * 72
        for ray in range(18):
            angle = math.tau * ray / 18
            x = center_x + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius * 0.72
            pygame.draw.circle(
                screen,
                color,
                (round(x), round(y)),
                2 if ray % 3 else 3,
            )


def draw_end_button(rect, label):
    hovered = rect.collidepoint(pygame.mouse.get_pos())
    fill = (226, 184, 105) if hovered else (177, 126, 61)
    pygame.draw.rect(screen, (2, 5, 13), rect.move(0, 4), border_radius=10)
    pygame.draw.rect(screen, fill, rect, border_radius=10)
    pygame.draw.rect(screen, (255, 225, 170), rect, 2, border_radius=10)
    text = button_font.render(label, True, (28, 24, 23))
    screen.blit(text, text.get_rect(center=rect.center))

def add_screen_shake(amount):
    global screen_shake
    screen_shake = max(screen_shake, float(amount))


def apply_player_damage(amount, position=None, heavy=False):
    global player_health, player_invuln_timer, hit_flash_timer

    if player_dash_timer > 0 or player_invuln_timer > 0 or player_dead:
        return False

    player_health = max(0, player_health - amount)
    player_invuln_timer = 0.7
    hit_flash_timer = 0.12
    add_damage_number(
        amount,
        position if position is not None else player.midtop,
        (255, 112, 105),
    )
    add_screen_shake(12 if heavy else 5)
    return True


def spawn_death_particles(position):
    for _ in range(12):
        death_particles.append({
            "x": float(position[0]),
            "y": float(position[1]),
            "vx": random.uniform(-85, 85),
            "vy": random.uniform(-105, -25),
            "life": random.uniform(0.35, 0.7),
            "max_life": 0.7,
            "size": random.randint(2, 5),
        })


def update_death_particles(delta_seconds):
    for particle in death_particles[:]:
        particle["life"] -= delta_seconds
        particle["x"] += particle["vx"] * delta_seconds
        particle["y"] += particle["vy"] * delta_seconds
        particle["vy"] += 115 * delta_seconds
        if particle["life"] <= 0:
            death_particles.remove(particle)


def draw_death_particles(surface):
    for particle in death_particles:
        life_ratio = max(0.0, particle["life"] / particle["max_life"])
        alpha = round(230 * life_ratio)
        radius = max(1, round(particle["size"] * (0.5 + life_ratio * 0.5)))
        particle_surface = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        center = (radius * 2, radius * 2)
        pygame.draw.circle(particle_surface, (255, 125, 58, alpha // 5), center, radius * 2)
        pygame.draw.circle(particle_surface, (255, 170, 78, alpha), center, radius)
        pygame.draw.circle(
            particle_surface,
            (255, 234, 165, alpha),
            center,
            max(1, radius // 2),
        )
        surface.blit(
            particle_surface,
            (round(particle["x"] - radius * 2), round(particle["y"] - radius * 2)),
        )


def add_damage_number(amount, position, color):
    damage_numbers.append({
        "text": str(amount),
        "x": float(position[0]),
        "y": float(position[1]),
        "timer": 0.85,
        "color": color,
    })


def update_damage_numbers(delta_seconds):
    for damage in damage_numbers[:]:
        damage["y"] -= 38 * delta_seconds
        damage["timer"] -= delta_seconds
        if damage["timer"] <= 0:
            damage_numbers.remove(damage)


def draw_damage_numbers():
    font = pygame.font.Font(None, 25)
    for damage in damage_numbers:
        alpha = min(255, round(255 * damage["timer"] / 0.85))
        image = font.render(damage["text"], True, damage["color"])
        image.set_alpha(alpha)
        shadow = font.render(damage["text"], True, (14, 12, 18))
        shadow.set_alpha(alpha)
        screen.blit(shadow, (round(damage["x"] + 1), round(damage["y"] + 2)))
        screen.blit(image, (round(damage["x"]), round(damage["y"])))


UPGRADE_OPTIONS = ("damage", "health", "speed")
UPGRADE_LABELS = {
    "damage": "+1 DAMAGE",
    "health": "+1 MAX HEALTH",
    "speed": "+20 SPEED",
}


def apply_chest_upgrade(upgrade):
    global PLAYER_ATTACK_DAMAGE, PLAYER_MAX_HEALTH, PLAYER_SPEED, player_health

    if upgrade == "damage":
        PLAYER_ATTACK_DAMAGE += 1
    elif upgrade == "health":
        PLAYER_MAX_HEALTH += 1
        player_health = min(PLAYER_MAX_HEALTH, player_health + 1)
    elif upgrade == "speed":
        PLAYER_SPEED += 20
    else:
        raise ValueError(f"Unknown chest upgrade: {upgrade}")
    play_sound("upgrade")
    return upgrade


def choose_chest_upgrade(index):
    global upgrade_choice_pending, has_key, objective_message

    if not upgrade_choice_pending or not 0 <= index < len(UPGRADE_OPTIONS):
        return False
    upgrade = apply_chest_upgrade(UPGRADE_OPTIONS[index])
    upgrade_choice_pending = False
    has_key = True
    objective_message = f"Chest upgrade: {UPGRADE_LABELS[upgrade]}! Reach the gate"
    return True


def draw_upgrade_choice():
    global upgrade_choice_rects

    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((3, 5, 12, 188))
    screen.blit(veil, (0, 0))
    panel = pygame.Rect(WIDTH // 2 - 390, HEIGHT // 2 - 154, 780, 308)
    draw_glass_panel(panel, (9, 14, 27, 248), (229, 184, 104, 225))

    eyebrow = label_font.render("THE CHEST'S LASTING GIFT", True, (239, 194, 125))
    screen.blit(eyebrow, eyebrow.get_rect(center=(WIDTH // 2, panel.y + 35)))
    heading = pygame.font.SysFont("georgia", 32, bold=True).render(
        "Choose one upgrade",
        True,
        (255, 235, 197),
    )
    screen.blit(heading, heading.get_rect(center=(WIDTH // 2, panel.y + 72)))

    button_width = 218
    button_height = 128
    gap = 18
    left = WIDTH // 2 - (3 * button_width + 2 * gap) // 2
    upgrade_choice_rects = [
        pygame.Rect(left + index * (button_width + gap), panel.y + 111, button_width, button_height)
        for index in range(len(UPGRADE_OPTIONS))
    ]

    for index, (upgrade, rect) in enumerate(zip(UPGRADE_OPTIONS, upgrade_choice_rects)):
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        fill = (42, 47, 60, 246) if not hovered else (65, 57, 47, 250)
        border = (191, 148, 81, 220) if not hovered else (255, 218, 146, 255)
        card = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(card, fill, card.get_rect(), border_radius=12)
        pygame.draw.rect(card, border, card.get_rect(), 2, border_radius=12)
        screen.blit(card, rect)

        icon_center = (rect.centerx, rect.y + 43)
        if upgrade == "damage":
            pygame.draw.line(screen, (227, 205, 161), (icon_center[0] - 13, icon_center[1] + 12), (icon_center[0] + 10, icon_center[1] - 11), 5)
            pygame.draw.polygon(screen, (255, 222, 151), [
                (icon_center[0] + 13, icon_center[1] - 15),
                (icon_center[0] + 7, icon_center[1] - 10),
                (icon_center[0] + 15, icon_center[1] - 7),
            ])
            pygame.draw.line(screen, (164, 120, 76), (icon_center[0] - 16, icon_center[1] + 3), (icon_center[0] - 5, icon_center[1] + 14), 3)
        elif upgrade == "health":
            pygame.draw.circle(screen, (225, 83, 90), (icon_center[0] - 8, icon_center[1] - 2), 9)
            pygame.draw.circle(screen, (225, 83, 90), (icon_center[0] + 8, icon_center[1] - 2), 9)
            pygame.draw.polygon(screen, (225, 83, 90), [
                (icon_center[0] - 16, icon_center[1]),
                (icon_center[0] + 16, icon_center[1]),
                (icon_center[0], icon_center[1] + 17),
            ])
            pygame.draw.line(screen, (255, 210, 181), (icon_center[0], icon_center[1] - 9), (icon_center[0], icon_center[1] + 7), 2)
            pygame.draw.line(screen, (255, 210, 181), (icon_center[0] - 7, icon_center[1] - 1), (icon_center[0] + 7, icon_center[1] - 1), 2)
        else:
            pygame.draw.line(screen, (124, 210, 221), (icon_center[0] - 16, icon_center[1] - 9), (icon_center[0] + 8, icon_center[1] - 9), 3)
            pygame.draw.line(screen, (124, 210, 221), (icon_center[0] - 8, icon_center[1]), (icon_center[0] + 15, icon_center[1]), 3)
            pygame.draw.line(screen, (124, 210, 221), (icon_center[0] - 16, icon_center[1] + 9), (icon_center[0] + 5, icon_center[1] + 9), 3)
            pygame.draw.polygon(screen, (208, 244, 242), [
                (icon_center[0] + 16, icon_center[1]),
                (icon_center[0] + 7, icon_center[1] - 6),
                (icon_center[0] + 7, icon_center[1] + 6),
            ])

        label = pygame.font.SysFont("avenir next", 16, bold=True).render(
            UPGRADE_LABELS[upgrade],
            True,
            (245, 231, 202),
        )
        screen.blit(label, label.get_rect(center=(rect.centerx, rect.y + 86)))
        key_hint = pygame.font.Font(None, 19).render(f"PRESS {index + 1}", True, (186, 194, 203))
        screen.blit(key_hint, key_hint.get_rect(center=(rect.centerx, rect.y + 111)))


def draw_boss_intro():
    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((2, 3, 9, 126))
    screen.blit(veil, (0, 0))
    pulse = 0.92 + 0.08 * math.sin(pygame.time.get_ticks() / 180)
    title = pygame.font.SysFont("georgia", 34, bold=True).render(
        "ANCIENT GUARDIAN COMMANDER",
        True,
        (round(255 * pulse), round(222 * pulse), round(172 * pulse)),
    )
    subtitle = pygame.font.SysFont("avenir next", 16, bold=True).render(
        "THE LAST BELLKEEPER'S TRIAL",
        True,
        (220, 213, 199),
    )
    panel = pygame.Rect(WIDTH // 2 - 390, HEIGHT // 2 - 65, 780, 130)
    draw_glass_panel(panel, (8, 10, 20, 235), (187, 133, 88, 210))
    screen.blit(title, title.get_rect(center=(WIDTH // 2, panel.y + 51)))
    screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, panel.y + 90)))

def draw_credits_screen(elapsed):
    draw_cinematic_background(festival_background, elapsed, 1.4)
    draw_ambient_sparks(elapsed)
    panel = pygame.Rect(184, 98, WIDTH - 368, 564)
    draw_glass_panel(panel, (7, 13, 27, 228), (222, 180, 108, 190))
    draw_lantern_mark(WIDTH // 2, 150, 18)
    title = story_title_font.render("The Last Lantern", True, (255, 230, 184))
    screen.blit(title, title.get_rect(center=(WIDTH // 2, 211)))
    subtitle = subtitle_font.render("A story of courage, memory, and the light we share.", True, (219, 225, 231))
    screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 260)))

    credit_lines = (
        ("A JOURNEY THROUGH LARKSPUR", (232, 194, 133)),
        ("The Dawn Bell is singing again.", (239, 239, 231)),
        ("Thank you for carrying Neri home.", (239, 239, 231)),
        ("Beyond the town, a newly lit trail waits.", (180, 202, 218)),
    )
    for index, (line, color) in enumerate(credit_lines):
        font = label_font if index == 0 else subtitle_font
        image = font.render(line, True, color)
        screen.blit(image, image.get_rect(center=(WIDTH // 2, 333 + index * 42)))

    draw_end_button(CREDITS_RESTART_BUTTON, "PLAY AGAIN")
    draw_end_button(CREDITS_TITLE_BUTTON, "RETURN TO TITLE")
    hint = label_font.render("R: PLAY AGAIN    T: TITLE    ESC: QUIT", True, (213, 207, 187))
    screen.blit(hint, hint.get_rect(center=(WIDTH // 2, 607)))


def transition_to(next_state, next_page=None, duration=TRANSITION_SECONDS):
    """Dissolve from the exact current frame into the next cinematic beat."""
    global state, story_page, transition_surface, transition_started, transition_seconds
    transition_surface = screen.copy()
    state = next_state
    if next_page is not None:
        story_page = next_page
    transition_started = pygame.time.get_ticks()
    transition_seconds = duration


def draw_transition():
    """Layer the outgoing frame over the new one for a smooth crossfade."""
    elapsed = (pygame.time.get_ticks() - transition_started) / 1000
    progress = min(1.0, elapsed / transition_seconds)
    alpha = round(255 * (1.0 - progress))
    if alpha > 0:
        transition_surface.set_alpha(alpha)
        screen.blit(transition_surface, (0, 0))
    return progress >= 1.0


def draw_letterbox():
    """Add restrained cinema bars without covering the story or controls."""
    pygame.draw.rect(screen, (3, 5, 12), (0, 0, WIDTH, 18))
    pygame.draw.rect(screen, (3, 5, 12), (0, HEIGHT - 18, WIDTH, 18))

running = True

while running:
    delta_seconds = min(clock.tick(FPS) / 1000, 0.05)
    animation_time = pygame.time.get_ticks() / 1000

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif (pygame.time.get_ticks() - transition_started) / 1000 < transition_seconds:
                continue
            elif state == STATE_TITLE and event.key in (
                 pygame.K_RETURN,
                 pygame.K_SPACE,
            ):
                 transition_to(STATE_STORY, 0)
            elif state == STATE_STORY and event.key in (
                 pygame.K_RETURN,
                 pygame.K_SPACE,
            ):
                if story_page < len(STORY) - 1:
                    transition_to(STATE_STORY, story_page + 1)
                else:
                     transition_to(STATE_INSTRUCTIONS)
            elif state == STATE_INSTRUCTIONS and event.key in (
                 pygame.K_RETURN,
                 pygame.K_SPACE,
            ):
                transition_to(STATE_PLAYING)
            elif state == STATE_PLAYING and upgrade_choice_pending and event.key in (
                pygame.K_1,
                pygame.K_2,
                pygame.K_3,
            ):
                choose_chest_upgrade(event.key - pygame.K_1)
            elif state == STATE_PLAYING and (boss_intro_timer > 0 or player_dead):
                continue
            elif state == STATE_VICTORY and event.key in (
                pygame.K_r,
                pygame.K_RETURN,
                pygame.K_SPACE,
            ):
                reset_room()
                transition_to(STATE_PLAYING)
            elif state == STATE_VICTORY and event.key in (pygame.K_h, pygame.K_HOME):
                reset_room()
                transition_to(STATE_TITLE)
            elif state == STATE_PLAYING and event.key == pygame.K_e:
                if upgrade_choice_pending:
                    continue
                if player.colliderect(chest.inflate(28, 28)):
                    if enemies_remain():
                        objective_message = "Defeat all enemies before claiming the key"
                    elif not chest_open:
                        chest_open = True
                        upgrade_choice_pending = True
                        objective_message = "Choose one of the chest's three upgrades"
                elif player.colliderect(gate.inflate(30,30)):
                    enter_next_room()
            elif state == STATE_GAME_OVER and event.key in (
                pygame.K_r,
                pygame.K_RETURN,
                pygame.K_SPACE,
            ):
                reset_room()
                transition_to(STATE_PLAYING)
            elif state == STATE_CREDITS and event.key == pygame.K_r:
                reset_room()
                transition_to(STATE_PLAYING)
            elif state == STATE_CREDITS and event.key == pygame.K_t:
                transition_to(STATE_TITLE)
            elif event.key == pygame.K_LSHIFT and state == STATE_PLAYING and not player_dead:
                if not upgrade_choice_pending and boss_intro_timer <= 0 and player_dash_cooldown <= 0:
                    player_dash_timer = 0.18
                    player_dash_cooldown = 1.5
            elif event.key== pygame.K_p and state in (STATE_PLAYING, STATE_PAUSED):
                state = STATE_PLAYING if state == STATE_PAUSED else STATE_PAUSED

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if (pygame.time.get_ticks() - transition_started) / 1000 < transition_seconds:
                continue
            if state == STATE_PLAYING and upgrade_choice_pending:
                selected_upgrade = next(
                    (
                        index for index, rect in enumerate(upgrade_choice_rects)
                        if rect.collidepoint(event.pos)
                    ),
                    None,
                )
                if selected_upgrade is not None:
                    choose_chest_upgrade(selected_upgrade)
            elif state == STATE_TITLE and START_BUTTON.collidepoint(event.pos):
                transition_to(STATE_STORY, 0)
            elif state == STATE_STORY and STORY_CONTINUE_BUTTON.collidepoint(event.pos):
                if story_page < len(STORY) -1:
                      transition_to(STATE_STORY, story_page + 1)
                else:
                 transition_to(STATE_INSTRUCTIONS)
            elif state == STATE_INSTRUCTIONS and DESCENT_BUTTON.collidepoint(event.pos):
                transition_to(STATE_PLAYING)
            elif state == STATE_VICTORY and VICTORY_RESTART_BUTTON.collidepoint(event.pos):
                reset_room()
                transition_to(STATE_PLAYING)
            elif state == STATE_VICTORY and VICTORY_HOME_BUTTON.collidepoint(event.pos):
                reset_room()
                transition_to(STATE_TITLE)
            elif state == STATE_GAME_OVER and ENDING_ACTION_BUTTON.collidepoint(event.pos):
                reset_room()
                transition_to(STATE_PLAYING)
            elif state == STATE_CREDITS and CREDITS_RESTART_BUTTON.collidepoint(event.pos):
                reset_room()
                transition_to(STATE_PLAYING)
            elif state == STATE_CREDITS and CREDITS_TITLE_BUTTON.collidepoint(event.pos):
                transition_to(STATE_TITLE)

    if state == STATE_PLAYING:
        play_music("dungeon")
    elif state == STATE_VICTORY:
        play_music("victory")
    elif state == STATE_CREDITS:
        play_music("victory")
    elif state == STATE_GAME_OVER:
        play_music("defeat")

    if state == STATE_VICTORY:
        neri_animations["se"]["Victorious"].update(delta_seconds)

    if state == STATE_PLAYING:
        player_attack_timer = max(0, player_attack_timer - delta_seconds)
        player_attack_flash = max(0, player_attack_flash - delta_seconds)
        player_dash_timer = max(0, player_dash_timer - delta_seconds)
        player_dash_cooldown = max(0, player_dash_cooldown - delta_seconds)
        player_invuln_timer = max(0, player_invuln_timer - delta_seconds)
        boss_intro_timer = max(0, boss_intro_timer - delta_seconds)
        controls_locked = player_dead or upgrade_choice_pending or boss_intro_timer > 0
        current_speed = PLAYER_SPEED * (3 if player_dash_timer > 0 else 1)
        keys = pygame.key.get_pressed()
        move_x = 0
        move_y = 0

        for potion in health_potions[:]:
            if not potion.update(delta_seconds):
                health_potions.remove(potion)
            elif not player_dead and player.colliderect(potion.rect):
                if player_health < PLAYER_MAX_HEALTH:
                    player_health = min(PLAYER_MAX_HEALTH, player_health + POTION_HEAL_AMOUNT)
                    play_sound("upgrade")
                    health_potions.remove(potion)
        update_sword_particles(delta_seconds)

        if combo_timer > 0:
            combo_timer -= delta_seconds
            if combo_timer <= 0:
                combo_count = 0

        if not controls_locked and (keys[pygame.K_LEFT] or keys[pygame.K_a]):
            move_x -= current_speed * delta_seconds
        if not controls_locked and (keys[pygame.K_RIGHT] or keys[pygame.K_d]):
            move_x += current_speed * delta_seconds
        if not controls_locked and (keys[pygame.K_UP] or keys[pygame.K_w]):
            move_y -= current_speed * delta_seconds
        if not controls_locked and (keys[pygame.K_DOWN] or keys[pygame.K_s]):
            move_y += current_speed * delta_seconds

        if not controls_locked and move_x != 0 and move_y != 0:
            move_x *= 0.70710678
            move_y *= 0.70710678

        # Keep Neri's facing and sprite animation in sync with the controls.
        if not controls_locked and (move_x != 0 or move_y != 0):
            if abs(move_x) > abs(move_y):
                player_facing = "right" if move_x > 0 else "left"
            else:
                player_facing = "down" if move_y > 0 else "up"

        next_neri_action = (
            "death"
            if player_dead
            else "attack"
            if player_attack_flash > 0
            else "walk"
            if move_x != 0 or move_y != 0
            else "idle"
        )
        next_neri_direction = active_neri_direction if player_dead else (
            "sw" if player_facing in ("left", "down") else "se"
        )
        if (next_neri_action, next_neri_direction) != (
            active_neri_action,
            active_neri_direction,
        ):
            active_neri_action = next_neri_action
            active_neri_direction = next_neri_direction
            active_neri_animation = neri_animations[active_neri_direction][active_neri_action]
            active_neri_animation.reset()
        active_neri_animation.update(delta_seconds)

        move_player_axis(move_x, "x")
        move_player_axis(move_y, "y")

        if not controls_locked and keys[pygame.K_SPACE] and player_attack_timer <= 0:
            attack_hitbox = get_player_attack_hitbox()
            player_attack_timer = PLAYER_ATTACK_COOLDOWN
            player_attack_flash = 0.12
            play_sound("sword")
            spawn_sword_particles(player.center, player_facing)
            for room_enemy in room_enemies[:]:
                if (
                    room_enemy.alive
                    and not room_enemy.dying
                    and not getattr(room_enemy, "reviving", False)
                    and attack_hitbox.colliderect(room_enemy.rect)
                ):
                    room_enemy.take_damage(PLAYER_ATTACK_DAMAGE)
                    combo_count += 1
                    combo_timer = 2.0

        if not upgrade_choice_pending and boss_intro_timer <= 0:
            for room_enemy in room_enemies[:]:
                room_enemy.update(player, delta_seconds)
            room_enemies[:] = [
                enemy for enemy in room_enemies
                if not getattr(enemy, "ready_for_removal", False)
            ]

            for projectile in enemy_projectiles[:]:
                if not projectile.update(delta_seconds):
                    enemy_projectiles.remove(projectile)

        if player_health <= 0 and not player_dead:
            player_dead = True
            death_animation = neri_animations[active_neri_direction]["death"]
            player_death_timer = max(1.8, sum(death_animation.durations) + 0.45)
            active_neri_action = "death"

        if player_dead:
            player_death_timer -= delta_seconds
            if player_death_timer <= 0:
                transition_to(STATE_GAME_OVER)

        if boss_victory_pending and not any(
            isinstance(enemy, AncientGuardianCommander)
            for enemy in room_enemies
        ):
            enemy_projectiles.clear()
            neri_animations["se"]["Victorious"].reset()
            transition_to(STATE_VICTORY)
            play_sound("victory")

        update_damage_numbers(delta_seconds)
        update_death_particles(delta_seconds)

    if state == STATE_PLAYING:
        if screen_shake > 0:
            camera_offset_x = random.randint(-round(screen_shake), round(screen_shake))
            camera_offset_y = random.randint(-round(screen_shake), round(screen_shake))
            screen_shake = max(0.0, screen_shake - 36 * delta_seconds)
        else:
            camera_offset_x = 0
            camera_offset_y = 0

    if state == STATE_TITLE:
        draw_title_screen(animation_time)
    elif state == STATE_STORY:
        draw_story_screen(animation_time)
    elif state == STATE_INSTRUCTIONS:
        draw_instructions_screen(animation_time)
    elif state == STATE_VICTORY:
        draw_ending_screen(animation_time, won=True)
    elif state == STATE_GAME_OVER:
        draw_ending_screen(animation_time)
    elif state == STATE_CREDITS:
        draw_credits_screen(animation_time)
    else:
        display_surface = screen
        world_surface.fill((0, 0, 0, 0))
        screen = world_surface
        draw_dungeon(animation_time)
        for projectile in enemy_projectiles:
            projectile.draw(screen)
        actors = [(enemy.rect.bottom, 0, enemy) for enemy in room_enemies]
        actors.append((player.bottom, 1, None))
        for _, is_player, actor in sorted(actors, key=lambda item: (item[0], item[1])):
            if is_player:
                draw_actor_shadow(player)
                draw_player_lantern((player.centerx, player.centery), animation_time)
                active_neri_animation.draw(
                    screen,
                    (player.centerx, player.bottom - PLAYER_SPRITE_SIZE[1] // 2),
                )
                if player_invuln_timer > 0 and int(player_invuln_timer * 18) % 2 == 0:
                    pygame.draw.ellipse(
                        screen,
                        (255, 226, 160),
                        pygame.Rect(
                            player.centerx - PLAYER_SPRITE_SIZE[0] // 2 - 4,
                            player.bottom - PLAYER_SPRITE_SIZE[1] - 4,
                            PLAYER_SPRITE_SIZE[0] + 8,
                            PLAYER_SPRITE_SIZE[1] + 8,
                        ),
                        2,
                    )
                if player_dash_timer > 0:
                    pygame.draw.circle(
                        screen,
                        (255, 210, 120),
                        player.center,
                        30,
                        2,
                    )
            else:
                draw_actor_shadow(actor.rect)
                actor.draw(screen)
        draw_damage_numbers()
        draw_death_particles(screen)

        for potion in health_potions:
            potion.draw(screen)
        draw_sword_particles(screen)
        draw_darkness_overlay(animation_time)

        screen = display_surface
        screen.fill((4, 6, 11))
        screen.blit(world_surface, (camera_offset_x, camera_offset_y))

        health_panel_width = max(208, 54 + (PLAYER_MAX_HEALTH - 1) * 29)
        health_panel = pygame.Rect(18, 27, health_panel_width, 55)
        draw_glass_panel(health_panel, (6, 11, 23, 220), (191, 153, 96, 170))
        name = label_font.render("NERI", True, (233, 211, 176))
        screen.blit(name, (health_panel.x + 14, health_panel.y + 9))
        for heart_index in range(PLAYER_MAX_HEALTH):
            color = (219, 91, 91) if heart_index < player_health else (78, 68, 75)
            center = (health_panel.x + 28 + heart_index * 29, health_panel.y + 36)
            pygame.draw.circle(screen, color, (center[0] - 4, center[1] - 2), 5)
            pygame.draw.circle(screen, color, (center[0] + 4, center[1] - 2), 5)
            pygame.draw.polygon(screen, color, [(center[0] - 9, center[1]), (center[0] + 9, center[1]), (center[0], center[1] + 9)])

        objective_panel = pygame.Rect(WIDTH - 314, 27, 296, 55)
        draw_glass_panel(objective_panel, (6, 11, 23, 220), (191, 153, 96, 170))
        objective_label = pygame.font.SysFont("avenir next", 12, bold=True).render("THE BELLKEEPER'S TRIAL", True, (239, 204, 141))
        objective_text = pygame.font.SysFont("avenir next", 14).render(objective_message, True, (224, 229, 232))
        screen.blit(objective_label, objective_label.get_rect(center=(objective_panel.centerx, objective_panel.y + 16)))
        screen.blit(objective_text, objective_text.get_rect(center=(objective_panel.centerx, objective_panel.y + 38)))
        if upgrade_choice_pending:
            draw_upgrade_choice()
        if boss_intro_timer > 0:
            draw_boss_intro()

    if state == STATE_PLAYING:
        hit_flash_timer = max(0.0, hit_flash_timer - delta_seconds)

    if state in (STATE_PLAYING, STATE_PAUSED):
        draw_room_status()
        draw_boss_health()
        draw_combo_counter()
        draw_minimap()
        draw_screen_flash()
        if state == STATE_PAUSED:
            draw_pause_screen()

    draw_letterbox()
    draw_transition()

    if state == STATE_PLAYING and player_attack_flash > 0:
        pygame.draw.rect(
            screen,
            (255, 211, 130),
            get_player_attack_hitbox(),
            2,
            border_radius=6,
        )

    pygame.display.flip()

pygame.quit()
