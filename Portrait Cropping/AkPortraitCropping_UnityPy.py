#! /usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'aelurum'
__version__ = "0.7b"

import concurrent.futures
import os
import sys
import traceback
from collections import defaultdict
from datetime import datetime
from enum import Enum, auto
from io import BytesIO
from zipfile import ZipFile, is_zipfile, Path as ZipPath

import UnityPy
from PIL import Image


class SourceType(Enum):
    APK = auto()
    DIR = auto()


class ImageFormat(Enum):
    PNG = auto()
    WEBP = auto()


class PortraitHub:
    """Represents a custom portrait hub with data needed for cropping, based on game's portrait hub and atlas assets.

    Attributes
    ----------
    sprite_count : int
        Total number of sprites in the game's portrait hub.
    loaded_sprite_count : int
        Number of successfully loaded sprites.
    sprite_size : tuple[int, int]
        A 2-tuple, containing (width, height) in pixels.
    atlases : list[dict]
        List of dictionaries with atlases data and sprites data from the game's atlas assets.

        Structure example:
        [
            {
                "texture_path_id": int,
                "alpha_path_id": int,
                "texture_name": str,
                "alpha_name": str,
                "sprites": list[dict]
                [
                    {
                        "name": str,
                        "guid": str,
                        "atlas": int,
                        "rect": dict[str, int]
                        {
                            "x": int,
                            "y": int,
                            "w": int,
                            "h": int
                        },
                        "rotate": int  # 0 or 1
                    },
                ]
            },
        ]
    is_loaded : bool
        Flag indicating that the custom portrait hub was loaded correctly.

    Methods
    -------
    crop_multithreaded(out_dir, img_format):
        Crop sprites using threads and return total number of processed sprites.
    """

    def __init__(self, path: str):
        """Custom portrait hub constructor.

        Parameters
        ----------
        path : str
            Path to the game`s .apk file or to the "charportraits" folder
            containing portrait asset files (portrait_hub.ab, pack[x].ab).
        """
        self.sprite_count: int = 0
        self.loaded_sprite_count: int = 0
        self.sprite_size: tuple = ()
        self.atlases: list = []
        self.is_loaded: bool = False
        self._input_path: str = ''
        self._source_type: SourceType
        self._unity_env = UnityPy.Environment()
        self._load_unity_env(path)
        self._parse_hub()

    def _load_unity_env(self, path: str):
        """Validate the specified path and load unity assets into memory."""
        self._input_path = os.path.abspath(os.path.normpath(path).replace('"', ''))
        if not os.path.exists(self._input_path):
            sys.exit(f'[Error] Incorrect path: "{self._input_path}". \n'
                     f'Specified .apk file or assets folder was not found.')

        if os.path.isdir(self._input_path):
            self._source_type = SourceType.DIR
            # Not sure whether to disable recursive folder loading here
            print('Loading assets..')
            self._unity_env.load_folder(self._input_path)
        elif os.path.isfile(self._input_path) and self._input_path.lower().endswith('.apk'):
            self._source_type = SourceType.APK
            if not is_zipfile(self._input_path):
                sys.exit(f'[Error] The specified .apk file "{self._input_path}" cannot be parsed.')

            print('Parsing apk..')
            with ZipFile(self._input_path, 'r') as apk_file:
                hub_dir = ZipPath(apk_file, 'assets/AB/Android/arts/charportraits/')
                if hub_dir.exists():
                    for asset_path in hub_dir.iterdir():
                        file = BytesIO(asset_path.read_bytes())
                        name = str(asset_path).lstrip(self._input_path)[1:]
                        self._unity_env.load_file(file, name=name)
                else:
                    sys.exit(f'[Error] "charportraits" folder was not found in this apk file: "{self._input_path}".')
        else:
            sys.exit(f'[Error] Unsupportable input file "{self._input_path}".\n'
                     f'Specify path to the .apk file or to the folder with the portrait assets.')

    def _parse_hub(self):
        """Find portrait hub in the loaded unity assets and parse it."""
        hub = self._unity_env.container.get('assets/torappu/dynamicassets/arts/charportraits/portrait_hub.asset')
        if hub:
            hub_dict = hub.read_typetree()
            sprite_list = hub_dict['_sprites']  # list[dict]
            self.sprite_count = len(sprite_list)
            self.sprite_size = tuple(hub_dict['_spriteSize'].values())  # {"width": int, "height": int}

            # generate a dict of { atlas_index: [sprite_name,], } to filter sprites later
            atlas_dict = defaultdict(list)
            for sprite in sprite_list:
                atlas_dict[sprite["atlas"]].append(sprite["name"])

            atlas_container_list = [f'assets/torappu/dynamicassets/{x}.asset' for x in hub_dict['_atlases']]
            self._parse_atlases(atlas_container_list, atlas_dict)
            self.is_loaded = True
        else:
            mode = '.apk file' if self._source_type == SourceType.APK else 'folder'
            sys.exit(f'[Error] "portrait_hub" was not found in this {mode}: "{self._input_path}".')

    def _parse_atlases(self, atlas_container_list: list, atlas_dict: dict):
        """Parse atlas assets and load sprites data."""
        loaded_sprite_count = 0
        loaded_atlas_count = 0
        for atlas_container in atlas_container_list:
            atlas_data = self._unity_env.container.get(atlas_container.lower())
            if atlas_data:
                atlas = atlas_data.read_typetree()
                if not self._validate_atlas(atlas, atlas_container):
                    continue
                sprite_list = atlas['_sprites']
                atlas_index = atlas['_index']
                filtered_sprite_list = [
                    sprite
                    for sprite in sprite_list
                    if sprite['name'] in atlas_dict[atlas_index]
                ]
                self.atlases.append(
                    {
                        'texture_name': atlas['_sign']['m_atlases'][0]['name'],
                        'alpha_name': atlas['_sign']['m_alphas'][0]['name'],
                        'texture_path_id': atlas['_atlas']['texture']['m_PathID'],
                        'alpha_path_id': atlas['_atlas']['alpha']['m_PathID'],
                        'sprites': filtered_sprite_list,
                    }
                )
                loaded_sprite_count += len(filtered_sprite_list)
                loaded_atlas_count += 1

        self.loaded_sprite_count = loaded_sprite_count
        print(f'Loaded [{loaded_sprite_count}/{self.sprite_count}] sprite data, '
              f'from [{loaded_atlas_count}/{len(atlas_container_list)}] atlas(-es).')

    @staticmethod
    def _validate_atlas(atlas: dict, atlas_container: str) -> bool:
        """Check that the atlas asset meets required conditions and return `False` if the check fails."""
        keys = ('_sprites', '_index', '_sign')
        if any(key not in atlas for key in keys):
            print(f'[Error] Unsupported atlas asset "{atlas_container}".\n'
                  f'Unknown atlas format.')
            return False

        sign_keys = ('m_atlases', 'm_alphas')
        if any(key not in atlas['_sign'] for key in sign_keys):
            print(f'[Error] Unsupported atlas asset "{atlas_container}".\n'
                  f'Atlas images were not found.')
            return False

        if len(atlas['_sprites']) == 0:
            print(f'[Warning] Atlas asset "{atlas_container}" doesn`t contain portraits.')
            return False

        atlas_imgs_count = (
            len(atlas['_sign']['m_atlases']),
            len(atlas['_sign']['m_alphas'])
        )
        if any(count != 1 for count in atlas_imgs_count):
            print(f'[Error] Unsupported atlas asset "{atlas_container}"\n'
                  f'Incorrect number of atlas images.')
            return False

        return True

    def crop_multithreaded(self, out_dir: str, img_format: ImageFormat) -> int:
        """Crop sprites using threads and return total number of processed sprites.

        Parameters
        ----------
        out_dir : str
            Path to the destination folder where portraits will be exported.
        img_format : ImageFormat
            Format of the output portrait images (.png/.webp).
        """
        if not self.is_loaded:
            print('[Error] Custom portrait hub was not loaded correctly.')
            return 0

        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        args = (
            (atlas, img_format, out_dir)
            for atlas in self.atlases
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            futures = (executor.submit(self._crop, arg) for arg in args)
            proc_count = sum(
                future.result()
                for future in concurrent.futures.as_completed(futures)
            )

        return proc_count

    def _crop(self, args_tuple: tuple) -> int:
        """Crop sprites from specified atlas and return processed sprite count."""
        atlas: dict
        img_format: ImageFormat
        out_dir: str
        if args_tuple and isinstance(args_tuple, tuple) and len(args_tuple) == 3:
            atlas, img_format, out_dir = args_tuple
        else:
            arg_error = f'{"args type" if not isinstance(args_tuple, tuple) else "args length"}'
            sys.exit(f'_crop(): [Error] Incorrect {arg_error}.')

        atlas_tex = None
        atlas_alpha = None
        for asset in self._unity_env.assets:
            texture_asset = asset.objects.get(atlas['texture_path_id'])
            alpha_asset = asset.objects.get(atlas['alpha_path_id'])
            if all((texture_asset, alpha_asset)):
                atlas_tex = texture_asset.read().image
                atlas_alpha = alpha_asset.read().image
                break
        if not atlas_tex:
            print(f'[Warning] Atlas image "{atlas["texture_name"]}" was not found.')
            return 0
        if not atlas_alpha:
            print(f'[Warning] Alpha image "{atlas["alpha_name"]}" was not found.')
            return 0

        atlas_alpha = atlas_alpha.convert(mode='L')
        if atlas_alpha.size != atlas_tex.size:
            atlas_alpha = atlas_alpha.resize(size=atlas_tex.size, resample=Image.BICUBIC)
        atlas_tex.putalpha(atlas_alpha)
        atlas_alpha.close()

        proc_count = 0
        for sprite in atlas['sprites']:
            sprite_name = sprite['name']
            rect = sprite['rect']
            rotate = sprite['rotate']

            # Uses flipped Y coord
            portrait = atlas_tex.crop(
                box=(
                    rect['x'],  # x
                    atlas_tex.height - (rect['y'] + rect['h']),  # y
                    rect['x'] + rect['w'],  # width
                    atlas_tex.height - rect['y']  # height
                )
            )
            if rotate:
                portrait = portrait.transpose(method=Image.ROTATE_270)
            if rect['w'] not in self.sprite_size or rect['h'] not in self.sprite_size:  # size fix (just in case)
                temp = Image.new(mode='RGBA', size=self.sprite_size, color=(1, 1, 1, 0))
                temp.alpha_composite(
                    im=portrait,
                    dest=(
                        max(self.sprite_size[0] - portrait.width, 0),
                        max(self.sprite_size[1] - portrait.height, 0)
                    )
                )
                portrait = temp

            output_path = os.path.join(out_dir, f'{sprite_name}.{img_format.name.lower()}')
            save_options = {'format': img_format.name}
            if img_format == ImageFormat.PNG:
                save_options['compress_level'] = 7
            elif img_format == ImageFormat.WEBP:
                save_options['lossless'] = False
            portrait.save(output_path, **save_options)
            proc_count += 1
        atlas_tex.close()
        print(f'Processed "{atlas["texture_name"]}" atlas.\n', end='')  # fix for "parallel" processing

        return proc_count


if __name__ == '__main__':
    image_format = ImageFormat.PNG

    for i, val in enumerate(sys.argv):
        if val.lower() == '-png':
            image_format = ImageFormat.PNG
            _ = sys.argv.pop(i)
            break
        if val.lower() == '-webp':
            image_format = ImageFormat.WEBP
            _ = sys.argv.pop(i)
            break

    current_dir = os.path.dirname(os.path.abspath(__file__))
    date = datetime.date(datetime.now()).isoformat()
    output_format = f'-{image_format.name.lower()}'
    output_dir = os.path.join(current_dir, '_output', date + output_format)

    input_path = ''
    if len(sys.argv) == 2:
        input_path = sys.argv[1]
    elif len(sys.argv) > 2:
        sys.exit('[Error] Too many arguments. Or unsupported image_format value.')
    elif len(sys.argv) == 1:
        input_path = input('Please enter a path to the game`s .apk file or to the "charportraits" folder '
                           'containing portrait asset files (portrait_hub.ab, pack[x].ab):\n')
    if not input_path:
        sys.exit('No input files.')

    try:
        portrait_hub = PortraitHub(input_path)
        processed_count = portrait_hub.crop_multithreaded(output_dir, image_format)
        print(f'Processed [{processed_count}/{portrait_hub.loaded_sprite_count}] portraits.')
    except Exception:
        print(traceback.format_exc())
        input('\nPress ENTER to exit..')
