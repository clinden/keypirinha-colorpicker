import keypirinha as kp
import keypirinha_util as kpu
from colorsys import rgb_to_hls, rgb_to_hsv
from time import sleep
from uuid import uuid4
from ctypes import windll, Structure, c_long, byref

class ColorPicker(kp.Plugin):
    DEFAULT_ITEM_LABEL = 'Color pick:'
    PACKAGE_COMMAND = kp.ItemCategory.USER_BASE + 1

    def __init__(self):
        super().__init__()

        self._item_label   = self.DEFAULT_ITEM_LABEL
        self._item_icon    = None
        self._preview_icon = None

        self._conversionMode = {
            'hex': 'Convert to hexadecimal',
            'rgb': 'Convert to RGB',
            'cmyk': 'Convert to CMYK',
            'hsv': 'Convert to HSV',
            'hsl': 'Convert to HSL'
        }

    def __del__(self):
        self._cleanup(full=True)

    def on_events(self, flags):
        """Reloads the package config when its changed
        """
        if flags & kp.Events.PACKCONFIG:
            self._read_config()

    def _read_config(self):
        settings = self.load_settings()

        self._item_label = settings.get('item_label', 'main', self.DEFAULT_ITEM_LABEL)

    def on_start(self):
        self._read_config()

        self._item_icon = self.load_icon('res://{}/colorpicker.ico'.format(self.package_full_name()))

    def on_catalog(self):
        """Adds the color pick command to the catalog
        """
        self.set_catalog([
            self.create_item(
                category=kp.ItemCategory.KEYWORD,
                label=self._item_label,
                short_desc='Pick a color from the screen',
                target='picker',
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.KEEPALL,
                icon_handle=self._item_icon
            )
        ])

    def on_deactivated(self):
        """Cleans up preview icon when Keypirinha Box is closed
        """
        self._cleanup(full=False)

    def _cleanup(self, full=False):
        if full and self._item_icon is not None: self._item_icon.free()

        if self._preview_icon is not None: self._preview_icon.free()

    def _generateIcon(self, rgb):
        """Generates ico file containing the picked color
        """
        with open('{}/preview.ico'.format(self.get_package_cache_path(True)), 'wb') as f:
            header = [0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x10, 0x10, 0x00, 0x00, 0x01, 0x00, 0x20, 0x00, 0x68, 0x04, 0x00, 0x00, 0x16, 0x00, 0x00, 0x00, 0x28, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x01, 0x00, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x13, 0x0b, 0x00, 0x00, 0x13, 0x0b, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,]
            data = [hx for r in range(256) for hx in [rgb[2], rgb[1], rgb[0], 255]]
            footer = [0x00 for i in range(64)]

            f.write(bytearray(header + data + footer))

        self._preview_icon = self.load_icon('cache://{}/preview.ico'.format(self.package_full_name()), force_reload=True)

    def _generateActions(self, rgb):
        """Generates suggestions list
        """
        self._actions = []

        for conversion, label in self._conversionMode.items():
            color_code = self._convertRgbTo(rgb, conversion)

            self._actions.append(
                self.create_item(
                    category=kp.ItemCategory.USER_BASE + 1,
                    label=label,
                    short_desc='Copy ' + color_code + ' to clipboard',
                    target=conversion,
                    icon_handle=self._preview_icon,
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.IGNORE,
                    data_bag=color_code
                )
            )

    def _convertRgbTo(self, rgb, to):
        """Converts an rgb code to another format
        Supported format: hex, cmyk, rgb, hsv, hls
        """
        def clamp(x): 
            return max(0, min(x, 255))

        def rgb_to_cmyk(rgb):
            if rgb == (0, 0, 0):
                return 0, 0, 0, 100
            
            cmy = tuple(map(lambda x: 1 - x / 255, rgb))
            
            min_cmy = min(cmy)
            return tuple(map(lambda x: ((x - min_cmy) / (1 - min_cmy))*100, cmy)) + (min_cmy*100,)

        if to == 'hex':
            return '#{0:02x}{1:02x}{2:02x}'.format(*map(clamp, rgb))
        elif to == 'rgb':
            return ', '.join(map(str, map(clamp, rgb)))
        elif to == 'cmyk':
            cmyk = rgb_to_cmyk(tuple(map(clamp, rgb)))
            return '{0:.0f}%, {1:.0f}%, {2:.0f}%, {3:.0f}%'.format(*cmyk)
        elif to == 'hsv':
            hsv = rgb_to_hsv(*map(lambda x: x/255., rgb))
            return f'{round(hsv[0]*360)}°, {round(hsv[1]*100)}%, {round(hsv[2]*100)}%'
        elif to == 'hsl':
            hls = rgb_to_hls(*map(lambda x: x/255., rgb))
            return f'{round(hls[0]*360)}°, {round(hls[2]*100)}%, {round(hls[1]*100)}%'

    def on_suggest(self, user_input, items_chain):
        """Sets the list of possible conversion as suggestions
        """
        if not items_chain:
            return

        rgb = self._getPixelColor()

        self._generateIcon(rgb)

        self._generateActions(rgb)

        self.set_suggestions(
            self._actions,
            kp.Match.FUZZY,
            kp.Sort.NONE
        )

    def on_execute(self, item, action):
        """Copies color code of selected suggestion
        """
        kpu.set_clipboard(item.data_bag())

    def _getCursorPos(self):
        """Returns mouse pointer position (x, y)
        """
        pt = Point()
        windll.user32.GetCursorPos(byref(pt))
        return (pt.x, pt.y)

    def _getPixelColor(self):
        """Returns pixel color of current mouse point position
        """
        hdc = windll.user32.GetDC(0)

        cursor_pos = self._getCursorPos()
        rgb = windll.gdi32.GetPixel(hdc, *cursor_pos)

        windll.user32.ReleaseDC(0, hdc)

        return (rgb & 0xff, (rgb >> 8) & 0xff, (rgb >> 16) & 0xff)

class Point(Structure):
    _fields_ = [('x', c_long), ('y', c_long)]