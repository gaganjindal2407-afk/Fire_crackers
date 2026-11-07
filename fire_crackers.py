import pygame
import numpy as np
import random
import math
import sys

# ---------------------------------------------------------
# SETUP & RESOLUTION
# ---------------------------------------------------------
WIDTH, HEIGHT = 1100, 750
FPS = 60
GROUND_Y = HEIGHT - 85

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Virtual Real-Life Fireworks Simulator")
clock = pygame.time.Clock()

# Pre-rendered glow textures for fast bloom
GLOW_CACHE = {}

def get_glow_surface(radius, color):
    r_key = int(max(4, radius))
    key = (r_key, color)
    if key in GLOW_CACHE:
        return GLOW_CACHE[key]
    
    size = r_key * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    steps = 6
    for i in range(steps, 0, -1):
        rad = r_key * (i / steps)
        alpha = int(40 * (1.0 - (i / steps))**1.6)
        pygame.draw.circle(surf, (*color, alpha), (r_key, r_key), int(rad))
        
    GLOW_CACHE[key] = surf
    return surf

# ---------------------------------------------------------
# VECTORIZED PROCEDURAL AUDIO (Fast & Zero-Lag)
# ---------------------------------------------------------
SAMPLE_RATE = 44100

def to_sound(samples):
    samples = np.clip(samples, -1.0, 1.0)
    int_samples = np.int16(samples * 32767)
    stereo = np.column_stack((int_samples, int_samples))
    return pygame.sndarray.make_sound(np.ascontiguousarray(stereo))

def create_boom_sound(duration=1.2, bass_depth=180.0):
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, False)
    freq = bass_depth * np.exp(-12.0 * t) + 26.0
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    bass = np.sin(phase) * np.exp(-3.5 * t)
    
    noise = np.random.normal(0, 0.8, n) * np.exp(-10.0 * t)
    click = np.random.uniform(-1, 1, n) * np.exp(-100.0 * t)
    
    combined = np.tanh((0.6 * bass + 0.6 * noise + 0.35 * click) * 1.7)
    return to_sound(combined)

def create_snap_sound():
    duration = 0.08
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, False)
    noise = np.random.uniform(-1, 1, n)
    hp_noise = np.diff(noise, prepend=noise[0])
    envelope = np.exp(-70.0 * t)
    return to_sound(np.tanh(hp_noise * envelope * 2.0))

def create_whistle_sound(duration=0.8):
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, False)
    f0 = 350.0 * np.exp(1.8 * (t / duration))
    phase0 = 2 * np.pi * np.cumsum(f0) / SAMPLE_RATE
    whistle = np.sin(phase0) + 0.4 * np.sin(phase0 * 2.0)
    envelope = np.sin(np.pi * (t / duration)) ** 0.6
    return to_sound(whistle * envelope * 0.45)

def create_sizzle_sound(duration=0.25):
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, False)
    sparks = np.random.choice([0.0, 1.0], size=n, p=[0.96, 0.04]) * np.random.uniform(-1, 1, n)
    base = np.random.normal(0, 0.25, n) * np.exp(-3.0 * t)
    return to_sound((sparks * 0.8 + base * 0.2) * 0.7)

SOUND_BOOM = create_boom_sound(1.3, 190.0)
SOUND_POP = create_boom_sound(0.5, 130.0)
SOUND_SNAP = create_snap_sound()
SOUND_WHISTLE = create_whistle_sound(0.8)
SOUND_SIZZLE = create_sizzle_sound(0.25)

# ---------------------------------------------------------
# OPTIMIZED PARTICLES & SMOKE
# ---------------------------------------------------------
class SmokePuff:
    def __init__(self, x, y, vx, vy, initial_radius=7):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.radius = initial_radius
        self.max_radius = initial_radius * random.uniform(2.5, 4.0)
        self.alpha = random.uniform(35, 60)
        self.decay = random.uniform(0.6, 1.1)

    def update(self):
        self.vx *= 0.96
        self.vy *= 0.96
        self.vy -= 0.02
        self.x += self.vx + 0.1
        self.y += self.vy
        self.radius += (self.max_radius - self.radius) * 0.04
        self.alpha -= self.decay
        return self.alpha > 0

    def draw(self, surface):
        if self.alpha <= 0:
            return
        surf = pygame.Surface((int(self.radius * 2), int(self.radius * 2)), pygame.SRCALPHA)
        pygame.draw.circle(surf, (50, 48, 54, int(self.alpha)), (int(self.radius), int(self.radius)), int(self.radius))
        surface.blit(surf, (self.x - self.radius, self.y - self.radius))


