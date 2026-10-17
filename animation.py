"""Load and play animated GIF sprites in pygame"""

import pygame
from PIL import Image, ImageSequence

class AnimatedGif:
    def __init__(self, path, size=None, loop=True):
        self.frames = []
        self.durations = []
        self.loop = loop
        self.frame_index = 0
        self.elapsed = 0.0
        self.finished = False

        with Image.open(path) as gif:
            for image_frame in ImageSequence.Iterator(gif):
                rgba_frame = image_frame.convert("RGBA")
                frame_size = rgba_frame.size

                surface = pygame.image.fromstring(
                    rgba_frame.tobytes(),
                    frame_size,
                    "RGBA",
                )

                if size is not None:
                    surface = pygame.transform.scale(surface, size)

                self.frames.append(surface)

                duration_ms = image_frame.info.get(
                    "duration",
                    gif.info.get("duration", 100),
                )
                self.durations.append(max(duration_ms/1000, 0.04))

        if not self.frames:
            raise ValueError(f"The GIF contains no frames: {path}")

    def reset(self):
        self.frame_index = 0
        self.elapsed = 0.0
        self.finished = False

    def update(self, delta_seconds):
        if self.finished or len(self.frames) == 1:
            return

        self.elapsed += delta_seconds

        while self.elapsed >= self.durations[self.frame_index]:
            self.elapsed -= self.durations[self.frame_index]

            if self.frame_index == len(self.frames) -1:
                if self.loop:
                    self.frame_index = 0
                else:
                    self.frame_index = len(self.frames) -1
                    self.elapsed = 0.0
                    self.finished = True
                    break

            else:
                self.frame_index += 1

    def draw(self, surface, center):
        frame = self.frames[self.frame_index]
        destination = frame.get_rect(center=center)
        surface.blit(frame, destination)