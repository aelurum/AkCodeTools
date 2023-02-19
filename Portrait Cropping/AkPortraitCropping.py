#! /usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'VaDiM#5824'
__version__ = '0.7b'

import json
import os
import sys
import traceback
from collections import defaultdict
from datetime import datetime
from enum import Enum, auto
from multiprocessing import Pool

try:
    from PIL import Image
except ModuleNotFoundError:
    sys.exit('Pillow library was not found.\n'
             'Please install it using "python3 -m pip install --upgrade Pillow"')


class ImageFormat(Enum):
    PNG = auto()
    WEBP = auto()


def validate_json_atlas(atlas_json: dict, atlas_path: str):
    """Check that the atlas json file meets required conditions and raise NotImplementedError if the check fails."""
    keys = ('_sprites', '_index', '_sign')
    if any(key not in atlas_json for key in keys):
        raise NotImplementedError(
            f'[Error] Unsupported atlas json file "{atlas_path}".\n'
            f'Unknown atlas format.'
        )

    sign_keys = ('m_atlases', 'm_alphas')
    if any(key not in atlas_json['_sign'] for key in sign_keys):
        raise NotImplementedError(
            f'[Error] Unsupported atlas json file "{atlas_path}".\n'
            f'Atlas images were not found.'
        )

    atlas_imgs_count = (
        len(atlas_json['_sign']['m_atlases']),
        len(atlas_json['_sign']['m_alphas'])
    )
    if any(count != 1 for count in atlas_imgs_count):
        raise NotImplementedError(
            f'[Error] Unsupported atlas json file "{atlas_path}".\n'
            f'Incorrect number of atlas images.'
        )


def load_portrait_hub(json_dir: str, hub_name: str) -> dict:
    """Parse jsons and return custom hub with data needed for cropping as a dict.

    Custom hub structure:
    {
        "sprite_count": int,
        "loaded_sprite_count": int,
        "root_atlas_name": str,
        "sprite_size": tuple[int, int]
        atlases: list[dict]
        [
            {
                "atlas_name": str,
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
    }
    """
    hub = {
        'sprite_count': 0,
        'loaded_sprite_count': 0,
        'root_atlas_name': "",
        'sprite_size': (),
        'atlases': [],
    }
    portrait_hub_path = os.path.join(json_dir, hub_name)
    if not os.path.exists(portrait_hub_path):
        sys.exit(f'[Error] "portrait_hub.json" was not found in this path: "{portrait_hub_path}"')

    with open(portrait_hub_path, "rb") as hub_data:
        json_hub = json.load(hub_data)

    sprite_list = json_hub['_sprites']  # list[dict]
    hub['sprite_count'] = len(sprite_list)
    hub['root_atlas_name'] = json_hub['_rootAtlasName']
    hub['sprite_size'] = tuple(json_hub['_spriteSize'].values())  # {"width": int, "height": int}

    # generate a dict of { atlas_index: [sprite_name, ], } to filter sprites later
    atlas_dict = defaultdict(list)
    for sprite in sprite_list:
        atlas_dict[sprite["atlas"]].append(sprite["name"])

    atlas_path_list = [
        os.path.join(json_dir, '{0}#{1}.json'.format(hub['root_atlas_name'], x))
        for x in atlas_dict.keys()
    ]

    loaded_sprite_count = 0
    loaded_atlas_count = 0
    for atlas_path in atlas_path_list:
        try:
            with open(atlas_path, "rb") as atlas_data:
                json_atlas = json.load(atlas_data)

            validate_json_atlas(json_atlas, atlas_path)
            sprite_list = json_atlas['_sprites']
            atlas_index = json_atlas['_index']
            filtered_sprite_list = [
                sprite
                for sprite in sprite_list
                if sprite['name'] in atlas_dict[atlas_index]
            ]
            hub['atlases'].append(
                {
                    'atlas_name': json_atlas['_sign']['m_atlases'][0]['name'],
                    'alpha_name': json_atlas['_sign']['m_alphas'][0]['name'],
                    'sprites': filtered_sprite_list,
                }
            )
            loaded_sprite_count += len(filtered_sprite_list)
            loaded_atlas_count += 1
        except FileNotFoundError:
            pass
        except NotImplementedError as error:
            print(error)

    hub['loaded_sprite_count'] = loaded_sprite_count
    print(f'Loaded [{loaded_sprite_count}/{hub["sprite_count"]}] sprite data, '
          f'from [{loaded_atlas_count}/{len(atlas_path_list)}] atlas(-es).')

    return hub