class SparkStreak:
    def __init__(self, x, y, vx, vy, color, radius=2.5, decay=5.5, gravity=0.2, drag=0.965, tail_len=1.8):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.radius = radius
        self.decay = decay
        self.alpha = 255.0
        self.gravity = gravity
        self.drag = drag
        self.tail_len = tail_len

    def update(self):
        self.vx *= self.drag
        self.vy = (self.vy * self.drag) + self.gravity
        self.x += self.vx
        self.y += self.vy
        self.alpha -= self.decay
        self.radius = max(0.8, self.radius * 0.985)
        return self.alpha > 0

    def draw(self, surface):
        if self.alpha <= 0:
            return
        head_x, head_y = int(self.x), int(self.y)
        tail_x = int(self.x - self.vx * self.tail_len)
        tail_y = int(self.y - self.vy * self.tail_len)

        # Draw directly on the additive target surface (No per-spark new surfaces)
        thick = max(1, int(self.radius))
        pygame.draw.line(surface, self.color, (tail_x, tail_y), (head_x, head_y), thick)
        pygame.draw.line(surface, (255, 255, 230), 
                         (int(tail_x * 0.5 + head_x * 0.5), int(tail_y * 0.5 + head_y * 0.5)), 
                         (head_x, head_y), max(1, thick - 1))

