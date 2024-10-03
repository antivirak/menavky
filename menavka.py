# @author Jaroslav Cerman; June 2024

import itertools
import math
import random
from functools import lru_cache
from itertools import dropwhile
from time import sleep
from typing import Generator, Iterator

import numpy as np
import pygame
from PIL import Image

from mol2geom import mol2geom

EXTENSION = 'png'
FPS = 48
CARD_SIZE = 80
ROTATE_SPEED = .02
SCALE = 18
width = 800
height = 800
# TODO maybe thicker lines?

with open("molfiles/Bn_boc_ser.mol") as f:
    _ = dropwhile(lambda x: 'V2000' not in x, f.readlines())
cube_points, bonds, atoms = mol2geom(list(_))
projection_matrix = np.array(
    [[1, 0, 0],
     [0, 1, 0],
     [0, 0, 0]]
)
atoms_to_color = {
    'C': (255, 255, 255),
    'H': (0, 0, 0),
    'O': (255, 0, 0),
    'N': (0, 0, 255),
    'Cl': (0, 255, 0),
    'F': (0, 255, 255),
    'Br': (255, 0, 255),
    'I': (255, 255, 0),
}


# class RectWithCache(pygame.Rect):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.full_image = None


class RectWithCache:
    def __init__(self, rect: pygame.Rect, full_img) -> None:
        self.rect = rect
        self.full_image = full_img


class Config:
    """
    Game configuration - could be in separate module / json
    """
    # pylint: disable=too-few-public-methods
    # pylint: disable=use-dict-literal
    def __init__(self) -> None:
        # card counts
        self.cards = dict(
            red_stripe_1=2,
            red_stripe_2=2,
            red_dot_1=2,
            red_dot_2=2,
            blue_stripe_1=2,
            blue_stripe_2=2,
            blue_dot_1=2,
            blue_dot_2=2,

            ventilation=3,
            eyes_mutation=1,
            stripes_mutation=1,
            colors_mutation=1,
            blue_lab=1,
            red_lab=1,
            yellow_lab=1,
            # shower=0,  # TODO need to decide if the shower counts as mutation - and if not, if it resets mutation count
        )

        # die
        self.labs_dice = (
            ('white', 'blue'),
            ('white', 'red'),
            ('white', 'yellow'),
            ('black', 'blue'),
            ('black', 'red'),
            ('black', 'yellow'),
        )
        self.eyes_dice = (1, 1, 1, 2, 2, 2)
        self.stripes_dice = (1, 1, 1, 2, 2, 2)
        self.colors_dice = (1, 1, 1, 2, 2, 2)

        self.eyes_map = {1: '1', 2: '2'}
        self.stripes_map = {1: 'stripe', 2: 'dot'}
        self.colors_map = {1: 'red', 2: 'blue'}


