"""Entry point for Dungeon Survivor."""

import pygame


WINDOW_WIDTH = 960
WINDOW_HEIGHT = 640
WINDOW_TITLE = "Dungeon Survivor"
FPS = 60
BACKGROUND_COLOR = (24, 27, 35)


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill(BACKGROUND_COLOR)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
