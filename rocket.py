import math
import random
import sys
import numpy as np
import pygame

# ==============================================================================
# CONFIGURATION & SETTINGS
# ==============================================================================
# Increased window resolution
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
FPS = 60

# Slower, more gradual rocket launch speed
ROCKET_MIN_SPEED = 4.5
ROCKET_MAX_SPEED = 6.5

# Physics
GRAVITY = 0.12            # Downward pull on explosion sparks
AIR_RESISTANCE = 0.96     # Friction that gently slows sparks over time
PARTICLE_COUNT = 90       # Number of sparks created per firework burst

# Bright firework color palette (R, G, B)
PALETTE = [
    (255, 60, 60),    # Bright Ruby Red
    (255, 215, 0),    # Shimmering Gold
    (50, 255, 120),   # Emerald Green
    (40, 180, 255),   # Electric Blue
    (255, 105, 180),  # Neon Pink
    (190, 70, 255),   # Radiant Violet
    (255, 140, 20),   # Warm Orange
    (0, 255, 230),    # Bright Cyan
]


# ==============================================================================
# SOUND GENERATION (Synthesized via NumPy)
# ==============================================================================
def create_whoosh_sound():
    """Generates an ascending whoosh/hiss sound using noise and frequency sweeps."""
    sample_rate = 44100
    duration = 0.85
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)

    # Filtered noise for air friction sound
    raw_noise = np.random.uniform(-1, 1, num_samples)
    kernel_size = 11
    smooth_noise = np.convolve(raw_noise, np.ones(kernel_size) / kernel_size, mode="same")

    # Upward whistle sweep
    sweep_freq = np.linspace(300, 750, num_samples)
    whistle = np.sin(2 * np.pi * sweep_freq * t) * 0.3

    # Envelope: smooth climb and decay
    envelope = np.sin(np.pi * (t / duration) ** 0.5) * np.exp(-t * 1.2)
    signal = (smooth_noise * 0.7 + whistle) * envelope

    audio_data = (np.clip(signal, -1.0, 1.0) * 32767).astype(np.int16)
    stereo_data = np.ascontiguousarray(np.column_stack((audio_data, audio_data)))
    return pygame.sndarray.make_sound(stereo_data)


def create_boom_sound():
    """Generates a deep explosion boom with low punch and decaying rumble."""
    sample_rate = 44100
    duration = 1.1
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)

    # Low-frequency punch
    punch_freq = np.linspace(110, 30, num_samples)
    punch = np.sin(2 * np.pi * punch_freq * t) * np.exp(-t * 6.0)

    # Low rumble decay
    raw_noise = np.random.uniform(-1, 1, num_samples)
    kernel_size = 18
    rumble = np.convolve(raw_noise, np.ones(kernel_size) / kernel_size, mode="same")
    rumble = rumble * np.exp(-t * 3.8)

    signal = punch * 0.75 + rumble * 0.8
    audio_data = (np.clip(signal, -1.0, 1.0) * 32767).astype(np.int16)
    stereo_data = np.ascontiguousarray(np.column_stack((audio_data, audio_data)))
    return pygame.sndarray.make_sound(stereo_data)