class UserInterface:
    def __init__(self):
        border = 2
        self.width = width
        self.height = height
        self.background = (214, 188, 155)  # (255, 255, 255)
        self.img = pygame.display.set_mode((width + (2 * border), height + (2 * border)))
        self.img.fill(self.background)
        self.transparent_layer = None
        self.angle_x = 0
        self.angle_y = 0
        self.angle_z = 0

    def arrange_images_in_circle(self, imagesToArrange: list) -> Iterator[tuple[RectWithCache, pygame.Surface]]:
        # pylint: disable=invalid-name
        imgWidth = self.width
        imgHeight = self.height

        # we want the circle to be as large as possible.
        # but the circle shouldn't extend all the way to the edge of the image.
        # If we do that, then when we paste images onto the circle,
        # those images will partially fall over the edge.
        # so we reduce the diameter of the circle by the width/height of the widest/tallest image.
        diameter = min(
            imgWidth  - CARD_SIZE,
            imgHeight - CARD_SIZE,
        )
        radius = diameter / 2

        circleCenterX = imgWidth // 2
        circleCenterY = imgHeight // 2
        theta = 2 * math.pi / len(imagesToArrange)

        for i, curImg in enumerate(imagesToArrange):
            angle = i * theta
            dx = int(radius * math.cos(angle))
            dy = int(radius * math.sin(angle))

            # dx and dy give the coordinates of where the center of our images would go.
            # So we must subtract half the height/width of the image
            # to find where their top-left corners should be.
            # size = curImg.get_size()
            size = (CARD_SIZE, CARD_SIZE)
            pos = (
                circleCenterX + dx - size[0] // 2,
                circleCenterY + dy - size[1] // 2,
            )
            original_size = curImg.size
            shorter_side = min(original_size)
            original_size = (shorter_side, shorter_side)
            rot = (
                curImg
                .resize(original_size)  # TODO crop would be better
                .rotate(-angle / math.pi * 180 - 90, expand=True)
            )

            scale = rot.size[1] / original_size[1]
            new_image = pygame.transform.smoothscale(
                pygame.image.fromstring(rot.tobytes(), rot.size, rot.mode),
                (CARD_SIZE * scale, CARD_SIZE * scale),
            )

            rect = new_image.get_rect()
            rect.update(*pos, *size)
            # rect.full_image = curImg
            # drawing the rotated rectangle to the screen
            self.blit(new_image, pos)
            yield (
                RectWithCache(rect, pygame.image.fromstring(curImg.tobytes(), curImg.size, curImg.mode)),
                new_image,
            )

    def show(self, cards, direction):
        cards_to_show = list(reversed(cards)) if direction == 'black' else cards
        images = [
            Image
            .open(f'menavky/{filename}.{EXTENSION}')
            .convert('RGBA') for filename in cards_to_show
        ]

        self.obj_map = list(zip(list(self.arrange_images_in_circle(images)), cards_to_show))
        self.update_transparent_layer()

    def blit(self, surface, pos) -> pygame.Rect:
        return self.img.blit(surface, pos)

    def update_transparent_layer(self):
        self.transparent_layer = self.img.copy()

    def reset_img(self):
        self.blit(self.transparent_layer, (0, 0))

    def update_color(self, rectangle, img):
        # pylint: disable=invalid-name
        w, h = img.get_size()
        new_img = img.copy()
        for x, y in itertools.product(range(w), range(h)):
            r, g, b, a = new_img.get_at((x, y))
            new_img.set_at((x, y), pygame.Color(r // 2, g, b, a))
        self.blit(new_img, rectangle)

    def zoom_hovered(self, rectangle_wc: RectWithCache) -> pygame.Surface:
        rectangle = rectangle_wc.rect
        current_screen = self.img.copy()
        rectangle = rectangle.move(
            (self.width  // 3 - rectangle.x) // 2,
            (self.height // 3 - rectangle.y) // 2,
        )

        rotation_x = np.array([
            [1, 0, 0],
            [0, math.cos(self.angle_x), -math.sin(self.angle_x)],
            [0, math.sin(self.angle_x), math.cos(self.angle_x)]]
        )
        rotation_y = np.array([
            [math.cos(self.angle_y), 0, math.sin(self.angle_y)],
            [0, 1, 0],
            [-math.sin(self.angle_y), 0, math.cos(self.angle_y)]]
        )
        rotation_z = np.array([
            [math.cos(self.angle_z), -math.sin(self.angle_z), 0],
            [math.sin(self.angle_z), math.cos(self.angle_z), 0],
            [0, 0, 1]]
        )

        points = np.zeros((len(cube_points), 2))
        surf = pygame.Surface((rectangle.w * 2, rectangle.h * 2))
        for i, point in enumerate(cube_points):
            rotate_x = np.matmul(rotation_x, point)
            rotate_y = np.matmul(rotation_y, rotate_x)
            rotate_z = np.matmul(rotation_z, rotate_y)
            point_2d = np.matmul(projection_matrix, rotate_z)

            x = (point_2d[0] * SCALE) + CARD_SIZE
            y = (point_2d[1] * SCALE) + CARD_SIZE

            points[i] = (x, y)
            pygame.draw.circle(surf, atoms_to_color[atoms[i]], (x, y), 5)
        for bond in bonds:
            pygame.draw.line(
                surf,
                (255, 255, 255),
                (points[bond[0]][0], points[bond[0]][1]), (points[bond[1]][0], points[bond[1]][1]),
                width=(bond[2] - 1) * 4 + 1,  # not possible for .aaline()
            )
        self.blit(surf, rectangle)

        self.angle_y -= ROTATE_SPEED

        #pygame.display.update(rectangle)
        return current_screen, surf

    @staticmethod
    @lru_cache()
    def image_load(fname):
        return pygame.image.load(f'menavky/{fname}')


class Field:
    def __init__(self, config: Config, ui: UserInterface, animation: bool = True) -> None:
        self.animation = animation
        self.cards_static = [card for card, count in config.cards.items() for _ in range(count)]
        self.cards = None
        self.direction = ''
        self.ui = ui
        self.next_count = 0
        self.current_card_filename = ''

    def __len__(self):
        return len(self.cards_static)

    def __next__(self, visible: bool = True):
        if not visible:
            if self.direction == 'black':
                self.next_count -= 1
            else:
                self.next_count += 1
            return next(self.cards)
        w = self.ui.width
        h = self.ui.height
        angle = 2 * math.pi / len(self) * (self.next_count - (
            1 if self.direction == 'black' else 0
        ))
        shape = [(w // 2, h // 2), (w // 2 + 400 * math.cos(angle),
                                    h // 2 + 400 * math.sin(angle))]

        if self.animation:
            self.ui.reset_img()
            center_image = pygame.transform.smoothscale(
                self.ui.image_load(self.current_card_filename),
                (CARD_SIZE * 1.5, CARD_SIZE * 1.5),
            )
            self.ui.blit(center_image, ((w // 2) - 40, (h // 2) - 40))

            pygame.draw.line(self.ui.img, (0, 0, 0), *shape)  # TODO dependency injection?
            pygame.display.flip()
            sleep(.55)  # pygame.time.wait?
        if self.direction == 'black':
            self.next_count -= 1
        else:
            self.next_count += 1
        return next(self.cards)

    def next_invisible(self):
        return self.__next__(visible=False)  # pylint: disable=unnecessary-dunder-call

    def create(self, start: str, direction: str):
        self.direction = direction
        self.cards_static.remove(start)
        self.shuffle()
        self.cards_static.insert(0, start)
        self.cards = itertools.cycle(self.cards_static)  # TODO or shuffle and then while loop on cycle?
        self.ui.show(self.cards_static, direction)
        return self

    def shuffle(self):
        random.shuffle(self.cards_static)  # mutates the list :(

    def cycle_to_start(self, start_lab: str, direction: str):
        if self.direction != direction:
            self.direction = direction
            self.cards_static.reverse()
            self.cards = itertools.cycle(self.cards_static)
            self.next_count = 0
        card = ''
        while card != start_lab:
            card = self.next_invisible()

    def show_throw(self, card: str, labs: tuple[str, str]):
        self.ui.reset_img()
        w = self.ui.width
        h = self.ui.height
        direction, lab = labs

        center_image = pygame.transform.smoothscale(
            self.ui.image_load(f'{card}.png'),
            (CARD_SIZE * 1.5, CARD_SIZE * 1.5),
        )
        self.ui.blit(
            center_image,
            ((w // 2) - CARD_SIZE * 1.5 / 2, (h // 2) - CARD_SIZE / 2 - CARD_SIZE),
        )
        center_image = pygame.transform.smoothscale(
            self.ui.image_load(f'{lab}_lab.png'),
            (CARD_SIZE, CARD_SIZE),
        )
        self.ui.blit(center_image, ((w // 2) - CARD_SIZE / 2, (h // 2) + CARD_SIZE / 2))

        h_offset = w // 2 - 30
        v_offset = 100
        scale = .2
        # Big curly arrow instead?
        # Generate arrow on the fly or have png?
        if direction == 'white':
            color = (255, 255, 255)
            coordinates = (
                (h_offset + scale *   0, v_offset + scale * 100),  # noqa: E222
                (h_offset + scale *   0, v_offset + scale * 200),  # noqa: E222
                (h_offset + scale * 250, v_offset + scale * 200),  # noqa: E222
                (h_offset + scale * 250, v_offset + scale * 300),  # noqa: E222
                (h_offset + scale * 350, v_offset + scale * 150),  # noqa: E222
                (h_offset + scale * 250, v_offset + scale *   0),  # noqa: E222
                (h_offset + scale * 250, v_offset + scale * 100),  # noqa: E222
            )
        elif direction == 'black':
            color = (0, 0, 0)
            coordinates = (
                (h_offset + scale * (350 -   0), v_offset + scale * 100),  # noqa: E222
                (h_offset + scale * (350 -   0), v_offset + scale * 200),  # noqa: E222
                (h_offset + scale * (350 - 250), v_offset + scale * 200),  # noqa: E222
                (h_offset + scale * (350 - 250), v_offset + scale * 300),  # noqa: E222
                (h_offset + scale * (350 - 350), v_offset + scale * 150),  # noqa: E222
                (h_offset + scale * (350 - 250), v_offset + scale *   0),  # noqa: E222
                (h_offset + scale * (350 - 250), v_offset + scale * 100),  # noqa: E222
            )
        else:
            raise ValueError('Invalid direction provided')
        pygame.draw.polygon(self.ui.img, color, coordinates)
        pygame.display.flip()


class Game:
    def __init__(self, config: Config, field: Field) -> None:
        self.config = config
        self.throw_dice()
        self.field = field.create(f'{self.labs[1]}_lab', self.labs[0])  # TODO allow manual; and from photo
        self.field_len = len(self.field)

    def set_init_dice_vals(self):
        self.labs = self.init_labs
        self.eyes = self.init_eyes
        self.stripes = self.init_stripes
        self.colors = self.init_colors

    def throw_dice(self) -> None:
        # pylint: disable=attribute-defined-outside-init
        self.init_labs = random.choice(self.config.labs_dice)
        self.init_eyes = random.choice(self.config.eyes_dice)
        self.init_stripes = random.choice(self.config.stripes_dice)
        self.init_colors = random.choice(self.config.colors_dice)
        self.set_init_dice_vals()
        self.print_dice()

    def print_dice(self) -> None:
        attrnames = {
            'labs': lambda x: x,
            'eyes': lambda x: self.config.eyes_map[x],
            'stripes': lambda x: self.config.stripes_map[x],
            'colors': lambda x: self.config.colors_map[x],
        }
        for attrname, _map in attrnames.items():
            print(f'{attrname}: {_map(getattr(self, attrname))}')

    def _throw_manual(self) -> None:
        for attrname in ('labs', 'eyes', 'stripes', 'colors'):
            if attrname == 'labs':
                value2 = input(f'Enter {attrname} die value (red / blue / yellow): ').strip()
                assert value2 in ('red', 'blue', 'yellow'), f'Invalid value {value2}; has to be red, blue or yellow'
                # TODO exit gracefully
                value1 = input(f'Enter {attrname} die value (black / white) arrow: ').strip()
                assert value1 in ('black', 'white'), f'Invalid value {value1}; has to be black or white'
                value = (value1, value2)
                setattr(self, attrname, value)
            else:
                quality1 = 'stripes' if 'stripes' in attrname else 'red'
                quality2 = 'dots' if 'stripes' in attrname else 'blue'
                val = input(f'Enter {attrname} die value ({quality1} = 1, {quality2} = 2): ')
                assert val in (1, 2), f'Invalid value {val}; has to be 1 or 2'
                setattr(self, attrname, val)

    def run(self) -> Generator[str, None, None]:
        if not self.field.animation:
            self.field.show_throw(
                f'{self.config.colors_map[self.colors]}_{self.config.stripes_map[self.stripes]}_{self.eyes}',
                self.labs,
            )
        count = 0
        while True:
            # count = self.game_loop(count) - save 1 indentation level
            card_to_find = f'{self.config.colors_map[self.colors]}_{self.config.stripes_map[self.stripes]}_{self.eyes}'
            self.field.current_card_filename = f'{card_to_find}.{EXTENSION}'
            # self.field is not-exhaustable generator
            card = next(self.field)  # pylint: disable=stop-iteration-return
            if card == 'ventilation':
                card = self.field.next_invisible()
                while card != 'ventilation':
                    card = self.field.next_invisible()
                continue
            if card == 'eyes_mutation':
                self.eyes = 2 if self.eyes == 1 else 1
            elif card == 'stripes_mutation':
                self.stripes = 2 if self.stripes == 1 else 1
            elif card == 'colors_mutation':
                self.colors = 2 if self.colors == 1 else 1
            elif card == 'shower':
                pass
            if card.endswith('_mutation'):
                if count == 3:
                    # mněňavka dies
                    yield card
                count += 1
                continue
            # Construct the wanted card name
            card_to_find = f'{self.config.colors_map[self.colors]}_{self.config.stripes_map[self.stripes]}_{self.eyes}'
            if card == card_to_find:
                yield card  # TODO there are more instances of each card
            yield ''  # TODO decouple the computation from visualisation

    def run_again(self) -> Generator[str, None, None]:
        self.throw_dice()
        self.field.cycle_to_start(f'{self.labs[1]}_lab', self.labs[0])
        return self.run()

    def replay_correct(self):
        self.field.cycle_to_start(f'{self.labs[1]}_lab', self.labs[0])
        self.set_init_dice_vals()
        assert not self.field.animation
        self.field.animation = True
        cards = self.run()
        while not next(cards):  # bump generator until it returns value
            pass  # itertools.dropwhile?
        self.field.animation = False


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Find the amino acid!")

    config = Config()
    ui = UserInterface()
    animation = False
    game = Game(config, Field(config, ui, animation=animation))
    cards = game.run()
    card = None

    done = False
    clock = pygame.time.Clock()

    # basicfont = pygame.font.SysFont(None, 32)

    hovered = None
    last_hovered = None
    current_screen = None
    while not done:
        if not card:
            card = next(cards)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True

            for (button_rect_wc, img), fname in ui.obj_map:
                button_rect = button_rect_wc.rect
                if button_rect.collidepoint(pygame.mouse.get_pos()):
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        game.field.ui.update_color(button_rect, img)
                        # save the change in color to current_screen
                        current_screen, surf = game.field.ui.zoom_hovered(button_rect_wc)
                        if fname == card:
                            print('Correct!')
                            if not animation:
                                game.replay_correct()
                            cards = game.run_again()
                            card = None
                            current_screen = None
                        break

                    #if hovered is not None and hovered != img:
                    #    game.field.ui.blit(current_screen, (0, 0))

                    screen, surf = game.field.ui.zoom_hovered(button_rect_wc)
                    current_screen = current_screen or screen
                    last_hovered = hovered
                    hovered = img
                    break
        if hovered is not None:
            if button_rect.collidepoint(pygame.mouse.get_pos()):
                screen = game.field.ui.zoom_hovered(button_rect_wc)
                current_screen = current_screen or screen
                #game.field.ui.blit(surf, (0, 0))
            else:
                if current_screen is not None:
                    game.field.ui.blit(current_screen, (0, 0))
                hovered = None

        pygame.display.flip()
        clock.tick(FPS)

    # while input('Run again with the same field? (Or type q to quit) ') != 'q':
    #     print(game.run_again())


if __name__ == '__main__':
    # TODO write tests
    main()
