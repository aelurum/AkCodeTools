#! /usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'VaDiM#5824'
__version__ = "0.6b"

import json
import os
import sys
import traceback
from datetime import datetime
from multiprocessing import Pool
try:
    from PIL import Image
except ModuleNotFoundError:
    print('Pillow library was not found.\nPlease install it using "python3 -m pip install --upgrade Pillow"')
    input('\nPress ENTER to exit..')
    exit()


def validate_json_atlas(atlas_json: dict, atlas_path: str):
    """ Check that the atlas json file meets required conditions and raise NotImplementedError if the check fails. """
    keys = ('_sprites', '_index', '_sign')
    if any(key not in atlas_json for key in keys):
        raise NotImplementedError(f'[Error] Unsupported atlas json file "{atlas_path}"')

    sign_keys = ('m_atlases', 'm_alphas')
    if any(key not in atlas_json['_sign'] for key in sign_keys):
        raise NotImplementedError(f'[Error] Unsupported atlas json file "{atlas_path}"')

    if len(atlas_json['_sign']['m_atlases']) != 1 or len(atlas_json['_sign']['m_alphas']) != 1:
        raise NotImplementedError(f'[Error] Unsupported atlas json file "{atlas_path}"\n'
                                  f'"m_atlases" or "m_alphas" length was != 1.')