# ==============================================================================
# PARTICLE CLASS
# ==============================================================================
class Particle:
    """Represents an individual glowing spark."""
    def __init__(self, x, y, color, vx, vy, radius=3, fade_rate=4.0, has_gravity=True):
        self.x = float(x)
        self.y = float(y)
        self.color = color
        self.vx = float(vx)
        self.vy = float(vy)
        self.radius = radius
        self.alpha = 255.0
        self.fade_rate = fade_rate
        self.has_gravity = has_gravity

    def update(self):
        self.x += self.vx
        self.y += self.vy

        self.vx *= AIR_RESISTANCE
        self.vy *= AIR_RESISTANCE

        if self.has_gravity:
            self.vy += GRAVITY

        self.alpha -= self.fade_rate

    def is_alive(self):
        return self.alpha > 0

    def draw(self, surface):
        current_alpha = max(0, int(self.alpha))
        size = self.radius * 6
        glow_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2

        # Outer soft glow
        outer_alpha = int(current_alpha * 0.35)
        pygame.draw.circle(glow_surface, (*self.color, outer_alpha), (center, center), self.radius * 2)

        # Colored body
        pygame.draw.circle(glow_surface, (*self.color, current_alpha), (center, center), self.radius)

        # White core hot spot
        pygame.draw.circle(glow_surface, (255, 255, 255, current_alpha), (center, center), max(1, self.radius // 2))

        surface.blit(
            glow_surface,
            (int(self.x) - center, int(self.y) - center),
            special_flags=pygame.BLEND_ADD
        )


# ==============================================================================
# ROCKET CLASS
# ==============================================================================
class Rocket:
    """Represents the ascending rocket."""
    def __init__(self, whoosh_sound, boom_sound):
        self.x = random.randint(150, WINDOW_WIDTH - 150)
        self.y = float(WINDOW_HEIGHT)
        # Detonation height adjusted for the larger window
        self.target_y = random.randint(160, 380)
        self.speed = random.uniform(ROCKET_MIN_SPEED, ROCKET_MAX_SPEED)
        self.color = random.choice(PALETTE)
        self.is_alive = True

        self.boom_sound = boom_sound
        whoosh_sound.play()

    def update(self, particles):
        self.y -= self.speed

        # Trailing sparks under the rocket
        for _ in range(2):
            spark_vx = random.uniform(-0.5, 0.5)
            spark_vy = random.uniform(0.8, 2.2)
            spark_color = (255, random.randint(180, 240), 90)
            particles.append(
                Particle(
                    x=self.x,
                    y=self.y,
                    color=spark_color,
                    vx=spark_vx,
                    vy=spark_vy,
                    radius=2,
                    fade_rate=9.0,
                    has_gravity=False
                )
            )

        if self.y <= self.target_y:
            self.explode(particles)

    def explode(self, particles):
        self.is_alive = False
        self.boom_sound.play()

        # Radial spark burst
        for _ in range(PARTICLE_COUNT):
            angle = random.uniform(0, 2 * math.pi)
            velocity = random.uniform(2.0, 7.5)
            vx = math.cos(angle) * velocity
            vy = math.sin(angle) * velocity
            particle_size = random.choice([2, 3, 3, 4])
            fade_rate = random.uniform(2.0, 4.0)

            particles.append(
                Particle(
                    x=self.x,
                    y=self.y,
                    color=self.color,
                    vx=vx,
                    vy=vy,
                    radius=particle_size,
                    fade_rate=fade_rate,
                    has_gravity=True
                )
            )

    def draw(self, surface):
        glow_size = 18
        glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        center = glow_size // 2

        pygame.draw.circle(glow_surf, (*self.color, 120), (center, center), 8)
        pygame.draw.circle(glow_surf, (255, 255, 255, 255), (center, center), 3)

        surface.blit(
            glow_surf,
            (int(self.x) - center, int(self.y) - center),
            special_flags=pygame.BLEND_ADD
        )


# ==============================================================================
# MAIN LOOP
# ==============================================================================
def main():
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.init()

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Firework Rocket Simulation")
    clock = pygame.time.Clock()

    whoosh_sound = create_whoosh_sound()
    boom_sound = create_boom_sound()

    # Night sky stars distributed across the 1200x800 area
    stars = [
        (random.randint(0, WINDOW_WIDTH), random.randint(0, WINDOW_HEIGHT), random.randint(1, 2))
        for _ in range(120)
    ]

    font = pygame.font.SysFont("Helvetica", 22)
    instruction_surf = font.render("Press ENTER to launch a rocket", True, (190, 200, 220))
    instruction_rect = instruction_surf.get_rect(center=(WINDOW_WIDTH // 2, 40))

    rockets = []
    particles = []

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    rockets.append(Rocket(whoosh_sound, boom_sound))
                elif event.key == pygame.K_ESCAPE:
                    running = False

        # Update rocket & spark states
        for rocket in rockets:
            rocket.update(particles)
        for particle in particles:
            particle.update()

        # Clean up finished entities
        rockets = [r for r in rockets if r.is_alive]
        particles = [p for p in particles if p.is_alive()]

        # Draw deep dark night sky (no screen flash tint)
        screen.fill((10, 12, 22))

        # Draw static stars
        for sx, sy, s_rad in stars:
            pygame.draw.circle(screen, (150, 160, 180), (sx, sy), s_rad)

        # Draw fireworks
        for particle in particles:
            particle.draw(screen)
        for rocket in rockets:
            rocket.draw(screen)

        # Draw instructions text
        screen.blit(instruction_surf, instruction_rect)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()