# ---------------------------------------------------------
# CRACKER MANAGER
# ---------------------------------------------------------
class CrackerSystem:
    def __init__(self):
        self.active_crackers = []
        self.sparks = []
        self.smoke = []
        self.light_sources = []
        self.screen_shake = 0.0
        self.flash_alpha = 0.0
        # Dedicated additive layer reused across frames
        self.spark_layer = pygame.Surface((WIDTH, HEIGHT))

    def add_spark(self, spark):
        if len(self.sparks) < 900:  # Protect FPS from overloading
            self.sparks.append(spark)

    def add_smoke(self, smk):
        if len(self.smoke) < 120:
            self.smoke.append(smk)

    def trigger_shake(self, amount):
        self.screen_shake = max(self.screen_shake, amount)

    def trigger_flash(self, intensity=160.0):
        self.flash_alpha = max(self.flash_alpha, intensity)

    def add_light(self, x, y, radius, color, intensity=1.0):
        self.light_sources.append((x, y, radius, color, intensity))

    def update_and_draw(self, surface):
        self.light_sources.clear()

        # 1. Update & draw smoke layer
        for smk in self.smoke[:]:
            if not smk.update():
                self.smoke.remove(smk)
            else:
                smk.draw(surface)

        # 2. Update crackers
        for cracker in self.active_crackers[:]:
            if not cracker.update(self):
                self.active_crackers.remove(cracker)
            else:
                cracker.draw(surface)

        # 3. Dynamic Bloom / Ground reflections
        for lx, ly, lrad, lcol, lint in self.light_sources:
            glow = get_glow_surface(lrad * lint, lcol)
            surface.blit(glow, (lx - lrad * lint, ly - lrad * lint), special_flags=pygame.BLEND_ADD)
            if ly > GROUND_Y - 180:
                refl_h = int(24 * lint)
                refl_w = int(lrad * 1.2 * lint)
                refl_surf = pygame.Surface((refl_w, refl_h), pygame.SRCALPHA)
                pygame.draw.ellipse(refl_surf, (*lcol, int(min(60, 40 * lint))), (0, 0, refl_w, refl_h))
                surface.blit(refl_surf, (lx - refl_w // 2, GROUND_Y - 4), special_flags=pygame.BLEND_ADD)

        # 4. Fast additive spark rendering
        self.spark_layer.fill((0, 0, 0))
        for p in self.sparks[:]:
            if not p.update():
                self.sparks.remove(p)
            else:
                p.draw(self.spark_layer)
        surface.blit(self.spark_layer, (0, 0), special_flags=pygame.BLEND_ADD)

        if self.screen_shake > 0:
            self.screen_shake -= 0.6
        if self.flash_alpha > 0:
            self.flash_alpha -= 9.0

# ---------------------------------------------------------
# CRACKERS (ANAAR, CHAKRI, ROCKET, SKYSHOT, LADI, SUTLI)
# ---------------------------------------------------------
class Anaar:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.timer = 0
        self.duration = 190
        SOUND_SIZZLE.play(-1, maxtime=3000)

    def update(self, manager):
        self.timer += 1
        prog = self.timer / self.duration
        intensity = math.sin(prog * math.pi) ** 1.3
        
        manager.add_light(self.x, self.y - 35, radius=140 * intensity + 30, color=(255, 140, 40), intensity=intensity * 1.4)

        if self.timer % 3 == 0:
            manager.add_smoke(SmokePuff(self.x + random.uniform(-3, 3), self.y - 25, random.uniform(-0.6, 0.6), random.uniform(-2.0, -3.5)))

        spark_count = int(12 * intensity) + 2
        for _ in range(spark_count):
            angle = random.uniform(-0.35, 0.35) - math.pi / 2
            speed = random.uniform(9.0, 20.0) * (0.4 + 0.6 * intensity)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            col = random.choice([(255, 255, 210), (255, 200, 70), (255, 130, 30)])
            manager.add_spark(SparkStreak(self.x, self.y - 25, vx, vy, col, random.uniform(2.0, 3.5), random.uniform(5.0, 8.0), gravity=0.26))

        if self.timer % 15 == 0 and random.random() < 0.4:
            SOUND_SNAP.play()

        return self.timer < self.duration

    def draw(self, surface):
        pts = [(self.x, self.y - 25), (self.x - 16, self.y), (self.x + 16, self.y)]
        pygame.draw.polygon(surface, (160, 65, 30), pts)
        pygame.draw.polygon(surface, (210, 110, 50), pts, 2)
        pygame.draw.circle(surface, (255, 255, 220), (int(self.x), int(self.y - 25)), 4)


class Chakri:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.angle = 0.0
        self.timer = 0
        self.duration = 240
        SOUND_WHISTLE.play()

    def update(self, manager):
        self.timer += 1
        self.angle += 0.52
        self.x += math.sin(self.timer * 0.09) * 0.8

        manager.add_light(self.x, self.y, radius=110, color=(255, 170, 50), intensity=1.1)

        if self.timer % 4 == 0:
            manager.add_smoke(SmokePuff(self.x, self.y, random.uniform(-0.4, 0.4), -0.4, 6))

        for offset in [0, math.pi]:
            fire_angle = self.angle + offset
            speed = random.uniform(7.0, 14.0)
            vx = math.cos(fire_angle) * speed
            vy = (math.sin(fire_angle) * speed) * 0.35
            col = random.choice([(255, 240, 170), (255, 170, 40), (255, 90, 20)])
            manager.add_spark(SparkStreak(self.x, self.y, vx, vy, col, random.uniform(2.0, 3.0), random.uniform(6, 10), gravity=0.06))

        if self.timer % 28 == 0:
            SOUND_SNAP.play()

        return self.timer < self.duration

    def draw(self, surface):
        pygame.draw.circle(surface, (130, 120, 105), (int(self.x), int(self.y)), 10)
        pygame.draw.circle(surface, (255, 210, 60), (int(self.x), int(self.y)), 4)


class Rocket:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vy = -16.0
        self.vx = random.uniform(-0.8, 0.8)
        self.exploded = False
        SOUND_WHISTLE.play()

    def update(self, manager):
        if not self.exploded:
            self.x += self.vx
            self.y += self.vy
            self.vy += 0.18

            manager.add_light(self.x, self.y, radius=55, color=(255, 180, 70), intensity=0.9)
            if random.random() < 0.6:
                manager.add_smoke(SmokePuff(self.x, self.y + 10, random.uniform(-0.3, 0.3), random.uniform(1.0, 2.5), initial_radius=5))

            manager.add_spark(SparkStreak(self.x, self.y + 6, random.uniform(-0.5, 0.5), random.uniform(2.5, 5.0), (255, 200, 80), 2.0, decay=20, gravity=0.02))

            if self.vy >= -1.0 or self.y <= 150:
                self.explode(manager)
                return False
            return True
        return False

    def explode(self, manager):
        self.exploded = True
        SOUND_POP.play()
        manager.trigger_shake(5.0)
        manager.trigger_flash(80.0)

        theme_color = random.choice([(255, 60, 60), (60, 255, 100), (80, 170, 255), (255, 220, 50), (250, 90, 240)])
        for _ in range(85):
            theta = random.uniform(0, 2 * math.pi)
            spd = random.uniform(2.5, 10.0)
            manager.add_spark(SparkStreak(self.x, self.y, math.cos(theta) * spd, math.sin(theta) * spd, theme_color, random.uniform(2.2, 3.8), random.uniform(3.0, 5.2), gravity=0.11))

    def draw(self, surface):
        if not self.exploded:
            pygame.draw.line(surface, (160, 130, 80), (self.x, self.y), (self.x, self.y + 24), 2)
            pygame.draw.rect(surface, (220, 35, 35), (self.x - 3, self.y - 8, 6, 12))


class SkyShot:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vy = -19.5
        self.target_y = random.uniform(100, 160)
        SOUND_POP.play()

    def update(self, manager):
        self.y += self.vy
        self.vy *= 0.985

        manager.add_light(self.x, self.y, radius=45, color=(255, 220, 170), intensity=0.8)
        manager.add_spark(SparkStreak(self.x, self.y, random.uniform(-0.3, 0.3), random.uniform(1.0, 2.5), (255, 220, 160), 2.0, decay=22, gravity=0.01))

        if self.vy >= -2.0 or self.y <= self.target_y:
            self.explode(manager)
            return False
        return True

    def explode(self, manager):
        SOUND_BOOM.play()
        manager.trigger_shake(15.0)
        manager.trigger_flash(180.0)

        outer_color = random.choice([(255, 215, 0), (255, 50, 110), (0, 255, 210), (180, 80, 255)])
        
        for _ in range(8):
            manager.add_smoke(SmokePuff(self.x + random.uniform(-15, 15), self.y + random.uniform(-15, 15), random.uniform(-0.8, 0.8), random.uniform(-0.4, 0.4), initial_radius=18))

        # Outer Canopy
        for _ in range(130):
            theta = random.uniform(0, 2 * math.pi)
            spd = random.uniform(3.5, 12.5)
            manager.add_spark(SparkStreak(self.x, self.y, math.cos(theta) * spd, math.sin(theta) * spd, outer_color, random.uniform(2.8, 4.2), random.uniform(2.2, 3.8), gravity=0.075))

        # Core
        for _ in range(40):
            theta = random.uniform(0, 2 * math.pi)
            spd = random.uniform(1.0, 4.5)
            manager.add_spark(SparkStreak(self.x, self.y, math.cos(theta) * spd, math.sin(theta) * spd, (255, 255, 240), 2.2, random.uniform(3.5, 5.5), gravity=0.05))

    def draw(self, surface):
        pygame.draw.circle(surface, (255, 240, 200), (int(self.x), int(self.y)), 4)


class Ladi:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.total_shots = 32
        self.current_shot = 0
        self.counter = 0

    def update(self, manager):
        self.counter += 1
        if self.counter >= 3:
            self.counter = 0
            self.current_shot += 1
            SOUND_SNAP.play()

            burst_x = self.x + random.uniform(-18, 18)
            burst_y = self.y - self.current_shot * 3.2

            manager.add_light(burst_x, burst_y, radius=75, color=(255, 190, 90), intensity=1.0)
            if random.random() < 0.6:
                manager.add_smoke(SmokePuff(burst_x, burst_y, random.uniform(-0.8, 0.8), random.uniform(-0.8, -2.0), initial_radius=8))

            for _ in range(10):
                spd = random.uniform(2, 6)
                ang = random.uniform(0, 2 * math.pi)
                manager.add_spark(SparkStreak(burst_x, burst_y, math.cos(ang) * spd, math.sin(ang) * spd, (255, 220, 130), 2.0, decay=20, gravity=0.18))

            for _ in range(3):
                manager.add_spark(SparkStreak(burst_x, burst_y, random.uniform(-3, 3), random.uniform(-4, -1), (200, 30, 30), 2.5, decay=8, gravity=0.22, tail_len=0.8))

        return self.current_shot < self.total_shots

    def draw(self, surface):
        remaining = self.total_shots - self.current_shot
        if remaining > 0:
            top_y = self.y - self.total_shots * 3.2
            bot_y = self.y - self.current_shot * 3.2
            pygame.draw.line(surface, (180, 25, 25), (self.x, top_y), (self.x, bot_y), 4)


class SutliBomb:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.fuse_timer = 90
        self.exploded = False

    def update(self, manager):
        if not self.exploded:
            self.fuse_timer -= 1
            fuse_x = self.x
            fuse_y = self.y - 16

            manager.add_light(fuse_x, fuse_y, radius=30, color=(255, 190, 50), intensity=0.7)
            manager.add_spark(SparkStreak(fuse_x, fuse_y, random.uniform(-1, 1), random.uniform(-2, -0.2), (255, 210, 60), 1.8, decay=26, gravity=0.06))

            if self.fuse_timer % 15 == 0:
                SOUND_SIZZLE.play(maxtime=140)

            if self.fuse_timer <= 0:
                self.explode(manager)
                return False
            return True
        return False

    def explode(self, manager):
        self.exploded = True
        SOUND_BOOM.play()
        manager.trigger_shake(20.0)
        manager.trigger_flash(220.0)

        for _ in range(10):
            manager.add_smoke(SmokePuff(self.x + random.uniform(-12, 12), self.y - random.uniform(4, 20), random.uniform(-2, 2), random.uniform(-0.8, -3), initial_radius=16))

        for _ in range(70):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(3, 14)
            manager.add_spark(SparkStreak(self.x, self.y - 6, math.cos(ang) * spd, math.sin(ang) * spd, (255, 235, 170), random.uniform(3.0, 5.5), random.uniform(7, 12), gravity=0.21))

        for _ in range(35):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(2, 8)
            manager.add_spark(SparkStreak(self.x, self.y - 6, math.cos(ang) * spd, math.sin(ang) * spd, (60, 130, 60), 3.0, random.uniform(4, 7), gravity=0.24, tail_len=1.0))

    def draw(self, surface):
        if not self.exploded:
            rect = pygame.Rect(self.x - 14, self.y - 14, 28, 24)
            pygame.draw.rect(surface, (45, 110, 50), rect, border_radius=4)
            pygame.draw.line(surface, (180, 165, 110), (self.x - 14, self.y - 2), (self.x + 14, self.y - 2), 2)
            pygame.draw.line(surface, (180, 165, 110), (self.x, self.y - 14), (self.x, self.y + 10), 2)
            pygame.draw.line(surface, (120, 120, 120), (self.x, self.y - 14), (self.x, self.y - 18), 2)

# ---------------------------------------------------------
# DIWALI ENVIRONMENT
# ---------------------------------------------------------
class Environment:
    def __init__(self, width, height, ground_y):
        self.width = width
        self.height = height
        self.ground_y = ground_y
        self.stars = [(random.randint(0, width), random.randint(0, ground_y - 120), random.uniform(0.6, 2.0)) for _ in range(120)]
        self.diyas = [130, 310, 550, 790, 970]

    def draw(self, surface):
        # Sky background
        for y in range(0, self.height, 4):
            ratio = y / self.height
            c = (int(5 + 16 * ratio), int(5 + 14 * ratio), int(18 + 36 * ratio))
            pygame.draw.rect(surface, c, (0, y, self.width, 4))

        time_ms = pygame.time.get_ticks()
        for sx, sy, srad in self.stars:
            twinkle = abs(math.sin(time_ms * 0.002 + sx))
            pygame.draw.circle(surface, (int(190 + 65 * twinkle), int(190 + 65 * twinkle), 255), (sx, sy), max(1, int(srad)))

        # Skyline silhouette
        skyline_pts = [
            (0, self.ground_y),
            (60, self.ground_y - 50), (95, self.ground_y - 95), (130, self.ground_y - 50),
            (210, self.ground_y - 50), (245, self.ground_y - 120), (280, self.ground_y - 50),
            (460, self.ground_y - 50), (495, self.ground_y - 85), (540, self.ground_y - 50),
            (740, self.ground_y - 50), (775, self.ground_y - 130), (810, self.ground_y - 50),
            (950, self.ground_y - 50), (990, self.ground_y - 100), (1030, self.ground_y - 50),
            (self.width, self.ground_y)
        ]
        pygame.draw.polygon(surface, (12, 15, 28), skyline_pts)

        # Ground
        pygame.draw.rect(surface, (18, 14, 15), (0, self.ground_y, self.width, self.height - self.ground_y))
        pygame.draw.line(surface, (70, 45, 38), (0, self.ground_y), (self.width, self.ground_y), 2)

        # Diyas
        for dx in self.diyas:
            dy = self.ground_y + 18
            flicker = math.sin(time_ms * 0.016 + dx) * 2.5
            glow_surf = get_glow_surface(36, (255, 140, 30))
            surface.blit(glow_surf, (dx - 36, dy - 36), special_flags=pygame.BLEND_ADD)
            pygame.draw.arc(surface, (180, 80, 30), (dx - 13, dy - 7, 26, 14), math.pi, 2 * math.pi, 4)
            pygame.draw.polygon(surface, (255, 175, 20), [(dx, dy - 15 + flicker), (dx - 5, dy - 4), (dx + 5, dy - 4)])
            pygame.draw.polygon(surface, (255, 255, 210), [(dx, dy - 10 + flicker), (dx - 2, dy - 4), (dx + 2, dy - 4)])

# ---------------------------------------------------------
# MAIN APPLICATION LOOP
# ---------------------------------------------------------
def main():
    env = Environment(WIDTH, HEIGHT, GROUND_Y)
    manager = CrackerSystem()
    font = pygame.font.SysFont("Arial", 15, bold=True)
    title_font = pygame.font.SysFont("Arial", 22, bold=True)

    controls = [
        ("A", "Anaar (Flower Pot)"),
        ("C", "Chakri (Spinner)"),
        ("R", "Rocket"),
        ("S", "Sky Shot (Mortar)"),
        ("L", "Ladi (Chain)"),
        ("B", "Sutli Bomb"),
        ("SPACE", "Mega Barrage"),
    ]

    running = True
    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_a:
                    manager.active_crackers.append(Anaar(random.randint(220, WIDTH - 220), GROUND_Y))
                elif event.key == pygame.K_c:
                    manager.active_crackers.append(Chakri(random.randint(240, WIDTH - 240), GROUND_Y + 4))
                elif event.key == pygame.K_r:
                    manager.active_crackers.append(Rocket(random.randint(180, WIDTH - 180), GROUND_Y))
                elif event.key == pygame.K_s:
                    manager.active_crackers.append(SkyShot(random.randint(240, WIDTH - 240), GROUND_Y))
                elif event.key == pygame.K_l:
                    manager.active_crackers.append(Ladi(random.randint(240, WIDTH - 240), GROUND_Y))
                elif event.key == pygame.K_b:
                    manager.active_crackers.append(SutliBomb(random.randint(220, WIDTH - 220), GROUND_Y))
                elif event.key == pygame.K_SPACE:
                    manager.active_crackers.append(Anaar(240, GROUND_Y))
                    manager.active_crackers.append(Chakri(WIDTH // 2, GROUND_Y + 4))
                    manager.active_crackers.append(SkyShot(WIDTH // 2 - 140, GROUND_Y))
                    manager.active_crackers.append(Rocket(WIDTH // 2 + 140, GROUND_Y))
                    manager.active_crackers.append(SutliBomb(WIDTH - 260, GROUND_Y))

        # 1. Environment backdrop
        env.draw(screen)

        # 2. Camera shake offset
        shake_x = random.uniform(-manager.screen_shake, manager.screen_shake) if manager.screen_shake > 0 else 0
        shake_y = random.uniform(-manager.screen_shake, manager.screen_shake) if manager.screen_shake > 0 else 0

        # 3. Cracker simulation & particles
        canvas = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        manager.update_and_draw(canvas)
        screen.blit(canvas, (shake_x, shake_y))

        # 4. Detonation lens flash
        if manager.flash_alpha > 0:
            flash_surf = pygame.Surface((WIDTH, HEIGHT))
            flash_surf.fill((255, 245, 230))
            flash_surf.set_alpha(int(min(255, manager.flash_alpha)))
            screen.blit(flash_surf, (0, 0), special_flags=pygame.BLEND_ADD)

        # 5. UI Overlay
        title_surf = title_font.render("SHUBH DIWALI - REALISTIC FIREWORKS ENGINE", True, (255, 215, 120))
        screen.blit(title_surf, (22, 18))

        curr_x = 22
        for key_char, label in controls:
            k_tag = font.render(f"[{key_char}]", True, (255, 225, 75))
            l_tag = font.render(f" {label}   ", True, (215, 215, 215))
            screen.blit(k_tag, (curr_x, 50))
            curr_x += k_tag.get_width()
            screen.blit(l_tag, (curr_x, 50))
            curr_x += l_tag.get_width()

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()