def load_portrait_hub(json_dir: str, hub_name: str) -> dict:
    """
    Parse jsons and return custom hub with needed data as a dict.

    Custom hub structure:

    {
        "sprite_count": int,
        "loaded_sprite_count": int,
        "root_atlas_name": str,
        "sprite_size":
        {
            "width": int,
            "height": int,
        },
        atlases:
        [
            {
                "atlas_name": str,
                "alpha_name": str,
                "sprites":
                [
                    {
                        "name": str,
                        "guid": str,
                        "atlas": int,
                        "rect":
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
        'sprite_size': {},
        'atlases': [],
    }
    portrait_hub_path = os.path.join(json_dir, hub_name)
    if not os.path.exists(portrait_hub_path):
        print(f'[Error] "portrait_hub.json" was not found in this path: "{portrait_hub_path}"')
        input('\nPress ENTER to exit..')
        exit()

    with open(portrait_hub_path, 'r', encoding='UTF-8') as hub_data:
        json_hub = json.load(hub_data)
        sprite_list = json_hub['_sprites']  # [dict, dict, dict, ]

        hub['sprite_count'] = len(sprite_list)
        hub['root_atlas_name'] = json_hub['_rootAtlasName']
        hub['sprite_size'] = json_hub['_spriteSize']

        # generate a dict of { atlas_index: [sprite_name, ], } to filter sprites later
        atlas_dict = {}
        for sprite in sprite_list:
            if sprite['atlas'] in atlas_dict:
                atlas_dict[sprite['atlas']].append(sprite['name'])
            else:
                atlas_dict[sprite['atlas']] = [sprite['name'], ]

        atlas_path_list = [
            os.path.join(json_dir, '{0}#{1}.json'.format(hub['root_atlas_name'], x))
            for x in atlas_dict.keys()
        ]

        loaded_sprite_count = 0
        loaded_atlas_count = 0
        for atlas_path in atlas_path_list:
            try:
                with open(atlas_path, 'r', encoding='UTF-8') as atlas_data:
                    json_atlas = json.load(atlas_data)
                    validate_json_atlas(json_atlas, atlas_path)
                    sprite_list = json_atlas['_sprites']
                    atlas_index = json_atlas['_index']
                    filtered_sprite_list = [sprite for sprite in sprite_list if sprite['name'] in atlas_dict[atlas_index]]
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
        print(f'Loaded [{loaded_sprite_count}/{hub["sprite_count"]}] sprite data, from [{loaded_atlas_count}/{len(atlas_path_list)}] atlas(-es).')

        return hub


def multiprocessing_crop(tex_dir: str, out_dir: str, img_format: str, hub: dict) -> int:
    """ Crop sprites using multiprocessing and return processed sprite count. """
    proc_count = 0
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    args = [(tex_dir, out_dir, img_format, hub, atlas) for atlas in hub['atlases']]
    with Pool(processes=os.cpu_count()) as pool:
        proc_count = sum(pool.map(_crop, args))

    return proc_count


def _crop(t_args: tuple = None,
          tex_dir: str = '',
          out_dir: str = '',
          img_format: str = '',
          hub: dict = None,
          atlas: dict = None) -> int:
    """ Crop sprites and return processed sprite count. """
    if t_args and isinstance(t_args, tuple) and len(t_args) == 5:
        tex_dir, out_dir, img_format, hub, atlas = t_args

    sprite_size = (hub['sprite_size']['width'], hub['sprite_size']['height'])

    proc_count = 0
    atlas_path = os.path.join(tex_dir, f'{atlas["atlas_name"]}.png')
    alpha_path = os.path.join(tex_dir, f'{atlas["alpha_name"]}.png')

    with Image.open(atlas_path) as atlas_tex:
        with Image.open(alpha_path) as atlas_alpha:
            atlas_alpha = atlas_alpha.convert(mode='L')
            if atlas_alpha.size != atlas_tex.size:
                atlas_alpha = atlas_alpha.resize(size=atlas_tex.size, resample=Image.BICUBIC)
            atlas_tex.putalpha(atlas_alpha)

            for sprite in atlas['sprites']:
                sprite_name = sprite['name']
                rect = sprite['rect']
                rotate = sprite['rotate']

                # Uses flipped Y coord
                portrait = atlas_tex.crop(box=(rect['x'],  # x
                                               atlas_tex.height - (rect['y'] + rect['h']),  # y
                                               rect['x'] + rect['w'],  # width
                                               atlas_tex.height - rect['y']))  # height
                if rotate:
                    portrait = portrait.transpose(method=Image.ROTATE_270)
                if rect['w'] not in sprite_size or rect['h'] not in sprite_size:  # size fix (just in case)
                    temp = Image.new(mode='RGBA', size=sprite_size, color=(1, 1, 1, 0))
                    temp.alpha_composite(im=portrait, dest=(max(sprite_size[0] - portrait.width, 0),
                                                            max(sprite_size[1] - portrait.height, 0)))
                    portrait = temp

                output_path = os.path.join(out_dir, f'{sprite_name}.{img_format.lower()}')
                save_options = {'format': img_format}
                if img_format.lower() == 'png':
                    save_options['compress_level'] = 7
                elif img_format.lower() == 'webp':
                    save_options['lossless'] = False
                portrait.save(output_path, **save_options)
                proc_count += 1
    print(f'Processed "{atlas["atlas_name"]}" atlas.\n', end='')

    return proc_count


if __name__ == '__main__':
    image_format = 'PNG'  # Supported formats: 'PNG', 'WEBP'

    cmd_args = [x.lower() for x in sys.argv]
    if '-png' in cmd_args:
        image_format = 'PNG'
    elif '-webp' in cmd_args:
        image_format = 'WEBP'

    current_dir = os.path.dirname(os.path.abspath(__file__))
    date = datetime.date(datetime.now()).isoformat()
    input_json_path = os.path.join(current_dir, 'MonoBehaviour')
    input_tex_path = os.path.join(current_dir, 'Texture2D')
    output_dir = os.path.join(current_dir, '_output', date)

    portrait_hub_name = 'portrait_hub.json'
    try:
        portrait_hub = load_portrait_hub(input_json_path, portrait_hub_name)
        processed_count = multiprocessing_crop(input_tex_path, output_dir, image_format, portrait_hub)
        print(f'Processed [{processed_count}/{portrait_hub["loaded_sprite_count"]}] portraits.')
    except Exception as e:
        print(traceback.format_exc())

    input('\nPress ENTER to exit..')
