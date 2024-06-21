# @author Jaroslav Cerman; June 2024

import itertools
import math
import random
from functools import lru_cache
from time import sleep
from typing import Generator

import pygame  # pygame==2.5.2
from PIL import Image  # pillow==10.3.0

EXTENSION = 'png'
FPS = 24
width = 800
height = 800


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
        # self.img = Image.new("RGB", (self.width, self.height), self.background)
        self.img = pygame.display.set_mode((width + (2 * border), height + (2 * border)))
        self.img.fill(self.background)
        # transparent_layer = pygame.Surface((width + (2 * border), height + (2 * border)), pygame.SRCALPHA)
        self.transparent_layer = None  # self.img.copy()  # transparent_layer.convert_alpha()

    def arrange_images_in_circle(self, imagesToArrange: list) -> Generator[pygame.Rect, None, None]:
        # pylint: disable=invalid-name
        # masterImage = self.img
        imgWidth = self.width
        imgHeight = self.height

        # we want the circle to be as large as possible.
        # but the circle shouldn't extend all the way to the edge of the image.
        # If we do that, then when we paste images onto the circle,
        # those images will partially fall over the edge.
        # so we reduce the diameter of the circle by the width/height of the widest/tallest image.
        diameter = min(
            imgWidth  - max(img.size[0] for img in imagesToArrange),
            imgHeight - max(img.size[1] for img in imagesToArrange)
        )
        radius = diameter / 2

        circleCenterX = imgWidth // 2
        circleCenterY = imgHeight // 2
        theta = 2 * math.pi / len(imagesToArrange)

        for i, curImg in enumerate(imagesToArrange):
            # button_surface = curImg  # pygame.Surface((80, 80))
            angle = i * theta
            dx = int(radius * math.cos(angle))
            dy = int(radius * math.sin(angle))

            # dx and dy give the coordinates of where the center of our images would go.
            # So we must subtract half the height/width of the image
            # to find where their top-left corners should be.
            # size = curImg.get_size()
            size = curImg.size
            pos = (
                circleCenterX + dx - size[0] // 2,
                circleCenterY + dy - size[1] // 2
            )
            rot = curImg.rotate(-angle / math.pi * 180 - 90, expand=True)

            new_image = pygame.image.fromstring(rot.tobytes(), rot.size, rot.mode)
            rect = new_image.get_rect()
            rect.update(*pos, 80, 80)  # TODO 80 as global var
            # drawing the rotated rectangle to the screen
            self.blit(new_image, pos)
            yield rect

    def show(self, cards, direction):
        cards_to_show = reversed(cards) if direction == 'black' else cards
        images = [
            Image
            .open(f'menavky/{filename}.{EXTENSION}')
            .convert('RGBA') for filename in cards_to_show
        ]  # .resize((80, 80))
        self.obj_map = list(zip(list(self.arrange_images_in_circle(images)), cards_to_show))
        self.update_transparent_layer()

    def blit(self, surface, pos):
        self.img.blit(surface, pos)

    def update_transparent_layer(self):
        self.transparent_layer = self.img.copy()

    def reset_img(self):
        self.blit(self.transparent_layer, (0, 0))

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
        self.next_count = -1
        self.current_card_filename = ''

    def __len__(self):
        return len(self.cards_static)

    def __next__(self, visible: bool = True):
        self.next_count += 1
        if not visible:
            return next(self.cards)
        w = self.ui.width
        h = self.ui.height
        angle = 2 * math.pi / len(self) * (self.next_count * (
            -1 if self.direction == 'black' else 1
        ) - (1 if self.direction == 'black' else 0))
        shape = [(w // 2, h // 2), (w // 2 + 400 * math.cos(angle),
                                    h // 2 + 400 * math.sin(angle))]

        if self.animation:
            self.ui.reset_img()
            center_image = self.ui.image_load(self.current_card_filename)
            self.ui.blit(center_image, ((w // 2) - 40, (h // 2) - 40))

            pygame.draw.line(self.ui.img, (0, 0, 0), *shape)  # TODO dependency injection?
            # img.show()
            pygame.display.flip()
            sleep(.55)  # pygame.time.wait?
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
        self.direction = direction  # TODO when changing direction, the animation breaks
        card = ''
        while card != start_lab:
            card = self.next_invisible()

    def show_throw(self, card: str, labs: tuple[str, str]):
        self.ui.reset_img()
        w = self.ui.width
        h = self.ui.height
        direction, lab = labs
        # self.current_card_filename = 
        center_image = self.ui.image_load(f'{card}.png')  # self.current_card_filename
        self.ui.blit(center_image, ((w // 2) - 40, (h // 2) - 40 - 80))
        center_image = self.ui.image_load(f'{lab}_lab.png')
        self.ui.blit(center_image, ((w // 2) - 40, (h // 2) + 40))

        # center_image = self.ui.image_load(f'{lab}_lab.png')  # TODO big curly arrow?
        h_offset = w // 2 - 30
        v_offset = 100
        scale = .2
        # surf = pygame.Surface((w, h))
        if direction == 'white':
            color = (255, 255, 255)
            coordinates = (
                (h_offset + scale *   0, v_offset + scale * 100),
                (h_offset + scale *   0, v_offset + scale * 200),
                (h_offset + scale * 250, v_offset + scale * 200),
                (h_offset + scale * 250, v_offset + scale * 300),
                (h_offset + scale * 350, v_offset + scale * 150),
                (h_offset + scale * 250, v_offset + scale *   0),
                (h_offset + scale * 250, v_offset + scale * 100),
            )
        elif direction == 'black':
            color = (0, 0, 0)
            coordinates = (
                (h_offset + scale * (350 -   0), v_offset + scale * 100),
                (h_offset + scale * (350 -   0), v_offset + scale * 200),
                (h_offset + scale * (350 - 250), v_offset + scale * 200),
                (h_offset + scale * (350 - 250), v_offset + scale * 300),
                (h_offset + scale * (350 - 350), v_offset + scale * 150),
                (h_offset + scale * (350 - 250), v_offset + scale *   0),
                (h_offset + scale * (350 - 250), v_offset + scale * 100),
            )
        else:
            raise ValueError('Invalid direction provided')
        pygame.draw.polygon(
            self.ui.img,
            # ((w // 2) - 40, (h // 2) + 40),
            color, coordinates,
        )
        # pygame.transform.scale_by(surf, .5)
        # Generate arrow on the fly or have png? Start with big narrow arrow with neutral background and correct direction color
        # self.ui.blit(center_image, ((w // 2) - 40, (h // 2) + 40))
        # self.ui.blit(surf, (0, 0))
        pygame.display.flip()


class Game:
    def __init__(self, config: Config, field: Field) -> None:
        self.config = config
        self.throw_dice()
        self.field = field.create(f'{self.labs[1]}_lab', self.labs[0])  # TODO allow manual; and from photo
        self.field_len = len(self.field)

    def throw_dice(self) -> None:
        # pylint: disable=attribute-defined-outside-init
        self.labs = random.choice(self.config.labs_dice)
        self.eyes = random.choice(self.config.eyes_dice)
        self.stripes = random.choice(self.config.stripes_dice)
        self.colors = random.choice(self.config.colors_dice)
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

    def throw_manual(self) -> None:
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
            # card = self.field.next_with_state(card_to_find)
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
        # self.field.cycle_to_start(f'{self.labs[1]}_lab', self.labs[0])
        self.field.cycle_to_start(f'{self.labs[1]}_lab', self.labs[0])
        return self.run()


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Mněňavky")

    config = Config()
    ui = UserInterface()
    game = Game(config, Field(config, ui, animation=False))
    cards = game.run()
    card = None

    done = False
    clock = pygame.time.Clock()

    # basicfont = pygame.font.SysFont(None, 32)

    while not done:
        if not card:
            card = next(cards)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for button_rect, fname in ui.obj_map:
                    if button_rect.collidepoint(event.pos):
                        print(fname)
                        if fname == card:
                            print('Correct!')
                            cards = game.run_again()
                            card = None

        pygame.display.flip()
        clock.tick(FPS)

    # while input('Run again with the same field? (Or type q to quit) ') != 'q':
    #     print(game.run_again())


if __name__ == '__main__':
    # TODO write tests
    main()
