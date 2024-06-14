# @author Jaroslav Cerman; June 2024

import itertools
import math
import random
from time import sleep

from PIL import Image, ImageDraw  # pillow==10.3.0

EXTENSION = 'png'


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
        self.width = 900
        self.height = 900
        self.img = Image.new("RGB", (self.width, self.height), (214, 188, 155))

    def arrange_images_in_circle(self, imagesToArrange: list[Image.Image]):
        # TODO rotate cards themselfs or just mirror the labs that are on bottom half
        # pylint: disable=invalid-name
        masterImage = self.img
        imgWidth, imgHeight = masterImage.size

        # we want the circle to be as large as possible.
        # but the circle shouldn't extend all the way to the edge of the image.
        # If we do that, then when we paste images onto the circle, those images will partially fall over the edge.
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
            angle = i * theta
            dx = int(radius * math.cos(angle))
            dy = int(radius * math.sin(angle))

            # dx and dy give the coordinates of where the center of our images would go.
            # So we must subtract half the height/width of the image to find where their top-left corners should be.
            pos = (
                circleCenterX + dx - curImg.size[0] // 2,
                circleCenterY + dy - curImg.size[1] // 2
            )
            masterImage.paste(curImg, pos)

    def show(self, cards, direction):
        cards_to_show = reversed(cards) if direction == 'black' else cards
        images = [Image.open(f'menavky/{filename}.{EXTENSION}') for filename in cards_to_show]  # .resize((80, 80))
        self.arrange_images_in_circle(images)


class Field:
    def __init__(self, config: Config, ui: UserInterface) -> None:
        self.cards_static = [card for card, count in config.cards.items() for _ in range(count)]
        self.cards = None
        self.direction = ''
        self.ui = ui
        self.next_count = -1

    def __len__(self):
        return len(self.cards_static)

    def __next__(self, visible=True):
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
        # creating new Image object
        img = self.ui.img.copy()
        # create line image
        img1 = ImageDraw.Draw(img)
        img1.line(shape, fill='black', width=0)
        # TODO show the current wanted card in the middle
        # filename = 'colors_mutation'
        # img.paste(Image.open(f'menavky/{filename}.{EXTENSION}'), (w // 2, h // 2))
        img.show()
        sleep(.55)
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

    def cycle_to_start(self, start: str, direction):
        if direction != self.direction:
            self.cards_static = list(reversed(self.cards_static))
            self.direction = direction
            self.cards = itertools.cycle(self.cards_static)
        while next(self) != start:
            next(self)


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
            else:
                quality1 = 'stripes' if 'stripes' in attrname else 'red'
                quality2 = 'dots' if 'stripes' in attrname else 'blue'
                value = input(f'Enter {attrname} die value ({quality1} = 1, {quality2} = 2): ')
                assert value in (1, 2), f'Invalid value {value}; has to be 1 or 2'
            setattr(self, attrname, value)

    def _prepare(self):
        """This is to prepare ventilation map for teleportation - but it will be better solved by while not next vent loop"""
        vent_map = {}
        last_vent = ''
        for count in range(self.field_len):
            card = next(self.field)
            if card != 'ventilation':
                continue
            if last_vent:
                vent_map[last_vent] = count
                last_vent = ''
            else:
                last_vent = count
        return vent_map

    def run(self) -> str:
        count = 0
        while True:
            # count = self.game_loop(count) - save 1 indentation level
            card = next(self.field)
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
                    return card
                count += 1
                continue
            # Construct the wanted card name
            card_to_find = f'{self.config.colors_map[self.colors]}_{self.config.stripes_map[self.stripes]}_{self.eyes}'
            if card == card_to_find:
                return card  # TODO there are more instances of each card

    def run_again(self) -> str:
        self.throw_dice()
        self.field.cycle_to_start(f'{self.labs[1]}_lab', self.labs[0])
        return self.run()


def main() -> None:
    config = Config()
    ui = UserInterface()
    game = Game(config, Field(config, ui))
    print(game.run())
    while input('Run again with the same field? (Or type q to quit) ') != 'q':
        print(game.run_again())


if __name__ == '__main__':
    # TODO write tests
    main()