def crop_multiprocessing(tex_dir: str, out_dir: str, img_format: ImageFormat, hub: dict) -> int:
    """Crop sprites using multiprocessing and return total number of processed sprites.

    Parameters
    ----------
    tex_dir : str
        Path to the Texture2D folder.
    out_dir : str
        Path to the destination folder where portraits will be exported.
    img_format : ImageFormat
        Format of the output portrait images (.png/.webp).
    hub : dict
        Custom hub dictionary.
    """
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    args = (
        (atlas, img_format, hub['sprite_size'], tex_dir, out_dir)
        for atlas in hub['atlases']
    )
    with Pool(processes=os.cpu_count()) as pool:
        proc_count = sum(pool.map(_crop, args))

    return proc_count


def _crop(args_tuple: tuple) -> int:
    """Crop sprites from specified atlas and return processed sprite count."""
    atlas: dict
    img_format: ImageFormat
    sprite_size: tuple
    tex_dir: str
    out_dir: str
    if args_tuple and isinstance(args_tuple, tuple) and len(args_tuple) == 5:
        atlas, img_format, sprite_size, tex_dir, out_dir = args_tuple
    else:
        arg_error = f'{"args type" if not isinstance(args_tuple, tuple) else "args length"}'
        sys.exit(f'_crop(): [Error] Incorrect {arg_error}.')

    atlas_path = os.path.join(tex_dir, f'{atlas["atlas_name"]}.png')
    alpha_path = os.path.join(tex_dir, f'{atlas["alpha_name"]}.png')

    atlas_tex = Image.open(atlas_path)
    with Image.open(alpha_path) as atlas_alpha:
        atlas_alpha = atlas_alpha.convert(mode='L')
        if atlas_alpha.size != atlas_tex.size:
            atlas_alpha = atlas_alpha.resize(size=atlas_tex.size, resample=Image.BICUBIC)
        atlas_tex.putalpha(atlas_alpha)

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
        if rect['w'] not in sprite_size or rect['h'] not in sprite_size:  # size fix (just in case)
            temp = Image.new(mode='RGBA', size=sprite_size, color=(1, 1, 1, 0))
            temp.alpha_composite(
                im=portrait,
                dest=(
                    max(sprite_size[0] - portrait.width, 0),
                    max(sprite_size[1] - portrait.height, 0)
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
    print(f'Processed "{atlas["atlas_name"]}" atlas.\n', end='')  # fix for "parallel" processing

    return proc_count


if __name__ == '__main__':
    image_format = ImageFormat.PNG

    cmd_args = [x.lower() for x in sys.argv]
    if '-png' in cmd_args:
        image_format = ImageFormat.PNG
    elif '-webp' in cmd_args:
        image_format = ImageFormat.WEBP

    current_dir = os.path.dirname(os.path.abspath(__file__))
    date = datetime.date(datetime.now()).isoformat()
    input_json_path = os.path.join(current_dir, 'MonoBehaviour')
    input_tex_path = os.path.join(current_dir, 'Texture2D')
    output_format = f'-{image_format.name.lower()}'
    output_dir = os.path.join(current_dir, '_output', date + output_format)

    portrait_hub_name = 'portrait_hub.json'
    try:
        portrait_hub = load_portrait_hub(input_json_path, portrait_hub_name)
        processed_count = crop_multiprocessing(input_tex_path, output_dir, image_format, portrait_hub)
        print(f'Processed [{processed_count}/{portrait_hub["loaded_sprite_count"]}] portraits.')
    except Exception:
        print(traceback.format_exc())
        input('\nPress ENTER to exit..')
