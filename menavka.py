# @author Jaroslav Cerman; June 2024

import itertools
import math
import random
import sys
from collections.abc import Generator, Iterator
from functools import lru_cache
from time import sleep

import numpy as np
import pygame
from PIL import Image

from mol2geom import mol2geom

FNAME_MAP = {
    'blue_stripe_1': 'Bn_boc_gly',
    'red_stripe_1': 'Bn_boc_ser',
    'blue_dot_1': 'Bn_gly',
    'red_dot_1': 'Bn_ser',
    'blue_stripe_2': 'Boc_gly',
    'red_stripe_2': 'Boc_ser',
    'blue_dot_2': 'gly',
    'red_dot_2': 'ser',
}
EXTENSION = 'png'
FPS = 48
CARD_SIZE = 80
ROTATE_SPEED = .02
SCALE = 18
width = 800
height = 800


class RectWithCache:
    """
    Pygame rectangle with more attributes: full_image (static), molecule to be shown (animated)
    """
    def __init__(
        self,
        rect: pygame.Rect,
        full_img: pygame.Surface,
        mol: tuple[np.ndarray, np.ndarray, dict[int, str]],  # could have made Mol class, this type is crazy :)
    ) -> None:
        self.rect = rect
        self.full_image = full_img
        self.matrix, self.bonds, self.atoms = mol


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
    """
    Encapsulates the UI elements and logic
    """
    def __init__(self):
        """Initialize the ui objects"""
        border = 2
        self.width = width
        self.height = height
        self.background = (214, 188, 155)
        self.img = pygame.display.set_mode((width + (2 * border), height + (2 * border)))
        self.img.fill(self.background)
        self.transparent_layer = None
        self.obj_map: list[tuple[Iterator[tuple[RectWithCache, pygame.Surface]]], str] = []
        self.angle_x = 0
        self.angle_y = 0
        self.angle_z = 0
        self.projection_matrix = np.array(
            [[1, 0, 0],
             [0, 1, 0],
             [0, 0, 0]]
        )
        self.atoms_to_color = {
            'C': (255, 255, 255),
            'H': (0, 0, 0),
            'O': (255, 0, 0),
            'N': (0, 0, 255),
            'Cl': (0, 255, 0),
            'F': (0, 255, 255),
            'Br': (255, 0, 255),
            'I': (255, 255, 0),
        }

    def arrange_images_in_circle(
        self, imagesToArrange: list[tuple[Image.Image, tuple[np.ndarray, np.ndarray, dict[int, str]]]],
    ) -> Iterator[tuple[RectWithCache, pygame.Surface]]:
        """Deal the cards in a circle"""
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

        for i, (curImg, mol) in enumerate(imagesToArrange):
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
                RectWithCache(
                    rect,
                    pygame.image.fromstring(curImg.tobytes(), curImg.size, curImg.mode),
                    mol,
                ),
                new_image,
            )

    def show(self, cards: list[str], direction: str):
        """Load the images and molecules from HDD"""
        cards_to_show = list(reversed(cards)) if direction == 'black' else cards
        images = [
            (
                Image
                .open(f'menavky/{filename}.{EXTENSION}')
                .convert('RGBA'),
                load_molecule(f'molfiles/{FNAME_MAP.get(filename, "not_found")}.mol'),
            ) for filename in cards_to_show
        ]

        self.obj_map = list(zip(list(self.arrange_images_in_circle(images)), cards_to_show))
        self.update_transparent_layer()

    def blit(self, surface: pygame.Surface, pos) -> pygame.Rect:
        """'partial' evaluation of pygame.Surface.blit"""
        return self.img.blit(surface, pos)

    def update_transparent_layer(self) -> None:
        self.transparent_layer = self.img.copy()

    def reset_img(self) -> None:
        self.blit(self.transparent_layer, (0, 0))

    def update_color(self, rectangle: pygame.Rect, img: pygame.Surface) -> None:
        """
        Make the card blue-ish after clicking on it.
        It will show user that the card was already clicked.
        """
        # pylint: disable=invalid-name
        w, h = img.get_size()
        new_img = img.copy()
        for x, y in itertools.product(range(w), range(h)):
            r, g, b, a = new_img.get_at((x, y))
            new_img.set_at((x, y), pygame.Color(r // 2, g, b, a))
        self.blit(new_img, rectangle)
        # recolor the rectangle in the same frame
        pygame.display.update(rectangle)

    def zoom_hovered(self, rectangle_wc: RectWithCache) -> pygame.Surface:
        """
        Define logic for zooming in on hovered card.
        The card can just be shown bigger or an animation of 3D molecule can be projected.
        """
        rectangle = rectangle_wc.rect
        current_screen = self.img.copy()
        rectangle = rectangle.move(
            (self.width  // 3 - rectangle.x) // 2,
            (self.height // 3 - rectangle.y) // 2,
        )

        # we only rotate around y-axis
        # rotation_x = np.array([
        #     [1, 0, 0],
        #     [0, math.cos(self.angle_x), -math.sin(self.angle_x)],
        #     [0, math.sin(self.angle_x), math.cos(self.angle_x)]]
        # )
        rotation_y = np.array([
            [math.cos(self.angle_y), 0, math.sin(self.angle_y)],
            [0, 1, 0],
            [-math.sin(self.angle_y), 0, math.cos(self.angle_y)]]
        )
        # rotation_z = np.array([
        #     [math.cos(self.angle_z), -math.sin(self.angle_z), 0],
        #     [math.sin(self.angle_z), math.cos(self.angle_z), 0],
        #     [0, 0, 1]]
        # )

        points = np.zeros((len(rectangle_wc.matrix), 2))
        surf = pygame.Surface((rectangle.w * 2, rectangle.h * 2))
        for i, point in enumerate(rectangle_wc.matrix):
            # rotate_x = np.matmul(rotation_x, point)
            # rotate_y = np.matmul(rotation_y, rotate_x)
            # rotate_z = np.matmul(rotation_z, rotate_y)
            # point_2d = np.matmul(self.projection_matrix, rotate_z)
            rotate_y = np.matmul(rotation_y, point)
            point_2d = np.matmul(self.projection_matrix, rotate_y)

            x = (point_2d[0] * SCALE) + CARD_SIZE
            y = (point_2d[1] * SCALE) + CARD_SIZE

            points[i] = (x, y)
            pygame.draw.circle(surf, self.atoms_to_color[rectangle_wc.atoms[i]], (x, y), 5)
        for bond in rectangle_wc.bonds:
            pygame.draw.line(
                surf,
                (255, 255, 255),
                (points[bond[0]][0], points[bond[0]][1]), (points[bond[1]][0], points[bond[1]][1]),
                width=(bond[2] - 1) * 4 + 1,  # not possible for .aaline()
            )
        if len(rectangle_wc.atoms) == 1 or ZOOM_ONLY:
            # I could also show the image rotated, but this is better
            self.blit(pygame.transform.smoothscale(
                rectangle_wc.full_image, (CARD_SIZE * 2, CARD_SIZE * 2),
            ), rectangle)
        else:
            self.blit(surf, rectangle)
            self.angle_y -= ROTATE_SPEED
        rectangle.h = rectangle.h * 2  # not sure why

        pygame.display.update(rectangle)
        return current_screen

    @staticmethod
    @lru_cache()
    def image_load(fname: str) -> pygame.Surface:
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

    def __len__(self) -> int:
        return len(self.cards_static)

    def __next__(self, visible: bool = True) -> str:
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

            pygame.draw.aaline(self.ui.img, (0, 0, 0), *shape)  # TODO dependency injection?
            pygame.display.flip()
            sleep(.55)  # pygame.time.wait?
        if self.direction == 'black':
            self.next_count -= 1
        else:
            self.next_count += 1
        return next(self.cards)

    def next_invisible(self) -> str:
        return self.__next__(visible=False)  # pylint: disable=unnecessary-dunder-call

    def create(self, start: str, direction: str) -> 'Field':
        self.direction = direction
        self.cards_static.remove(start)
        self.shuffle()
        self.cards_static.insert(0, start)
        self.cards = itertools.cycle(self.cards_static)  # TODO or shuffle and then while loop on cycle?
        self.ui.show(self.cards_static, direction)
        return self

    def shuffle(self) -> None:
        random.shuffle(self.cards_static)  # mutates the list :(

    def cycle_to_start(self, start_lab: str, direction: str) -> None:
        if self.direction != direction:
            self.direction = direction
            self.cards_static.reverse()
            self.cards = itertools.cycle(self.cards_static)
            self.next_count = 0
        card = ''
        while card != start_lab:
            card = self.next_invisible()

    def show_throw(self, card: str, labs: tuple[str, str]) -> None:
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
        # pylint: disable=attribute-defined-outside-init
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
        """Option to throw the dice manually and input the values. Not used now."""
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
                assert val in ('1', '2'), f'Invalid value {val}; has to be 1 or 2'
                setattr(self, attrname, int(val))

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

    def replay_correct(self) -> None:
        self.field.cycle_to_start(f'{self.labs[1]}_lab', self.labs[0])
        self.set_init_dice_vals()
        assert not self.field.animation
        self.field.animation = True
        cards = self.run()
        while not next(cards):  # bump generator until it returns value
            pass  # itertools.dropwhile?
        self.field.animation = False


def load_molecule(fname: str) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    """
    Return molecule 3D coordinates, adjacency matrix (with bond multiplicity)
    and atom index - element symbol mapping
    """
    if 'not_found' in fname:
        return np.zeros((0, 0)), np.zeros((0, 0)), {1: 'H'}

    with open(fname) as f:
        mol = itertools.dropwhile(lambda x: 'V2000' not in x, f.readlines())
    matrix, bonds, atoms = mol2geom(list(mol))

    return matrix, bonds, atoms


def game_loop(
    cards, card, hovered, last_hovered, current_screen, button_rect_wc, button_rect, ui, game,
    done=False,
) -> tuple:
    if not card:
        card = next(cards)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            done = True
        for (button_rect_wc, img), fname in ui.obj_map:  # pylint: disable=redefined-argument-from-local
            button_rect = button_rect_wc.rect
            if not button_rect.collidepoint(pygame.mouse.get_pos()):
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.field.ui.blit(current_screen, (0, 0))
                game.field.ui.update_color(button_rect, img)
                # save the change in color to current_screen
                current_screen = game.field.ui.zoom_hovered(button_rect_wc)
                if fname == card:
                    print('Correct!')
                    if not game.field.animation:
                        game.replay_correct()
                    game.field.ui.blit(current_screen, (0, 0))
                    cards = game.run_again()
                    card = None
                    current_screen = None
                break

            if current_screen is None:
                # do this only one time, so the zoom_hovered is not called multiple times
                screen = game.field.ui.zoom_hovered(button_rect_wc)
            current_screen = current_screen or screen
            last_hovered = hovered
            hovered = img
            break

    if hovered is not None:
        if button_rect.collidepoint(pygame.mouse.get_pos()) and (
            last_hovered is None or last_hovered == hovered
        ):
            # I need to use last_hovered to prevent artefacts from appearing
            # if the mouse is moved quickly between cards (hovered is not None between)
            game.field.ui.zoom_hovered(button_rect_wc)  # here we cannot assign current_screen
        else:
            if current_screen is not None:
                game.field.ui.blit(current_screen, (0, 0))
            hovered = None
            last_hovered = None

            pygame.display.flip()

    return done, cards, card, hovered, last_hovered, current_screen, button_rect_wc


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Find the amino acid!")

    config = Config()
    ui = UserInterface()
    game = Game(config, Field(config, ui, animation=False))
    cards = game.run()

    clock = pygame.time.Clock()

    # basicfont = pygame.font.SysFont(None, 32)

    done = False
    card = None
    hovered = None
    last_hovered = None
    current_screen = None
    button_rect_wc = RectWithCache(
        pygame.Rect(0, 0, 0, 0), None, (np.zeros((0, 0)), np.zeros((0, 0)), {1: 'H'}),
    )
    while not done:
        done, cards, card, hovered, last_hovered, current_screen, button_rect_wc = game_loop(
            cards, card, hovered, last_hovered, current_screen, button_rect_wc,
            button_rect_wc.rect, ui, game,
        )
        clock.tick(FPS)


if __name__ == '__main__':
    # TODO write tests
    ZOOM_ONLY = len(sys.argv) > 1 and '-z' in sys.argv[1]
    main()
